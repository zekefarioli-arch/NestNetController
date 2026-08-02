import subprocess
from unittest.mock import patch, MagicMock

from app.services.firewall import firewall_service
from app.models import Device


def make_device(mac="AA:BB:CC:DD:EE:99"):
    return Device(name="test_device", mac=mac)


def test_block_device_dry_run_never_touches_subprocess():
    with patch("app.services.firewall.subprocess.run") as mock_run:
        result = firewall_service.block_device(make_device())
    mock_run.assert_not_called()
    assert result["success"] is True
    assert result["dry_run"] is True


def test_unblock_device_dry_run():
    result = firewall_service.unblock_device(make_device())
    assert result["success"] is True


def test_block_group_blocks_every_device():
    devices = [make_device("AA:BB:CC:DD:EE:01"), make_device("AA:BB:CC:DD:EE:02")]
    results = firewall_service.block_group(devices, "test_group")
    assert len(results) == 2
    assert all(r["success"] for r in results)


def test_block_command_uses_configured_wan_interface():
    firewall_service.dry_run = False
    firewall_service.wan_interface = "ppp0"
    try:
        with patch("app.services.firewall.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            firewall_service.block_device(make_device("AA:BB:CC:DD:EE:05"))
        called_cmd = mock_run.call_args[0][0]
        assert "-o" in called_cmd
        assert "ppp0" in called_cmd
        assert "DROP" in called_cmd
    finally:
        firewall_service.dry_run = True


def test_block_device_failure_is_reported_not_raised():
    firewall_service.dry_run = False
    try:
        with patch("app.services.firewall.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "iptables", stderr="permission denied"
            )
            result = firewall_service.block_device(make_device())
        assert result["success"] is False
        assert "permission denied" in result["error"]
    finally:
        firewall_service.dry_run = True


def test_sync_allowlist_dry_run_skips_real_commands():
    with patch("app.services.firewall.subprocess.run") as mock_run:
        result = firewall_service.sync_allowlist([make_device()])
    mock_run.assert_not_called()
    assert result["dry_run"] is True


def test_get_blocked_macs_dry_run_returns_empty():
    assert firewall_service.get_blocked_macs() == []
