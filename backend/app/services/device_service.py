import json
import yaml
import logging
import os
import re
import shutil
from datetime import datetime
from typing import List, Dict, Optional
from ..config import settings
from ..models import Device, DeviceGroup

logger = logging.getLogger(__name__)

class DeviceService:
    def __init__(self):
        self.config_path = settings.devices_config_path
        self._groups_cache: Optional[List[DeviceGroup]] = None
    
    def load_groups(self, force_reload: bool = False) -> List[DeviceGroup]:
        """Load device groups from YAML configuration"""
        if self._groups_cache is not None and not force_reload:
            return self._groups_cache
        
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            groups = []
            
            # Load regular groups
            if 'groups' in config:
                for group_name, group_data in config['groups'].items():
                    devices = []
                    if 'devices' in group_data:
                        for device_data in group_data['devices']:
                            devices.append(Device(**device_data))
                    
                    groups.append(DeviceGroup(
                        name=group_name,
                        description=group_data.get('description', ''),
                        devices=devices,
                        protected=group_data.get('protected', False),
                        always_on=group_data.get('always_on', False),
                        auto_detect=group_data.get('auto_detect', False),
                        enabled=True  # Default to enabled
                    ))
            
            # Add kids group (auto-detect)
            if 'kids' in config:
                groups.append(DeviceGroup(
                    name='kids',
                    description=config['kids'].get('description', 'Unknown devices'),
                    devices=[],
                    protected=False,
                    auto_detect=True,
                    enabled=True
                ))
            
            self._groups_cache = groups
            logger.info(f"Loaded {len(groups)} device groups from configuration")
            return groups
            
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {self.config_path}")
            return []
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML configuration: {e}")
            return []
    
    def get_group(self, group_name: str) -> Optional[DeviceGroup]:
        """Get a specific group by name"""
        groups = self.load_groups()
        for group in groups:
            if group.name == group_name:
                return group
        return None
    
    def get_all_devices(self) -> List[Device]:
        """Get all devices from all groups"""
        groups = self.load_groups()
        all_devices = []
        for group in groups:
            if not group.auto_detect:
                all_devices.extend(group.devices)
        return all_devices
    
    # --- Default-deny: which groups reach the internet ---

    def _state_path(self) -> str:
        return os.path.join(os.path.dirname(self.config_path), "group_state.json")

    def is_always_allowed(self, group: DeviceGroup) -> bool:
        """Infrastructure and always_on groups (cameras, workstations) never need switching on."""
        return group.protected or group.always_on

    def get_enabled_groups(self) -> set:
        """Names of the other groups the user switched on. Empty when nothing was ever switched on."""
        try:
            with open(self._state_path(), 'r') as f:
                return set(json.load(f).get("enabled", []))
        except FileNotFoundError:
            return set()
        except (ValueError, OSError, AttributeError) as e:
            # An unreadable state fails closed: nothing is switched on
            logger.error(f"Cannot read {self._state_path()}: {e}")
            return set()

    def set_group_enabled(self, group_name: str, enabled: bool) -> None:
        names = self.get_enabled_groups()
        if enabled:
            names.add(group_name)
        else:
            names.discard(group_name)
        tmp_path = f"{self._state_path()}.tmp"
        with open(tmp_path, 'w') as f:
            json.dump({"enabled": sorted(names)}, f, indent=2)
        os.replace(tmp_path, self._state_path())

    def is_group_enabled(self, group: DeviceGroup) -> bool:
        """True when the group's devices are on the firewall allowlist (ignoring DROP blocks)."""
        return self.is_always_allowed(group) or group.name in self.get_enabled_groups()

    def get_allowed_devices(self) -> List[Device]:
        """Devices that get an ACCEPT rule to the internet: everything else is dropped."""
        allowed = []
        for group in self.load_groups():
            if not group.auto_detect and self.is_group_enabled(group):
                allowed.extend(group.devices)
        return allowed

    def get_devices_by_group(self, group_name: str) -> List[Device]:
        """Get all devices in a specific group"""
        group = self.get_group(group_name)
        if group:
            return group.devices
        return []
    
    def is_protected_group(self, group_name: str) -> bool:
        """Check if a group is protected (infrastructure)"""
        group = self.get_group(group_name)
        if group:
            return group.protected
        return False
    
    def reload_configuration(self):
        """Force reload of configuration from disk"""
        self._groups_cache = None
        return self.load_groups(force_reload=True)

    # --- Mutation support: backup, validate, atomic write, rotate ---

    MAC_PATTERN = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")

    def _backup_dir(self) -> str:
        backup_dir = os.path.join(os.path.dirname(self.config_path), ".backups")
        os.makedirs(backup_dir, exist_ok=True)
        return backup_dir

    def _backup_current_file(self) -> None:
        """Copy the current devices.yaml to .backups/ with a timestamp, if it exists."""
        if not os.path.exists(self.config_path):
            return
        backup_dir = self._backup_dir()
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S-%f")
        backup_path = os.path.join(backup_dir, f"devices.yaml.{timestamp}")
        shutil.copy2(self.config_path, backup_path)
        logger.info(f"Backed up devices.yaml to {backup_path}")

    def _rotate_backups(self, keep: int = 10) -> None:
        backup_dir = self._backup_dir()
        backups = sorted(f for f in os.listdir(backup_dir) if f.startswith("devices.yaml."))
        excess = len(backups) - keep
        for old_backup in backups[:max(excess, 0)]:
            os.remove(os.path.join(backup_dir, old_backup))

    def _groups_to_yaml_dict(self, groups: List[DeviceGroup]) -> dict:
        """Convert in-memory groups back to the devices.yaml structure."""
        result = {"groups": {}}
        for group in groups:
            if group.auto_detect:
                result["kids"] = {"description": group.description or "Unknown or unregistered devices"}
                continue
            result["groups"][group.name] = {
                "description": group.description or "",
                "protected": group.protected,
                "always_on": group.always_on,
                "devices": [
                    {"name": d.name, "mac": d.mac, "description": d.description}
                    for d in group.devices
                ],
            }
        return result

    def save_groups(self, groups: List[DeviceGroup]) -> None:
        """
        Backs up the current file, validates the new content against the real
        Pydantic models, then writes atomically. Never leaves devices.yaml in
        a partial or invalid state.
        """
        self._backup_current_file()

        yaml_content = self._groups_to_yaml_dict(groups)

        # Validate by re-parsing exactly as load_groups() would
        try:
            yaml_str = yaml.safe_dump(yaml_content, sort_keys=False)
            reparsed = yaml.safe_load(yaml_str)
            for group_name, group_data in reparsed.get("groups", {}).items():
                for device_data in group_data.get("devices", []):
                    Device(**device_data)
        except Exception as e:
            raise ValueError(f"Validation failed, nothing was written: {e}")

        tmp_path = f"{self.config_path}.tmp"
        with open(tmp_path, "w") as f:
            f.write(yaml_str)
        os.replace(tmp_path, self.config_path)

        self._rotate_backups(keep=10)
        self._groups_cache = None
        logger.info("devices.yaml updated and validated successfully")

    def add_group(self, name: str, description: Optional[str], auto_detect: bool) -> DeviceGroup:
        groups = self.load_groups()
        if any(g.name.lower() == name.lower() for g in groups):
            raise ValueError(f"Group '{name}' already exists")
        if name.lower() == "kids":
            raise ValueError("'kids' is a reserved group name")

        new_group = DeviceGroup(
            name=name,
            description=description or "",
            devices=[],
            protected=False,  # UI can never create protected groups
            always_on=False,
            auto_detect=auto_detect,
            enabled=True,
        )
        groups.append(new_group)
        self.save_groups(groups)
        return new_group

    def delete_group(self, name: str) -> None:
        groups = self.load_groups()
        target = next((g for g in groups if g.name == name), None)
        if target is None:
            raise LookupError(f"Group '{name}' not found")
        if target.protected:
            raise PermissionError(f"Cannot delete protected group '{name}'")
        if target.devices:
            raise ValueError(f"Group '{name}' still has {len(target.devices)} device(s); remove them first")

        remaining = [g for g in groups if g.name != name]
        self.save_groups(remaining)

    def add_device(self, group_name: str, device: Device) -> Device:
        mac = device.mac.upper()
        if not self.MAC_PATTERN.match(mac):
            raise ValueError(f"Invalid MAC address format: {device.mac}")

        groups = self.load_groups()
        target = next((g for g in groups if g.name == group_name), None)
        if target is None:
            raise LookupError(f"Group '{group_name}' not found")
        if target.auto_detect:
            raise ValueError("Cannot manually add devices to an auto-detect group")

        for g in groups:
            if any(d.mac.upper() == mac for d in g.devices):
                raise ValueError(f"MAC {mac} is already assigned to group '{g.name}'")

        device.mac = mac
        target.devices.append(device)
        self.save_groups(groups)
        return device

    def delete_device(self, group_name: str, mac: str) -> None:
        mac = mac.upper()
        groups = self.load_groups()
        target = next((g for g in groups if g.name == group_name), None)
        if target is None:
            raise LookupError(f"Group '{group_name}' not found")

        before = len(target.devices)
        target.devices = [d for d in target.devices if d.mac.upper() != mac]
        if len(target.devices) == before:
            raise LookupError(f"Device with MAC {mac} not found in group '{group_name}'")

        self.save_groups(groups)

    def restore_latest_backup(self) -> str:
        """Restore the most recent backup as the active devices.yaml. Returns the backup filename used."""
        backup_dir = self._backup_dir()
        backups = sorted(f for f in os.listdir(backup_dir) if f.startswith("devices.yaml."))
        if not backups:
            raise LookupError("No backups available to restore")

        latest = backups[-1]
        backup_path = os.path.join(backup_dir, latest)

        # Back up the current (about-to-be-overwritten) file too, so restore is itself reversible
        self._backup_current_file()

        tmp_path = f"{self.config_path}.tmp"
        shutil.copy2(backup_path, tmp_path)
        os.replace(tmp_path, self.config_path)

        self._groups_cache = None
        logger.info(f"Restored devices.yaml from backup {latest}")
        return latest


device_service = DeviceService()
