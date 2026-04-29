import json
import logging
from datetime import datetime
from typing import List
from ..config import settings
from ..models import ActionLog

logger = logging.getLogger(__name__)

class LoggingService:
    def __init__(self):
        self.log_file = settings.log_file_path
    
    def log_action(self, user: str, action: str, target: str, success: bool, details: str = None) -> ActionLog:
        """Log an action to the activity log"""
        log_entry = ActionLog(
            timestamp=datetime.utcnow().isoformat(),
            user=user,
            action=action,
            target=target,
            success=success,
            details=details
        )
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(log_entry.model_dump()) + "\n")
            logger.info(f"Action logged: {user} - {action} - {target} - {'SUCCESS' if success else 'FAILED'}")
        except Exception as e:
            logger.error(f"Failed to write to log file: {e}")
        
        return log_entry
    
    def get_recent_logs(self, limit: int = 100) -> List[ActionLog]:
        """Get recent activity logs"""
        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
            
            logs = []
            for line in reversed(lines[-limit:]):
                try:
                    log_data = json.loads(line.strip())
                    logs.append(ActionLog(**log_data))
                except json.JSONDecodeError:
                    continue
            
            return logs
        except FileNotFoundError:
            logger.warning(f"Log file not found: {self.log_file}")
            return []
        except Exception as e:
            logger.error(f"Failed to read log file: {e}")
            return []

logging_service = LoggingService()
