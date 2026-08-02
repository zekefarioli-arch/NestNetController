import pytest
import yaml
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.services.device_service import device_service
from app.services.firewall import firewall_service
from app.services.logging_service import logging_service

SAMPLE_CONFIG = {
    "groups": {
        "essential": {
            "description": "Critical devices",
            "devices": [
                {"name": "test_phone", "mac": "AA:BB:CC:DD:EE:01", "description": "Test phone"}
            ],
        },
        "security": {
            "description": "Security devices",
            "devices": [{"name": "test_camera", "mac": "AA:BB:CC:DD:EE:02"}],
        },
        "media": {
            "description": "Media devices",
            "devices": [{"name": "test_tv", "mac": "AA:BB:CC:DD:EE:03"}],
        },
        "infrastructure": {
            "description": "Never blocked",
            "protected": True,
            "devices": [{"name": "gateway", "mac": "AA:BB:CC:DD:EE:F1"}],
        },
    },
    "kids": {"description": "Unknown devices"},
}


@pytest.fixture
def devices_yaml(tmp_path):
    path = tmp_path / "devices.yaml"
    path.write_text(yaml.dump(SAMPLE_CONFIG))
    return path


@pytest.fixture(autouse=True)
def reset_device_service(devices_yaml):
    """Cada test apunta a un devices.yaml descartable, nunca al real."""
    original_path = device_service.config_path
    device_service.config_path = str(devices_yaml)
    device_service._groups_cache = None
    yield
    device_service.config_path = original_path
    device_service._groups_cache = None


@pytest.fixture(autouse=True)
def force_dry_run():
    """Nunca dejar que un test toque iptables real, sin importar el .env."""
    original = firewall_service.dry_run
    firewall_service.dry_run = True
    yield
    firewall_service.dry_run = original


@pytest.fixture
def log_file(tmp_path):
    original = logging_service.log_file
    logging_service.log_file = str(tmp_path / "activity.log")
    yield logging_service.log_file
    logging_service.log_file = original


@pytest.fixture
def client(reset_device_service, force_dry_run, log_file):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(client):
    r = client.post(
        "/auth/login",
        json={"username": settings.admin_username, "password": settings.admin_password},
    )
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
