from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Network Configuration
    wan_interface: str = "ppp0"
    lan_interface: str = "enp5s0"
    # Input interfaces whose traffic to the WAN is always accepted (comma-separated), for
    # clients that are not identified by MAC: on the router, WireGuard runs in a container and
    # its clients reach the host as one source on the Docker bridge (docker0)
    allow_interfaces: str = ""
    
    # Application Settings
    dry_run: bool = True
    api_port: int = 8002
    ui_port: int = 3002
    
    # Security
    jwt_secret: str = "your-super-secret-jwt-key-change-this"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours
    admin_username: str = "admin"
    admin_password: str = "changeme"
    
    # Logging
    log_level: str = "INFO"
    
    # Paths
    devices_config_path: str = "/app/config/devices.yaml"
    log_file_path: str = "/app/logs/activity.log"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
