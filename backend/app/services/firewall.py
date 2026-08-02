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

    def sync_allowlist(self, all_devices: List[Device]) -> Dict:
        """
        Ensure only known devices (from devices.yaml) can reach the WAN.
        Removes the broad LAN->WAN accept-all rule (one-time migration,
        safe to call repeatedly), clears any previously-managed allow
        rules, then re-adds one ACCEPT per known MAC. Block rules
        (inserted at the top via -I) always take priority over these,
        since these are appended at the bottom via -A.
        Idempotent - safe to call on every startup and every reload.
        """
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would sync allowlist for {len(all_devices)} known devices")
            return {"success": True, "dry_run": True, "devices_count": len(all_devices)}

        # 1. Remove the broad LAN->WAN accept-all rule if still present
        remove_wide = subprocess.run(
            ["iptables", "-D", "FORWARD", "-i", self.lan_interface, "-o", self.wan_interface, "-j", "ACCEPT"],
            capture_output=True, text=True
        )
        if remove_wide.returncode == 0:
            logger.info(f"[EXECUTED] Removed broad accept-all rule ({self.lan_interface} -> {self.wan_interface})")

        # 2. Remove previously-managed allowlist rules (tagged with our comment)
        while True:
            check = subprocess.run(
                ["iptables", "-L", "FORWARD", "-v", "-n", "--line-numbers"],
                capture_output=True, text=True
            )
            managed = [l for l in check.stdout.split("\n") if self.ALLOWLIST_TAG in l]
            if not managed:
                break
            line_num = managed[0].split()[0]
            subprocess.run(["iptables", "-D", "FORWARD", line_num], capture_output=True, text=True)

        # 3. Add one ACCEPT per known MAC (deduplicated), appended at the end
        results = []
        seen_macs = set()
        for device in all_devices:
            mac = device.mac.upper()
            if mac in seen_macs or "PENDIENTE" in mac or "REEMPLAZAR" in mac:
                continue
            seen_macs.add(mac)
            command = [
                "iptables", "-A", "FORWARD",
                "-m", "mac", "--mac-source", mac,
                "-o", self.wan_interface,
                "-m", "comment", "--comment", self.ALLOWLIST_TAG,
                "-j", "ACCEPT"
            ]
            result = self._execute_command(command, f"ALLOWLIST: {device.name} (mac: {mac})")
            results.append(result)

        success = all(r.get("success", False) for r in results)
        logger.info(f"Allowlist sync complete: {len(results)} devices allowed")
        return {"success": success, "devices_count": len(results), "results": results}

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
