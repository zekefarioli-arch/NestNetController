from .auth import router as auth_router
from .devices import router as devices_router
from .logs import router as logs_router

__all__ = [
    "auth_router",
    "devices_router",
    "logs_router",
]
