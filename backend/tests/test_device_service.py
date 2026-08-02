import yaml
from app.services.device_service import device_service


def test_load_groups_returns_all_groups():
    groups = device_service.load_groups()
    names = {g.name for g in groups}
    assert names == {"essential", "security", "media", "infrastructure", "kids"}


def test_infrastructure_group_is_protected():
    group = device_service.get_group("infrastructure")
    assert group.protected is True


def test_kids_group_is_auto_detect_and_empty():
    group = device_service.get_group("kids")
    assert group.auto_detect is True
    assert group.devices == []


def test_essential_group_has_expected_device():
    group = device_service.get_group("essential")
    assert len(group.devices) == 1
    assert group.devices[0].mac == "AA:BB:CC:DD:EE:01"


def test_get_group_unknown_returns_none():
    assert device_service.get_group("does_not_exist") is None


def test_get_all_devices_excludes_kids_group():
    devices = device_service.get_all_devices()
    assert len(devices) == 4  # essential + security + media + infrastructure
    assert "AA:BB:CC:DD:EE:01" in {d.mac for d in devices}


def test_is_protected_group():
    assert device_service.is_protected_group("infrastructure") is True
    assert device_service.is_protected_group("essential") is False


def test_reload_configuration_reflects_file_changes(devices_yaml):
    device_service.load_groups()
    original_count = len(device_service.get_group("essential").devices)

    config = yaml.safe_load(devices_yaml.read_text())
    config["groups"]["essential"]["devices"].append(
        {"name": "second_device", "mac": "AA:BB:CC:DD:EE:99"}
    )
    devices_yaml.write_text(yaml.dump(config))

    device_service.reload_configuration()
    assert len(device_service.get_group("essential").devices) == original_count + 1


def test_missing_config_file_returns_empty_list():
    device_service.config_path = "/nonexistent/path/devices.yaml"
    device_service._groups_cache = None
    assert device_service.load_groups() == []
