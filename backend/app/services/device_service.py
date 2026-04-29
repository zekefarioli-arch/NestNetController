import yaml
import logging
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

device_service = DeviceService()
