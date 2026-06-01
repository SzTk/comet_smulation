# Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 4-layer authentication (Azure Easy Auth + Google JWT) to the comet simulation app using a single FastAPI container, following the azure-easy-auth-google-template pattern.

**Architecture:** Azure Easy Auth handles Google login (Layer 1). `EmailAllowlistMiddleware` validates `X-MS-CLIENT-PRINCIPAL-NAME` against an email allowlist (Layer 2). The frontend uses GSI silent sign-in to obtain a Google ID token (Layer 3). `POST /simulate` and `GET /presets` verify the JWT against Google JWKS independently (Layer 4). `GET /simulate/{job_id}/stream` is exempt — the UUID job_id acts as a capability token. `AUTH_ENABLED=false` by default for local dev.

**Tech Stack:** FastAPI, python-jose[cryptography], pydantic-settings, httpx (existing), Google Sign-In (GSI) JS library, Azure Container Apps Easy Auth.

---

### Task 1: Add dependencies and create Settings config

**Files:**
- Modify: `requirements.txt`
- Create: `api/core/__init__.py`
- Create: `api/core/config.py`

- [ ] **Step 1: Update `requirements.txt`**

Add two lines at the end:

```
python-jose[cryptography]>=3.3.0
pydantic-settings>=2.0.0
```

Full file after edit:
```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
numpy>=1.26.0
httpx>=0.27.0
pytest>=8.2.0
pytest-asyncio>=0.23.0
python-jose[cryptography]>=3.3.0
pydantic-settings>=2.0.0
```

- [ ] **Step 2: Create `api/core/__init__.py`** (empty file)

- [ ] **Step 3: Create `api/core/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__")

    auth_enabled: bool = False
    google_client_id: str = ""
    allowed_emails: list[str] = []


settings = Settings()
```

- [ ] **Step 4: Install and verify**

```bash
pip install -r requirements.txt
python -c "from api.core.config import settings; print(settings.auth_enabled, settings.allowed_emails)"
```

Expected output: `False []`

- [ ] **Step 5: Commit**

```bash
git add requirements.txt api/core/__init__.py api/core/config.py
git commit -m "feat: add auth config and pydantic-settings dependency"
```

---

### Task 2: JWT verification dependency (TDD)

**Files:**
- Create: `api/core/tests/__init__.py`
- Create: `api/core/tests/test_auth.py`
- Create: `api/core/auth.py`

- [ ] **Step 1: Create `api/core/tests/__init__.py`** (empty file)

- [ ] **Step 2: Write `api/core/tests/test_auth.py`**

Strategy: patch `_decode_google_jwt` with `AsyncMock` so no real Google network call is made.

```python
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
```

- [ ] **Step 3: Run to verify tests fail**

```bash
pytest api/core/tests/test_auth.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` (auth.py doesn't exist yet).

- [ ] **Step 4: Create `api/core/auth.py`**

```python
import time
from typing import Any, Optional

import httpx
from fastapi import Header, HTTPException
from jose import JWTError, jwt

from api.core.config import settings

_GOOGLE_JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"
_GOOGLE_ISSUER = "https://accounts.google.com"
_JWKS_TTL = 3600

_jwks_cache: dict[str, Any] = {}
_jwks_fetched_at: float = 0.0


async def _fetch_jwks() -> dict[str, Any]:
    global _jwks_cache, _jwks_fetched_at
    async with httpx.AsyncClient() as client:
        resp = await client.get(_GOOGLE_JWKS_URI, timeout=10.0)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_fetched_at = time.monotonic()
    return _jwks_cache


async def _get_jwks() -> dict[str, Any]:
    if _jwks_cache and time.monotonic() - _jwks_fetched_at < _JWKS_TTL:
        return _jwks_cache
    return await _fetch_jwks()


async def _decode_google_jwt(token: str) -> dict[str, Any]:
    """Verify a Google ID token against JWKS, retrying once on key rotation."""
    jwks = await _get_jwks()
    try:
        return jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.google_client_id,
            issuer=_GOOGLE_ISSUER,
        )
    except JWTError:
        global _jwks_fetched_at
        _jwks_fetched_at = 0.0
        jwks = await _fetch_jwks()
        return jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.google_client_id,
            issuer=_GOOGLE_ISSUER,
        )


async def require_authorized_user(
    authorization: Optional[str] = Header(None),
    x_ms_token_google_id_token: Optional[str] = Header(None),
) -> Optional[str]:
    """FastAPI dependency. Returns verified email, or None when auth is disabled."""
    if not settings.auth_enabled:
        return None

    token: Optional[str] = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    elif x_ms_token_google_id_token:
        token = x_ms_token_google_id_token

    if not token:
        raise HTTPException(
            status_code=401,
            detail={"error": "Unauthorized", "message": "Authentication required"},
        )

    try:
        claims = await _decode_google_jwt(token)
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail={"error": "Unauthorized", "message": "Invalid or expired token"},
        )

    if not claims.get("email_verified", False):
        raise HTTPException(
            status_code=401,
            detail={"error": "Unauthorized", "message": "Email not verified"},
        )

    email: str = claims.get("email", "")
    if email not in settings.allowed_emails:
        raise HTTPException(
            status_code=403,
            detail={"error": "Forbidden", "message": "Email not authorized"},
        )

    return email
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest api/core/tests/test_auth.py -v
```

Expected: `8 passed`

- [ ] **Step 6: Commit**

```bash
git add api/core/tests/__init__.py api/core/tests/test_auth.py api/core/auth.py
git commit -m "feat: add JWT verification dependency (require_authorized_user)"
```

---

### Task 3: Email allowlist middleware (TDD)

**Files:**
- Create: `api/core/tests/test_middleware.py`
- Create: `api/core/middleware.py`

- [ ] **Step 1: Write `api/core/tests/test_middleware.py`**

```python
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
```

- [ ] **Step 2: Run to verify tests fail**

```bash
pytest api/core/tests/test_middleware.py -v
```

Expected: `ModuleNotFoundError` (middleware.py doesn't exist yet).

- [ ] **Step 3: Create `api/core/middleware.py`**

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api.core.config import settings


class EmailAllowlistMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.auth_enabled:
            return await call_next(request)

        email = request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME", "")
        if not email or email not in settings.allowed_emails:
            return Response("Forbidden", status_code=403)

        return await call_next(request)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest api/core/tests/test_middleware.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add api/core/tests/test_middleware.py api/core/middleware.py
git commit -m "feat: add EmailAllowlistMiddleware (Layer 2 email allowlist)"
```

---

### Task 4: Wire auth into routes and app

**Files:**
- Modify: `api/routes.py`
- Modify: `main.py`

- [ ] **Step 1: Update `api/routes.py`**

Add to the imports block (after existing imports):

```python
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from api.core.auth import require_authorized_user
```

Note: `APIRouter` and `HTTPException` are already imported — only add `Depends`. The full import block becomes:

```python
import asyncio
import json
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.core.auth import require_authorized_user
from physics.simulation import SimulationParams, run_simulation
```

Change `get_presets`:

```python
@router.get("/presets")
def get_presets(email: Optional[str] = Depends(require_authorized_user)):
    return PRESETS
```

Change `start_simulation`:

```python
@router.post("/simulate")
async def start_simulation(
    req: SimulateRequest,
    email: Optional[str] = Depends(require_authorized_user),
):
```

Leave `GET /health` and `GET /simulate/{job_id}/stream` unchanged.

- [ ] **Step 2: Update `main.py`**

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.core.middleware import EmailAllowlistMiddleware
from api.routes import router

app = FastAPI(title="Comet Simulation")
app.add_middleware(EmailAllowlistMiddleware)
app.include_router(router)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

- [ ] **Step 3: Run the full test suite**

```bash
pytest -v
```

Expected: all tests pass (existing tests + new auth/middleware tests). If existing tests fail because they now hit protected endpoints, check if `auth_enabled` defaults to `False` — it does, so existing tests should pass without modification.

- [ ] **Step 4: Commit**

```bash
git add api/routes.py main.py
git commit -m "feat: wire EmailAllowlistMiddleware and require_authorized_user into app"
```

---

### Task 5: Frontend — GSI silent sign-in

**Files:**
- Create: `static/js/gsi-auth.js`
- Modify: `static/index.html`
- Modify: `static/js/api.js`

- [ ] **Step 1: Create `static/js/gsi-auth.js`**

Replace `YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com` with the real client ID before deploying to Azure. During local dev (`AUTH_ENABLED=false`), the token is never checked by the backend.

```javascript
const GOOGLE_CLIENT_ID = "YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com";

let _idToken = null;
let _tokenExpiry = 0;
const _tokenWaiters = [];

function _onGoogleCredential(response) {
    try {
        const payload = JSON.parse(atob(response.credential.split('.')[1]));
        _tokenExpiry = payload.exp * 1000;
    } catch {
        _tokenExpiry = Date.now() + 3_600_000;
    }
    _idToken = response.credential;
    _tokenWaiters.splice(0).forEach(fn => fn(_idToken));
}

// Called by the GSI library once it has loaded.
window.onGoogleLibraryLoad = function () {
    google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: _onGoogleCredential,
        auto_select: true,
        use_fedcm_for_prompt: true,
    });
    google.accounts.id.prompt();
};

export function clearTokenCache() {
    _idToken = null;
    _tokenExpiry = 0;
}

/**
 * Returns Promise<string|null>.
 * Resolves with cached token if still valid; otherwise waits up to 5s for GSI.
 */
export function getIdToken() {
    if (_idToken && Date.now() < _tokenExpiry - 60_000) {
        return Promise.resolve(_idToken);
    }
    if (typeof google !== "undefined" && google.accounts?.id) {
        google.accounts.id.prompt();
    }
    return new Promise(resolve => {
        let settled = false;
        const timer = setTimeout(() => {
            if (!settled) { settled = true; resolve(null); }
        }, 5_000);
        _tokenWaiters.push(token => {
            if (!settled) { settled = true; clearTimeout(timer); resolve(token); }
        });
    });
}
```

- [ ] **Step 2: Add GSI script tag to `static/index.html`**

Add this line inside `<head>`, immediately before the closing `</head>` tag:

```html
  <script src="https://accounts.google.com/gsi/client" async defer></script>
</head>
```

- [ ] **Step 3: Replace `static/js/api.js`**

```javascript
// static/js/api.js
// Handles POST /simulate and SSE streaming.

import { clearTokenCache, getIdToken } from "./gsi-auth.js";

async function _authHeaders() {
    const token = await getIdToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function startSimulation(payload, onProgress, onResult, onError) {
    const body = JSON.stringify(payload);

    async function _post() {
        return fetch("/simulate", {
            method: "POST",
            headers: { "Content-Type": "application/json", ...(await _authHeaders()) },
            body,
        });
    }

    let resp;
    try {
        resp = await _post();
    } catch (e) {
        onError("サーバーへの接続に失敗しました。");
        return;
    }

    if (resp.status === 401) {
        clearTokenCache();
        try {
            resp = await _post();
        } catch (e) {
            onError("サーバーへの接続に失敗しました。");
            return;
        }
    }

    if (!resp.ok) {
        onError(`サーバーエラー: ${resp.status}`);
        return;
    }

    const { job_id } = await resp.json();

    const es = new EventSource(`/simulate/${job_id}/stream`);

    es.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === "progress") {
            onProgress(msg.percent);
        } else if (msg.type === "result") {
            es.close();
            onResult(msg);
        }
    };

    es.onerror = () => {
        es.close();
        onError("ストリーム接続エラー。");
    };
}

export async function fetchPresets() {
    const resp = await fetch("/presets", { headers: await _authHeaders() });
    return resp.json();
}
```

- [ ] **Step 4: Verify `static/index.html` uses `type="module"` for the entry script**

`index.html` already contains `<script type="module">` that imports `ui.js`. Confirm `ui.js` imports from `api.js`. Since `api.js` now uses `import` statements (ES module), any script that imports from it must also be a module — this is already satisfied.

- [ ] **Step 5: Commit**

```bash
git add static/js/gsi-auth.js static/index.html static/js/api.js
git commit -m "feat: add GSI silent sign-in and auth token injection to frontend"
```

---

### Task 6: Create CLAUDE.md

**Files:**
- Create: `CLAUDE.md`

- [ ] **Step 1: Create `CLAUDE.md`**

```markdown
## 認証
以下のテンプレートのパターンを採用する:
https://github.com/SzTk/azure-easy-auth-google-template
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add CLAUDE.md with auth template reference"
```

---

## Azure デプロイ時の追加作業 (実装スコープ外)

実装完了後、本番デプロイ前に必要な手順:

1. Google Cloud Console で OAuth 2.0 クライアント ID を作成し、リダイレクト URI に `https://<APP_FQDN>/.auth/login/google/callback` を登録
2. `static/js/gsi-auth.js` の `GOOGLE_CLIENT_ID` を実際の値に更新
3. Container App の環境変数を設定: `AUTH_ENABLED=true`, `GOOGLE_CLIENT_ID=<value>`, `ALLOWED_EMAILS=["user@example.com"]`
4. テンプレートの `deploy/enable-auth.sh` を使って Easy Auth を有効化
