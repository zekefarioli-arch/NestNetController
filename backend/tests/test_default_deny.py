"""Default-deny: what sync_allowlist leaves in iptables, checked against a fake iptables."""
import subprocess
from unittest.mock import patch

import pytest

from app.models import Device
from app.services.device_service import device_service
from app.services.firewall import firewall_service

RETURN_RULE = "-A DOCKER-USER -i ppp0 -o enp7s0f0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT"
BROAD_RULE = "-A DOCKER-USER -i enp7s0f0 -o ppp0 -j ACCEPT"
PANEL_RULE = "-A DOCKER-USER ! -i ppp0 -p tcp -m tcp --dport 3002 -j ACCEPT"


class FakeIptables:
    """Just enough of iptables: -S, -A, -I, -D and -P on named chains, with a log of commands."""

    def __init__(self, forward=(), docker_user=(RETURN_RULE, BROAD_RULE, PANEL_RULE), policy="DROP"):
        self.chains = {
            "FORWARD": ["-A FORWARD -j DOCKER-USER", *forward],
            "DOCKER-USER": list(docker_user),
        }
        self.policy = policy
        self.log = []

    def run(self, command, **kwargs):
        args = command[1:]
        self.log.append(" ".join(args))
        op = args[0]
        if op == "-S":
            if args[1] not in self.chains:
                return subprocess.CompletedProcess(command, 1, "", "No chain")
            out = [f"-P {args[1]} {self.policy}"] if args[1] == "FORWARD" else ["-N " + args[1]]
            return subprocess.CompletedProcess(command, 0, "\n".join(out + self.chains[args[1]]) + "\n", "")
        if op == "-P":
            self.policy = args[2]
        else:
            chain, rest = args[1], args[2:]
            if op == "-I" and rest and rest[0].isdigit():
                rest = rest[1:]
            rule = f"-A {chain} " + " ".join(rest).replace("--mac-source ", "--mac-source ")
            for token in rest:
                if token.count(":") == 5:
                    rule = rule.replace(token, token.lower())
            if op == "-A":
                self.chains[chain].append(rule)
            elif op == "-I":
                self.chains[chain].insert(0, rule)
            elif op == "-D":
                if rule not in self.chains[chain]:
                    return subprocess.CompletedProcess(command, 1, "", "Bad rule")
                self.chains[chain].remove(rule)
        return subprocess.CompletedProcess(command, 0, "", "")


def allow_rule(mac):
    return f"-A FORWARD -o ppp0 -m mac --mac-source {mac.lower()} -m comment --comment nestnet-allow -j ACCEPT"


@pytest.fixture
def live():
    """Firewall in non-dry-run mode with a fake iptables."""
    saved = (firewall_service.dry_run, firewall_service.wan_interface, firewall_service.allow_interfaces)
    firewall_service.dry_run = False
    firewall_service.wan_interface = "ppp0"
    firewall_service.allow_interfaces = []
    yield
    firewall_service.dry_run, firewall_service.wan_interface, firewall_service.allow_interfaces = saved


def sync(fake, macs):
    devices = [Device(name=f"d{i}", mac=m) for i, m in enumerate(macs)]
    with patch("app.services.firewall.subprocess.run", side_effect=fake.run):
        return firewall_service.sync_allowlist(devices)


def test_broad_rule_is_removed_and_only_listed_macs_are_accepted(live):
    fake = FakeIptables(forward=[allow_rule("AA:BB:CC:DD:EE:99")])  # a stale one
    result = sync(fake, ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"])
    assert result["success"] is True
    assert BROAD_RULE not in fake.chains["DOCKER-USER"]
    assert RETURN_RULE in fake.chains["DOCKER-USER"] and PANEL_RULE in fake.chains["DOCKER-USER"]
    accepted = [r for r in fake.chains["FORWARD"] if "nestnet-allow" in r]
    assert sorted(accepted) == sorted([allow_rule("AA:BB:CC:DD:EE:01"), allow_rule("AA:BB:CC:DD:EE:02")])
    assert fake.policy == "DROP"


def test_broad_rule_goes_last_so_nobody_is_cut_during_the_sync(live):
    fake = FakeIptables()
    sync(fake, ["AA:BB:CC:DD:EE:01"])
    adds = [i for i, c in enumerate(fake.log) if c.startswith("-A FORWARD")]
    removal = next(i for i, c in enumerate(fake.log) if c.startswith("-D DOCKER-USER"))
    assert adds and max(adds) < removal


def test_broad_rule_is_removed_whatever_the_lan_interface_is(live):
    # the router's .env names enp5s0 (a dead card) while the traffic flows through enp7s0f0
    assert firewall_service.lan_interface != "enp7s0f0"
    fake = FakeIptables(docker_user=[RETURN_RULE, BROAD_RULE])
    sync(fake, [])
    assert fake.chains["DOCKER-USER"] == [RETURN_RULE]


def test_broad_rule_in_forward_chain_is_removed_too(live):
    fake = FakeIptables(forward=["-A FORWARD -i enp7s0f0 -o ppp0 -j ACCEPT"])
    sync(fake, [])
    assert "-A FORWARD -i enp7s0f0 -o ppp0 -j ACCEPT" not in fake.chains["FORWARD"]


def test_sync_is_idempotent(live):
    fake = FakeIptables()
    sync(fake, ["AA:BB:CC:DD:EE:01"])
    before = {k: list(v) for k, v in fake.chains.items()}
    fake.log.clear()
    sync(fake, ["AA:BB:CC:DD:EE:01"])
    assert fake.chains == before
    assert not [c for c in fake.log if c.split()[0] in ("-A", "-I", "-D")]


def test_policy_is_set_to_drop_when_it_was_accept(live):
    fake = FakeIptables(policy="ACCEPT")
    sync(fake, [])
    assert fake.policy == "DROP"


def test_return_traffic_rule_is_added_when_missing(live):
    fake = FakeIptables(docker_user=[BROAD_RULE])
    sync(fake, [])
    assert any("ESTABLISHED" in r for r in fake.chains["DOCKER-USER"])


def test_allowed_interface_is_accepted_and_survives_the_broad_rule_cleanup(live):
    firewall_service.allow_interfaces = ["docker0"]
    fake = FakeIptables(docker_user=[RETURN_RULE, "-A DOCKER-USER -i docker0 -o ppp0 -j ACCEPT"])
    sync(fake, [])
    assert "-A FORWARD -i docker0 -o ppp0 -m comment --comment nestnet-allow-if -j ACCEPT" in fake.chains["FORWARD"]
    assert "-A DOCKER-USER -i docker0 -o ppp0 -j ACCEPT" in fake.chains["DOCKER-USER"]


def test_removed_interface_rule_is_cleaned_up(live):
    stale = "-A FORWARD -i br-old -o ppp0 -m comment --comment nestnet-allow-if -j ACCEPT"
    fake = FakeIptables(forward=[stale])
    sync(fake, [])
    assert stale not in fake.chains["FORWARD"]


# --- which devices are allowed: the groups ---

def test_by_default_only_protected_and_always_on_groups_are_allowed():
    macs = {d.mac for d in device_service.get_allowed_devices()}
    assert macs == {"AA:BB:CC:DD:EE:F1"}  # infrastructure; the sample config has no always_on group


def test_always_on_group_is_allowed_without_switching_it_on():
    groups = device_service.load_groups()
    security = next(g for g in groups if g.name == "security")
    security.always_on = True
    device_service.save_groups(groups)
    macs = {d.mac for d in device_service.get_allowed_devices()}
    assert macs == {"AA:BB:CC:DD:EE:F1", "AA:BB:CC:DD:EE:02"}


def test_switching_a_group_on_and_off_is_remembered():
    device_service.set_group_enabled("media", True)
    assert "AA:BB:CC:DD:EE:03" in {d.mac for d in device_service.get_allowed_devices()}
    device_service.set_group_enabled("media", False)
    assert "AA:BB:CC:DD:EE:03" not in {d.mac for d in device_service.get_allowed_devices()}


def test_unreadable_state_fails_closed():
    with open(device_service._state_path(), "w") as f:
        f.write("{not json")
    assert {d.mac for d in device_service.get_allowed_devices()} == {"AA:BB:CC:DD:EE:F1"}


def test_groups_endpoint_shows_unlisted_groups_as_blocked_until_switched_on(client, auth_headers):
    states = {g["name"]: g["enabled"] for g in client.get("/devices/groups", headers=auth_headers).json()}
    assert states["infrastructure"] is True
    assert states["essential"] is False and states["media"] is False
    client.post("/devices/groups/media/enable", headers=auth_headers)
    states = {g["name"]: g["enabled"] for g in client.get("/devices/groups", headers=auth_headers).json()}
    assert states["media"] is True
    client.post("/devices/groups/media/disable", headers=auth_headers)
    states = {g["name"]: g["enabled"] for g in client.get("/devices/groups", headers=auth_headers).json()}
    assert states["media"] is False


def test_toggle_flips_a_blocked_group_on(client, auth_headers):
    r = client.post("/devices/groups/essential/toggle", headers=auth_headers)
    assert r.json()["new_state"] == "enabled"
    r = client.post("/devices/groups/essential/toggle", headers=auth_headers)
    assert r.json()["new_state"] == "disabled"


def test_quick_action_only_essential_leaves_only_essential_on(client, auth_headers):
    client.post("/devices/groups/media/enable", headers=auth_headers)
    client.post("/devices/quick-action", json={"action": "only_essential"}, headers=auth_headers)
    states = {g["name"]: g["enabled"] for g in client.get("/devices/groups", headers=auth_headers).json()}
    assert states["essential"] is True and states["media"] is False


# --- always-on groups cannot be switched off, by any route ---

@pytest.fixture
def locked_groups():
    """essential and security always on, as on the router; media stays switchable."""
    groups = device_service.load_groups()
    for g in groups:
        if g.name in ("essential", "security"):
            g.always_on = True
    device_service.save_groups(groups)


def states(client, auth_headers):
    return {g["name"]: g["enabled"] for g in client.get("/devices/groups", headers=auth_headers).json()}


@pytest.mark.parametrize("group", ["essential", "security", "infrastructure"])
@pytest.mark.parametrize("route", ["toggle", "disable"])
def test_always_on_groups_refuse_to_be_switched_off(client, auth_headers, locked_groups, group, route):
    r = client.post(f"/devices/groups/{group}/{route}", headers=auth_headers)
    assert r.status_code == 403
    assert "always on" in r.json()["detail"]
    assert states(client, auth_headers)[group] is True
    assert group not in device_service.get_enabled_groups()
    assert {"AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02", "AA:BB:CC:DD:EE:F1"} <= {d.mac for d in device_service.get_allowed_devices()}


@pytest.mark.parametrize("action", ["only_essential", "only_essential_security", "enable_all"])
def test_scenes_never_switch_off_an_always_on_group(client, auth_headers, locked_groups, action):
    client.post("/devices/groups/media/enable", headers=auth_headers)
    r = client.post("/devices/quick-action", json={"action": action}, headers=auth_headers)
    assert r.status_code == 200
    s = states(client, auth_headers)
    assert s["essential"] is True and s["security"] is True and s["infrastructure"] is True
    assert s["media"] is (action == "enable_all")


def test_a_leftover_block_rule_does_not_show_an_always_on_group_as_off(client, auth_headers, locked_groups):
    with patch("app.routers.devices.firewall_service.get_blocked_macs", return_value=["AA:BB:CC:DD:EE:02"]):
        assert states(client, auth_headers)["security"] is True


def test_enabling_an_always_on_group_is_harmless(client, auth_headers, locked_groups):
    r = client.post("/devices/groups/security/enable", headers=auth_headers)
    assert r.status_code == 200 and r.json()["success"] is True


# --- open mode: "Everything on" trusts the Wi-Fi password (phones randomise their MAC) ---

OPEN_RULE = "-A FORWARD -o ppp0 -m comment --comment nestnet-open -j ACCEPT"


def test_open_mode_adds_one_accept_all_rule_and_closing_removes_it(live):
    fake = FakeIptables(forward=[allow_rule("AA:BB:CC:DD:EE:F1")])
    with patch("app.services.firewall.subprocess.run", side_effect=fake.run):
        firewall_service.sync_allowlist([Device(name="a", mac="AA:BB:CC:DD:EE:F1")], open_mode=True)
        firewall_service.sync_allowlist([Device(name="a", mac="AA:BB:CC:DD:EE:F1")], open_mode=True)
        assert fake.chains["FORWARD"].count(OPEN_RULE) == 1
        firewall_service.sync_allowlist([Device(name="a", mac="AA:BB:CC:DD:EE:F1")], open_mode=False)
    assert OPEN_RULE not in fake.chains["FORWARD"]
    assert allow_rule("AA:BB:CC:DD:EE:F1") in fake.chains["FORWARD"]
    assert fake.policy == "DROP"


def test_open_mode_is_off_by_default_and_switching_a_group_off_ends_it():
    assert device_service.is_open_mode() is False
    device_service.set_group_enabled("media", True)
    device_service.set_open_mode(True)
    assert device_service.is_open_mode() is True and "media" in device_service.get_enabled_groups()
    device_service.set_group_enabled("media", False)
    assert device_service.is_open_mode() is False


def test_unreadable_state_is_not_open_mode():
    with open(device_service._state_path(), "w") as f:
        f.write("{not json")
    assert device_service.is_open_mode() is False


def test_enable_all_opens_and_any_other_scene_closes(client, auth_headers):
    client.post("/devices/quick-action", json={"action": "enable_all"}, headers=auth_headers)
    assert device_service.is_open_mode() is True
    client.post("/devices/quick-action", json={"action": "only_essential_security"}, headers=auth_headers)
    assert device_service.is_open_mode() is False
