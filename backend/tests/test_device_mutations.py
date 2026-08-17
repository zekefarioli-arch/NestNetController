import os
import yaml
from app.services.device_service import device_service
from app.models import Device


# --- Service-level tests ---

def test_add_group_success():
    group = device_service.add_group("guests", "Visiting devices", auto_detect=False)
    assert group.name == "guests"
    assert group.protected is False
    assert device_service.get_group("guests") is not None


def test_add_group_duplicate_name_rejected():
    device_service.add_group("guests", None, False)
    try:
        device_service.add_group("Guests", None, False)  # case-insensitive
        assert False, "should have raised ValueError"
    except ValueError:
        pass


def test_add_group_reserved_kids_name_rejected():
    try:
        device_service.add_group("kids", None, False)
        assert False, "should have raised ValueError"
    except ValueError:
        pass


def test_delete_group_success():
    device_service.add_group("temp_group", None, False)
    device_service.delete_group("temp_group")
    assert device_service.get_group("temp_group") is None


def test_delete_protected_group_rejected():
    try:
        device_service.delete_group("infrastructure")
        assert False, "should have raised PermissionError"
    except PermissionError:
        pass


def test_delete_group_with_devices_rejected():
    try:
        device_service.delete_group("essential")
        assert False, "should have raised ValueError"
    except ValueError:
        pass


def test_delete_nonexistent_group_raises_lookup_error():
    try:
        device_service.delete_group("nope")
        assert False, "should have raised LookupError"
    except LookupError:
        pass


def test_add_device_success():
    device = Device(name="new_phone", mac="aa:bb:cc:dd:ee:77")
    result = device_service.add_device("media", device)
    assert result.mac == "AA:BB:CC:DD:EE:77"  # normalized to uppercase
    group = device_service.get_group("media")
    assert any(d.mac == "AA:BB:CC:DD:EE:77" for d in group.devices)


def test_add_device_invalid_mac_rejected():
    device = Device(name="bad", mac="not-a-mac")
    try:
        device_service.add_device("media", device)
        assert False, "should have raised ValueError"
    except ValueError:
        pass


def test_add_device_duplicate_mac_rejected():
    device = Device(name="dup", mac="AA:BB:CC:DD:EE:01")  # already in essential fixture
    try:
        device_service.add_device("media", device)
        assert False, "should have raised ValueError"
    except ValueError:
        pass


def test_add_device_to_auto_detect_group_rejected():
    device = Device(name="x", mac="AA:BB:CC:DD:EE:88")
    try:
        device_service.add_device("kids", device)
        assert False, "should have raised ValueError"
    except ValueError:
        pass


def test_add_device_to_unknown_group_raises_lookup_error():
    device = Device(name="x", mac="AA:BB:CC:DD:EE:88")
    try:
        device_service.add_device("nope", device)
        assert False, "should have raised LookupError"
    except LookupError:
        pass


def test_delete_device_success():
    device_service.delete_device("essential", "AA:BB:CC:DD:EE:01")
    group = device_service.get_group("essential")
    assert group.devices == []


def test_delete_nonexistent_device_raises_lookup_error():
    try:
        device_service.delete_device("essential", "AA:BB:CC:DD:EE:99")
        assert False, "should have raised LookupError"
    except LookupError:
        pass


def test_save_groups_creates_backup(devices_yaml):
    device_service.add_group("another_group", None, False)
    backup_dir = os.path.join(os.path.dirname(str(devices_yaml)), ".backups")
    assert os.path.isdir(backup_dir)
    assert len(os.listdir(backup_dir)) >= 1


def test_restore_latest_backup(devices_yaml):
    device_service.add_group("will_be_undone", None, False)
    assert device_service.get_group("will_be_undone") is not None

    device_service.restore_latest_backup()
    device_service.reload_configuration()
    assert device_service.get_group("will_be_undone") is None


def test_restore_with_no_backups_raises_lookup_error(tmp_path):
    device_service.config_path = str(tmp_path / "isolated_devices.yaml")
    device_service._groups_cache = None
    with open(device_service.config_path, "w") as f:
        yaml.dump({"groups": {}}, f)

    try:
        device_service.restore_latest_backup()
        assert False, "should have raised LookupError"
    except LookupError:
        pass


# --- API-level (router) tests ---

def test_create_group_via_api(client, auth_headers):
    r = client.post("/devices/groups", json={"name": "guests", "description": "test"}, headers=auth_headers)
    assert r.status_code == 201
    assert r.json()["name"] == "guests"


def test_create_duplicate_group_via_api_400(client, auth_headers):
    client.post("/devices/groups", json={"name": "guests"}, headers=auth_headers)
    r = client.post("/devices/groups", json={"name": "guests"}, headers=auth_headers)
    assert r.status_code == 400


def test_add_device_via_api(client, auth_headers):
    r = client.post(
        "/devices/groups/media/devices",
        json={"name": "new_tv", "mac": "AA:BB:CC:DD:EE:44"},
        headers=auth_headers,
    )
    assert r.status_code == 201
    assert r.json()["mac"] == "AA:BB:CC:DD:EE:44"


def test_add_device_invalid_mac_via_api_400(client, auth_headers):
    r = client.post(
        "/devices/groups/media/devices",
        json={"name": "bad", "mac": "nope"},
        headers=auth_headers,
    )
    assert r.status_code == 400


def test_delete_device_via_api(client, auth_headers):
    client.post(
        "/devices/groups/media/devices",
        json={"name": "temp", "mac": "AA:BB:CC:DD:EE:55"},
        headers=auth_headers,
    )
    r = client.delete("/devices/groups/media/devices/AA:BB:CC:DD:EE:55", headers=auth_headers)
    assert r.status_code == 200


def test_delete_protected_group_via_api_403(client, auth_headers):
    r = client.delete("/devices/groups/infrastructure", headers=auth_headers)
    assert r.status_code == 403


def test_restore_via_api(client, auth_headers):
    client.post("/devices/groups", json={"name": "temp_for_restore"}, headers=auth_headers)
    r = client.post("/devices/restore", headers=auth_headers)
    assert r.status_code == 200
