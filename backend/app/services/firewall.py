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
    
    def block_device(self, device: Device) -> Dict:
        """Block internet access for a specific device by MAC address"""
        mac = device.mac.upper()
        
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
            f"Blocking device {device.name} ({mac})"
        )
    
    def unblock_device(self, device: Device) -> Dict:
        """Unblock internet access for a specific device by MAC address"""
        mac = device.mac.upper()
        
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
            f"Unblocking device {device.name} ({mac})"
        )
    
    def block_group(self, devices: List[Device]) -> List[Dict]:
        """Block all devices in a group"""
        results = []
        for device in devices:
            result = self.block_device(device)
            results.append(result)
        return results
    
    def unblock_group(self, devices: List[Device]) -> List[Dict]:
        """Unblock all devices in a group"""
        results = []
        for device in devices:
            result = self.unblock_device(device)
            results.append(result)
        return results
    
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
