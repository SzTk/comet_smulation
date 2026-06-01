from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.core.middleware import EmailAllowlistMiddleware

_ALLOWED_EMAIL = "user@example.com"


def _make_client() -> TestClient:
    app = FastAPI()
    app.add_middleware(EmailAllowlistMiddleware)

    @app.get("/")
    def index():
        return {"ok": True}

    return TestClient(app)


@pytest.fixture(autouse=True)
def _enable_auth():
    with patch("api.core.middleware.settings") as mock:
        mock.auth_enabled = True
        mock.allowed_emails = [_ALLOWED_EMAIL]
        yield mock


def test_allowed_email_passes():
    resp = _make_client().get("/", headers={"X-MS-CLIENT-PRINCIPAL-NAME": _ALLOWED_EMAIL})
    assert resp.status_code == 200


def test_missing_header_returns_403():
    resp = _make_client().get("/")
    assert resp.status_code == 403


def test_disallowed_email_returns_403():
    resp = _make_client().get(
        "/", headers={"X-MS-CLIENT-PRINCIPAL-NAME": "attacker@example.com"}
    )
    assert resp.status_code == 403


def test_auth_disabled_bypasses_allowlist(_enable_auth):
    _enable_auth.auth_enabled = False
    resp = _make_client().get("/")
    assert resp.status_code == 200
