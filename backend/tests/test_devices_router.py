from app.config import settings


def test_login_success(client):
    r = client.post(
        "/auth/login",
        json={"username": settings.admin_username, "password": settings.admin_password},
    )
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_login_wrong_password(client):
    r = client.post(
        "/auth/login", json={"username": settings.admin_username, "password": "wrong"}
    )
    assert r.status_code == 401


def test_get_groups_requires_auth(client):
    r = client.get("/devices/groups")
    assert r.status_code in (401, 403)


def test_get_groups_returns_configured_groups(client, auth_headers):
    r = client.get("/devices/groups", headers=auth_headers)
    assert r.status_code == 200
    names = {g["name"] for g in r.json()}
    assert names == {"essential", "security", "media", "infrastructure", "kids"}


def test_toggle_protected_group_is_forbidden(client, auth_headers):
    r = client.post("/devices/groups/infrastructure/toggle", headers=auth_headers)
    assert r.status_code == 403


def test_toggle_unknown_group_404(client, auth_headers):
    r = client.post("/devices/groups/doesnotexist/toggle", headers=auth_headers)
    assert r.status_code == 404


def test_disable_then_enable_media_group(client, auth_headers):
    r = client.post("/devices/groups/media/disable", headers=auth_headers)
    assert r.status_code == 200 and r.json()["success"] is True

    r = client.post("/devices/groups/media/enable", headers=auth_headers)
    assert r.status_code == 200 and r.json()["success"] is True


def test_quick_action_only_essential(client, auth_headers):
    r = client.post(
        "/devices/quick-action", json={"action": "only_essential"}, headers=auth_headers
    )
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_quick_action_unknown_action_400(client, auth_headers):
    r = client.post(
        "/devices/quick-action", json={"action": "not_a_real_action"}, headers=auth_headers
    )
    assert r.status_code == 400


def test_reload_endpoint_reports_group_count(client, auth_headers):
    r = client.post("/devices/reload", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["groups_count"] == 5


def test_logs_endpoint_records_actions(client, auth_headers):
    client.post("/devices/groups/media/disable", headers=auth_headers)
    r = client.get("/logs/recent", headers=auth_headers)
    assert r.status_code == 200
    assert any(log["action"] == "disable_group" for log in r.json())
