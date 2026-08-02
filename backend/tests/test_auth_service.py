import pytest
from fastapi import HTTPException

from app.services.auth import authenticate_user, create_access_token, verify_token
from app.config import settings


def test_authenticate_correct_credentials():
    assert authenticate_user(settings.admin_username, settings.admin_password) is True


def test_authenticate_wrong_password():
    assert authenticate_user(settings.admin_username, "wrong-password") is False


def test_authenticate_unknown_user():
    assert authenticate_user("nobody", settings.admin_password) is False


def test_create_and_verify_token_roundtrip():
    token = create_access_token({"sub": "admin"})
    payload = verify_token(token)
    assert payload["sub"] == "admin"


def test_verify_token_rejects_garbage():
    with pytest.raises(HTTPException):
        verify_token("not-a-real-token")
