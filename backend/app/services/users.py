"""
Panel users. Passwords live hashed (scrypt, from the standard library) in config/users.yaml,
managed with `python -m app.users` inside the container. The admin of the .env keeps working
as the first user until a user of that name is set in the file; from then on the file wins.
"""
import base64
import hashlib
import hmac
import os
import secrets
from typing import Dict, Optional

import yaml

from ..config import settings
from .device_service import device_service

_N, _R, _P = 2 ** 14, 8, 1  # about 16 MB and 50 ms per check


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P)
    return "scrypt${}${}${}${}${}".format(_N, _R, _P, base64.b64encode(salt).decode(), base64.b64encode(digest).decode())


def check_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p))
    except (ValueError, TypeError):
        return False  # a damaged entry fails closed
    return hmac.compare_digest(actual, expected)


def _path() -> str:
    # next to devices.yaml, in the folder mounted into the container (device_service knows the real path)
    return os.path.join(os.path.dirname(device_service.config_path), "users.yaml")


def load_users() -> Dict[str, str]:
    """username -> stored hash. A missing or unreadable file means no file users (not an open door)."""
    try:
        with open(_path(), "r") as f:
            data = yaml.safe_load(f) or {}
        return {str(k): str(v) for k, v in (data.get("users") or {}).items()}
    except (FileNotFoundError, yaml.YAMLError, AttributeError):
        return {}


def _save(users: Dict[str, str]) -> None:
    tmp = f"{_path()}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        yaml.safe_dump({"users": users}, f)
    os.replace(tmp, _path())


def set_password(username: str, password: str) -> None:
    users = load_users()
    users[username] = hash_password(password)
    _save(users)


def remove_user(username: str) -> bool:
    users = load_users()
    if username not in users:
        return False
    del users[username]
    _save(users)
    return True


def verify_login(username: str, password: str) -> bool:
    users = load_users()
    if username in users:
        return check_password(password, users[username])
    if username == settings.admin_username:
        return hmac.compare_digest(password.encode(), settings.admin_password.encode())
    return False


def credential_stamp(username: str) -> Optional[str]:
    """
    A short fingerprint of the user's current credential, or None if the user does not exist.
    It goes inside the session token, so changing a password or removing the user ends the
    sessions that were opened with the old one.
    """
    users = load_users()
    if username in users:
        secret = users[username]
    elif username == settings.admin_username:
        secret = settings.admin_password
    else:
        return None
    return hmac.new(settings.jwt_secret.encode(), secret.encode(), hashlib.sha256).hexdigest()[:16]
