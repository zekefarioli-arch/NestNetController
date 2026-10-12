"""Panel users: hashed passwords in users.yaml, the .env admin as a fallback, sessions tied to the credential."""
import os
import stat

import pytest

from app.config import settings
from app.services import users


def login(client, name, password):
    return client.post("/auth/login", json={"username": name, "password": password})


def headers(client, name, password):
    return {"Authorization": f"Bearer {login(client, name, password).json()['access_token']}"}


def test_env_admin_works_until_the_file_has_an_admin(client):
    assert login(client, settings.admin_username, settings.admin_password).status_code == 200
    users.set_password(settings.admin_username, "a-new-long-password")
    assert login(client, settings.admin_username, settings.admin_password).status_code == 401  # old one is dead
    assert login(client, settings.admin_username, "a-new-long-password").status_code == 200


def test_a_second_user_can_sign_in_and_is_named_in_the_activity(client):
    users.set_password("vivi", "vivi-long-password")
    h = headers(client, "vivi", "vivi-long-password")
    assert client.post("/devices/groups/media/enable", headers=h).status_code == 200
    log = client.get("/logs/recent", headers=h).json()
    assert any(entry["user"] == "vivi" and entry["action"] == "enable_group" for entry in log)


def test_wrong_password_and_unknown_user_are_refused(client):
    users.set_password("vivi", "vivi-long-password")
    assert login(client, "vivi", "wrong").status_code == 401
    assert login(client, "nobody", "vivi-long-password").status_code == 401


def test_passwords_are_stored_hashed_with_a_private_file():
    users.set_password("vivi", "vivi-long-password")
    path = users._path()
    assert "vivi-long-password" not in open(path).read()
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_changing_a_password_ends_the_old_sessions(client):
    users.set_password("vivi", "first-long-password")
    old = headers(client, "vivi", "first-long-password")
    assert client.get("/devices/groups", headers=old).status_code == 200
    users.set_password("vivi", "second-long-password")
    assert client.get("/devices/groups", headers=old).status_code == 401
    assert client.get("/devices/groups", headers=headers(client, "vivi", "second-long-password")).status_code == 200


def test_removing_a_user_ends_the_sessions(client):
    users.set_password("vivi", "vivi-long-password")
    h = headers(client, "vivi", "vivi-long-password")
    assert users.remove_user("vivi") is True
    assert client.get("/devices/groups", headers=h).status_code == 401
    assert login(client, "vivi", "vivi-long-password").status_code == 401


def test_a_token_without_the_credential_stamp_is_refused(client):
    from app.services.auth import create_access_token
    token = create_access_token({"sub": settings.admin_username})
    assert client.get("/devices/groups", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_a_damaged_entry_fails_closed():
    assert users.check_password("x", "scrypt$broken") is False
    assert users.check_password("x", "plain-text") is False


def test_unreadable_file_means_no_file_users():
    with open(users._path(), "w") as f:
        f.write("users: [not, a, mapping")
    assert users.load_users() == {}


def test_cli_asks_twice_and_checks_the_length(monkeypatch, capsys):
    from app import users as cli
    answers = iter(["short"])
    monkeypatch.setattr("getpass.getpass", lambda prompt="": next(answers))
    assert cli.main(["set", "vivi"]) == 1 and "too short" in capsys.readouterr().out
    answers = iter(["a-long-enough-password", "a-different-one-here"])
    assert cli.main(["set", "vivi"]) == 1 and "different" in capsys.readouterr().out
    assert "vivi" not in users.load_users()
    answers = iter(["a-long-enough-password", "a-long-enough-password"])
    assert cli.main(["set", "vivi"]) == 0 and "vivi" in users.load_users()
