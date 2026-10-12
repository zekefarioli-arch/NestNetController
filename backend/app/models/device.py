from pydantic import BaseModel
from typing import List, Optional

class Device(BaseModel):
    name: str
    mac: str
    description: Optional[str] = None

class DeviceGroup(BaseModel):
    name: str
    description: Optional[str] = None
    devices: List[Device]
    protected: bool = False
    # Default-deny: a group is blocked unless it is protected, always_on, or switched on in the UI
    always_on: bool = False
    auto_detect: bool = False
    enabled: bool = True

class NewDeviceGroup(BaseModel):
    name: str
    description: Optional[str] = None
    auto_detect: bool = False

class NewDevice(BaseModel):
    name: str
    mac: str
    description: Optional[str] = None

class GroupStatusUpdate(BaseModel):
    group_name: str
    enabled: bool

class QuickAction(BaseModel):
    action: str  # "only_essential", "only_essential_security", "enable_all", "disable_all", "block_kids"

class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class ActionLog(BaseModel):
    timestamp: str
    user: str
    action: str
    target: str
    success: bool
    details: Optional[str] = None
