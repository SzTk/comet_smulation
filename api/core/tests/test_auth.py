from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jose import JWTError

from api.core.auth import require_authorized_user

# Minimal FastAPI app exposing one protected endpoint
_app = FastAPI()


@_app.get("/protected")
async def _protected(email: str | None = Depends(require_authorized_user)):
    return {"email": email}


_client = TestClient(_app)

_ALLOWED_EMAIL = "allowed@example.com"
_CLIENT_ID = "test-client.apps.googleusercontent.com"
_VALID_CLAIMS = {"email": _ALLOWED_EMAIL, "email_verified": True}


class TestAuthEnabled:
    @pytest.fixture(autouse=True)
    def _enable_auth(self):
        with patch("api.core.auth.settings") as mock:
            mock.auth_enabled = True
            mock.google_client_id = _CLIENT_ID
            mock.allowed_emails = [_ALLOWED_EMAIL]
            yield mock

    def test_no_token_returns_401(self):
        resp = _client.get("/protected")
        assert resp.status_code == 401
        assert resp.json()["detail"]["error"] == "Unauthorized"

    def test_malformed_bearer_returns_401(self):
        with patch("api.core.auth._decode_google_jwt", new=AsyncMock(side_effect=JWTError)):
            resp = _client.get("/protected", headers={"Authorization": "Bearer bad.token"})
        assert resp.status_code == 401

    def test_valid_bearer_returns_email(self):
        with patch("api.core.auth._decode_google_jwt", new=AsyncMock(return_value=_VALID_CLAIMS)):
            resp = _client.get("/protected", headers={"Authorization": "Bearer fake.token"})
        assert resp.status_code == 200
        assert resp.json()["email"] == _ALLOWED_EMAIL

    def test_valid_ms_token_header_returns_email(self):
        with patch("api.core.auth._decode_google_jwt", new=AsyncMock(return_value=_VALID_CLAIMS)):
            resp = _client.get("/protected", headers={"X-Ms-Token-Google-Id-Token": "fake.token"})
        assert resp.status_code == 200
        assert resp.json()["email"] == _ALLOWED_EMAIL

    def test_bearer_takes_priority_over_ms_header(self):
        with patch(
            "api.core.auth._decode_google_jwt", new=AsyncMock(return_value=_VALID_CLAIMS)
        ) as mock_decode:
            _client.get(
                "/protected",
                headers={
                    "Authorization": "Bearer bearer.token",
                    "X-Ms-Token-Google-Id-Token": "ms.token",
                },
            )
        mock_decode.assert_awaited_once_with("bearer.token")

    def test_unverified_email_returns_401(self):
        claims = {"email": _ALLOWED_EMAIL, "email_verified": False}
        with patch("api.core.auth._decode_google_jwt", new=AsyncMock(return_value=claims)):
            resp = _client.get("/protected", headers={"Authorization": "Bearer fake.token"})
        assert resp.status_code == 401

    def test_disallowed_email_returns_403(self):
        claims = {"email": "attacker@example.com", "email_verified": True}
        with patch("api.core.auth._decode_google_jwt", new=AsyncMock(return_value=claims)):
            resp = _client.get("/protected", headers={"Authorization": "Bearer fake.token"})
        assert resp.status_code == 403
        assert resp.json()["detail"]["error"] == "Forbidden"


class TestAuthDisabled:
    def test_no_token_returns_200_and_email_is_none(self):
        # auth_enabled defaults to False in Settings
        resp = _client.get("/protected")
        assert resp.status_code == 200
        assert resp.json()["email"] is None
