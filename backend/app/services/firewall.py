import re
import shlex
import subprocess
import logging
from typing import List, Dict, Optional
from ..config import settings
from ..models import Device, ActionLog
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class FirewallService:
    def __init__(self):
        self.wan_interface = settings.wan_interface
        self.lan_interface = settings.lan_interface
        self.dry_run = settings.dry_run
        self.allow_interfaces = [i.strip() for i in settings.allow_interfaces.split(",") if i.strip()]
        self.MAC_RULE = re.compile(r"^-A FORWARD .*--mac-source (\S+) .*--comment nestnet-allow -j ACCEPT$")
        self.INTERFACE_RULE = re.compile(r"^-A FORWARD -i (\S+) .*--comment nestnet-allow-if -j ACCEPT$")
        
    def _execute_command(self, command: List[str], description: str) -> Dict:
        """Execute iptables command or simulate in dry-run mode"""
        cmd_str = " ".join(command)
        
        if self.dry_run:
            logger.info(f"[DRY-RUN] {description}: {cmd_str}")
            return {
                "success": True,
                "dry_run": True,
                "command": cmd_str,
                "description": description
            }
        
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"[EXECUTED] {description}: {cmd_str}")
            return {
                "success": True,
                "dry_run": False,
                "command": cmd_str,
                "description": description,
                "output": result.stdout
            }
        except subprocess.CalledProcessError as e:
            logger.error(f"[FAILED] {description}: {cmd_str} - Error: {e.stderr}")
            return {
                "success": False,
                "dry_run": False,
                "command": cmd_str,
                "description": description,
                "error": e.stderr
            }
    
    def block_device(self, device: Device, group_name: str = None) -> Dict:
        """Block internet access for a specific device by MAC address"""
        mac = device.mac.upper()
        group_tag = f" from group '{group_name}'" if group_name else ""
        
        # Block FORWARD chain for this MAC
        command = [
            "iptables",
            "-I", "FORWARD",
            "-m", "mac",
            "--mac-source", mac,
            "-o", self.wan_interface,
            "-j", "DROP"
        ]
        
        return self._execute_command(
            command,
            f"BLOCK: {device.name}{group_tag} (mac: {mac})"
        )
    
    def unblock_device(self, device: Device, group_name: str = None) -> Dict:
        """Unblock internet access for a specific device by MAC address"""
        mac = device.mac.upper()
        group_tag = f" from group '{group_name}'" if group_name else ""
        
        # Remove DROP rule for this MAC
        command = [
            "iptables",
            "-D", "FORWARD",
            "-m", "mac",
            "--mac-source", mac,
            "-o", self.wan_interface,
            "-j", "DROP"
        ]
        
        return self._execute_command(
            command,
            f"UNBLOCK: {device.name}{group_tag} (mac: {mac})"
        )
    
    def block_group(self, devices: List[Device], group_name: str = None) -> List[Dict]:
        """Block all devices in a group"""
        results = []
        for device in devices:
            result = self.block_device(device, group_name)
            results.append(result)
        return results
    
    def unblock_group(self, devices: List[Device], group_name: str = None) -> List[Dict]:
        """Unblock all devices in a group"""
        results = []
        for device in devices:
            result = self.unblock_device(device, group_name)
            results.append(result)
        return results

    ALLOWLIST_TAG = "nestnet-allow"
    INTERFACE_TAG = "nestnet-allow-if"
    OPEN_TAG = "nestnet-open"

    def _iptables(self, args: List[str]) -> subprocess.CompletedProcess:
        return subprocess.run(["iptables", *args], capture_output=True, text=True)

    def _rules(self, chain: str) -> List[str]:
        """Rules of a chain as `-A CHAIN ...` lines; empty if the chain does not exist."""
        result = self._iptables(["-S", chain])
        if result.returncode != 0:
            return []
        return [l for l in result.stdout.splitlines() if l.startswith("-A ")]

    def _delete_rule(self, rule: str, description: str) -> Dict:
        return self._execute_command(["iptables", "-D", *shlex.split(rule)[1:]], description)

    def _ensure_return_traffic_rule(self) -> None:
        """
        Replies from the internet must reach the LAN or default-deny would break every allowed
        device. The router already has this rule in DOCKER-USER; it is only added if missing.
        """
        chain = "DOCKER-USER" if self._iptables(["-S", "DOCKER-USER"]).returncode == 0 else "FORWARD"
        for c in ("DOCKER-USER", "FORWARD"):
            if any("ESTABLISHED" in r and f"-i {self.wan_interface} " in r and r.endswith("-j ACCEPT")
                   for r in self._rules(c)):
                return
        self._execute_command(
            ["iptables", "-I", chain, "1", "-i", self.wan_interface, "-m", "conntrack",
             "--ctstate", "RELATED,ESTABLISHED", "-j", "ACCEPT"],
            f"RETURN TRAFFIC: accept replies from {self.wan_interface} in {chain}"
        )

    def sync_allowlist(self, devices: List[Device], open_mode: bool = False) -> Dict:
        """
        Default-deny: only `devices` (and the interfaces in ALLOW_INTERFACES) can reach the WAN.

        The caller passes the devices that are allowed right now (device_service.get_allowed_devices():
        protected and always_on groups, plus the groups switched on in the UI). Everything else
        falls to the FORWARD chain's DROP policy, including devices nobody has listed.

        Order matters so nobody is cut by the sync itself: the new ACCEPT rules go in first, stale
        ones are removed next, the policy becomes DROP, and only then the broad "LAN to WAN
        accept all" rule is deleted (wherever it is: FORWARD or DOCKER-USER, whatever LAN
        interface it names). Block rules inserted at the top (-I) still win over these ACCEPTs.
        With open_mode ("Everything on") one extra tagged rule lets every client reach the WAN, for
        phones whose randomised MAC is on no list; it is removed again as soon as open_mode is off.
        Idempotent: safe on every startup and every reload.
        """
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would sync allowlist for {len(devices)} allowed devices")
            return {"success": True, "dry_run": True, "devices_count": len(devices)}

        self._ensure_return_traffic_rule()
        results = []

        # 1. One ACCEPT per allowed MAC (deduplicated); stale and duplicate rules are removed
        wanted = {}
        for device in devices:
            mac = device.mac.upper()
            if "PENDIENTE" in mac or "REEMPLAZAR" in mac:
                continue
            wanted.setdefault(mac, device)
        present = set()
        for rule in self._rules("FORWARD"):
            m = self.MAC_RULE.match(rule)
            if not m:
                continue
            mac = m.group(1).upper()
            if mac in wanted and mac not in present:
                present.add(mac)
            else:
                results.append(self._delete_rule(rule, f"ALLOWLIST: remove stale rule (mac: {mac})"))
        for mac, device in wanted.items():
            if mac in present:
                continue
            results.append(self._execute_command(
                ["iptables", "-A", "FORWARD", "-o", self.wan_interface,
                 "-m", "mac", "--mac-source", mac, "-m", "comment", "--comment", self.ALLOWLIST_TAG,
                 "-j", "ACCEPT"],
                f"ALLOWLIST: {device.name} (mac: {mac})"
            ))

        # 2. Interfaces that are always allowed (WireGuard clients arrive on the Docker bridge)
        wanted_ifs = set(self.allow_interfaces)
        present_ifs = set()
        for rule in self._rules("FORWARD"):
            m = self.INTERFACE_RULE.match(rule)
            if not m:
                continue
            if m.group(1) in wanted_ifs and m.group(1) not in present_ifs:
                present_ifs.add(m.group(1))
            else:
                results.append(self._delete_rule(rule, f"ALLOWLIST: remove stale interface rule ({m.group(1)})"))
        for iface in sorted(wanted_ifs - present_ifs):
            results.append(self._execute_command(
                ["iptables", "-A", "FORWARD", "-i", iface, "-o", self.wan_interface,
                 "-m", "comment", "--comment", self.INTERFACE_TAG, "-j", "ACCEPT"],
                f"ALLOWLIST: interface {iface}"
            ))

        # 2b. Open mode: one tagged accept-all rule (the tag keeps step 4 from deleting it)
        open_rules = [r for r in self._rules("FORWARD") if f"--comment {self.OPEN_TAG} " in r]
        if open_mode and not open_rules:
            results.append(self._execute_command(
                ["iptables", "-A", "FORWARD", "-o", self.wan_interface,
                 "-m", "comment", "--comment", self.OPEN_TAG, "-j", "ACCEPT"],
                "OPEN MODE: every client may reach the internet"
            ))
        elif not open_mode:
            for rule in open_rules:
                results.append(self._delete_rule(rule, "OPEN MODE ended: remove accept-all rule"))

        # 3. Anything not accepted above is dropped
        results.append(self._execute_command(
            ["iptables", "-P", "FORWARD", "DROP"], "Setting FORWARD chain default policy to DROP"
        ))

        # 4. Last, the broad "accept every LAN client" rule goes away
        removed_broad = 0
        broad = re.compile(rf"^-A (FORWARD|DOCKER-USER) -i (\S+) -o {re.escape(self.wan_interface)} -j ACCEPT$")
        for chain in ("DOCKER-USER", "FORWARD"):
            for rule in self._rules(chain):
                m = broad.match(rule)
                if m and m.group(2) not in wanted_ifs:
                    results.append(self._delete_rule(rule, f"DEFAULT-DENY: remove accept-all rule ({m.group(2)} -> {self.wan_interface}) from {chain}"))
                    removed_broad += 1

        success = all(r.get("success", False) for r in results)
        logger.info(f"Allowlist sync complete: {len(wanted)} devices allowed, "
                    f"{len(wanted_ifs)} interfaces allowed, {removed_broad} accept-all rules removed")
        return {"success": success, "devices_count": len(wanted), "results": results,
                "removed_accept_all": removed_broad}

    def get_current_rules(self) -> List[str]:
        """Get current iptables rules"""
        if self.dry_run:
            return ["[DRY-RUN MODE] No actual rules to display"]
        
        try:
            result = subprocess.run(
                ["iptables", "-L", "FORWARD", "-v", "-n"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.split("\n")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get iptables rules: {e.stderr}")
            return []
    
    def clear_all_rules(self) -> Dict:
        """Clear all NestNetController rules (emergency reset)"""
        command = ["iptables", "-F", "FORWARD"]
        return self._execute_command(
            command,
            "Clearing all FORWARD chain rules"
        )
    
    def initialize_firewall(self) -> Dict:
        """Initialize firewall with default ACCEPT policy"""
        command = ["iptables", "-P", "FORWARD", "ACCEPT"]
        return self._execute_command(
            command,
            "Setting FORWARD chain default policy to ACCEPT"
        )
    
    def get_blocked_macs(self) -> List[str]:
        """Get list of currently blocked MAC addresses"""
        if self.dry_run:
            return []
        
        try:
            result = subprocess.run(
                ["iptables", "-L", "FORWARD", "-v", "-n"],
                capture_output=True,
                text=True,
                check=True
            )
            
            blocked_macs = []
            for line in result.stdout.split("\n"):
                if "DROP" in line and "MAC" in line:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part.upper().replace(":", "").replace("-", "").isalnum() and len(part) == 17:
                            blocked_macs.append(part.upper())
            
            return blocked_macs
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get blocked MACs: {e.stderr}")
            return []

firewall_service = FirewallService()
