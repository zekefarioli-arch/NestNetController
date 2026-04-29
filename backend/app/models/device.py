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
    auto_detect: bool = False
    enabled: bool = True

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
