from fastapi import APIRouter, Depends
from typing import List
from ..models import ActionLog
from ..services import logging_service
from .auth import get_current_user

router = APIRouter(prefix="/logs", tags=["logs"])

@router.get("/recent", response_model=List[ActionLog])
async def get_recent_logs(
    limit: int = 100,
    current_user: str = Depends(get_current_user)
):
    """Get recent activity logs"""
    logs = logging_service.get_recent_logs(limit=limit)
    return logs
