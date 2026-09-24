"""authentication is tested against a local provider stub and a disposable database."""

import json
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from ofc.api import create_app
from ofc.auth_provider import AuthSettings, SupabaseAuth
from ofc.auth_service import digest
from ofc.persistence.models import (
    AuthIdentityRow,
    AuthSessionRow,
    PlayerRow,
)
from ofc.persistence.sqlalchemy import SQLAlchemyRepository
from ofc.schema import upgrade


class FakeProvider:
    def __init__(self):
        self.user_id = str(uuid4())
        self.other_id = str(uuid4())
        self.confirmed = True
        self.confirmation_required = False
        self.calls = []
        self.refreshes = 0

    def respond(self, request):
        body = json.loads(request.content) if request.content else {}
        self.calls.append((request.method, request.url.path, body))
        path = request.url.path.removeprefix("/auth/v1")
        if path == "/signup":
            if self.confirmation_required:
                return httpx.Response(200, json={"id": self.user_id})
            return httpx.Response(200, json={
                "access_token": "access", "refresh_token": "refresh", "expires_in": 3600
            })
        if path == "/token":
            if (
                body.get("password") == "incorrect"
                or body.get("auth_code") == "invalid"
            ):
                return httpx.Response(400, json={"error_code": "invalid_credentials"})
            self.refreshes += request.url.params.get("grant_type") == "refresh_token"
            return httpx.Response(
                200,
                json={
                    "access_token": "access-other"
                    if body.get("email") == "other@example.com"
                    else "access",
                    "refresh_token": "refresh",
                    "expires_in": 3600,
                },
            )
        if path == "/user":
            subject = (
                self.other_id
                if request.headers.get("Authorization") == "Bearer access-other"
                else self.user_id
            )
            return httpx.Response(
                200,
                json={
                    "id": subject,
                    "email": "same@example.com",
                    "email_confirmed_at": "2026-01-01" if self.confirmed else None,
                    "user_metadata": {"name": "Alice"},
                    "identities": [{"provider": "email"}],
                },
            )
        if path == "/logout":
            return httpx.Response(204)
        return httpx.Response(200, json={})


@pytest.fixture
def auth(tmp_path):
    url = f"sqlite:///{tmp_path / 'auth.sqlite3'}"
    upgrade(url)
    repo = SQLAlchemyRepository(url)
    settings = AuthSettings(
        "https://auth.example.com",
        "publishable",
        Fernet.generate_key().decode(),
        "http://testserver",
    )
    fake = FakeProvider()
    provider = SupabaseAuth(
        settings, httpx.Client(transport=httpx.MockTransport(fake.respond))
    )
    app = create_app(repository=repo, auth_provider=provider)
    with TestClient(
        app, headers={"Origin": settings.origin, "X-OFC-Request": "1"}
    ) as client:
        yield client, repo, fake, app.state.auth
    provider.close()
    repo.close()


def login(client, email="alice@example.com"):
    response = client.post(
        "/auth/login", json={"email": email, "password": "correct-password"}
    )
    assert response.status_code == 200, response.text
    return response


def test_cookie_login_stable_identity_and_no_browser_tokens(auth):
    client, repo, _, _ = auth
    response = login(client)
    player = response.json()["player_id"]
    assert response.json()["providers"] == ["email"]
    assert "token" not in response.json()
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    assert response.headers["cache-control"] == "no-store"
    token = client.cookies["ofc_session"]
    with repo.transaction() as u:
        row = u.session.get(AuthSessionRow, digest(token))
        assert token not in row.provider_tokens
        assert "refresh" not in row.provider_tokens
        assert row.token_hash != token
        assert u.session.get(PlayerRow, player).token_hash is None
    assert client.get("/auth/session").json()["player_id"] == player
    assert client.post("/games", json={"name": "friends"}).status_code == 201
    client.post("/auth/logout")
    assert client.get("/auth/session").status_code == 401
    assert login(client).json()["player_id"] == player
    with repo.transaction() as u:
        assert u.session.scalar(select(func.count()).select_from(AuthIdentityRow)) == 1


def test_same_email_does_not_merge_distinct_provider_subjects(auth):
    client, _, _, _ = auth
    first = login(client).json()["player_id"]
    second = login(client, "other@example.com").json()["player_id"]
    assert first != second


def test_invalid_credentials_unverified_accounts_and_legacy_keys_rejected(auth):
    client, _, fake, _ = auth
    response = client.post(
        "/auth/login", json={"email": "a@example.com", "password": "incorrect"}
    )
    assert response.status_code == 401
    assert "incorrect" not in response.text
    fake.confirmed = False
    response = client.post(
        "/auth/login", json={"email": "a@example.com", "password": "correct"}
    )
    assert response.status_code == 401
    assert "ofc_session" not in client.cookies
    assert client.post("/players", json={"name": "guest"}).status_code == 410
    assert (
        client.post(
            "/games", json={"name": "x"}, headers={"Authorization": "Bearer old-key"}
        ).status_code
        == 401
    )


def test_csrf_checks_login_and_authenticated_game_writes(auth):
    client, _, _, _ = auth
    data = {"email": "a@example.com", "password": "correct"}
    assert (
        client.post(
            "/auth/login", json=data, headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert (
        client.post("/auth/login", json=data, headers={"X-OFC-Request": ""}).status_code
        == 403
    )
    login(client)
    assert (
        client.post(
            "/games", json={"name": "x"}, headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )


def test_signup_signs_in_immediately_without_email_flow(auth):
    client, _, fake, _ = auth
    response = client.post("/auth/signup", json={
        "email": "alice@example.com", "password": "correct-password", "name": "Alice"
    })
    assert response.status_code == 200
    player = response.json()["player_id"]
    assert "ofc_session" in client.cookies
    assert "ofc_auth_flow" not in client.cookies
    assert "access_token" not in response.text
    assert client.get("/auth/session").json()["player_id"] == player
    body = next(body for _, path, body in fake.calls if path == "/auth/v1/signup")
    assert "code_challenge" not in body
    assert client.post("/auth/logout").status_code == 200
    assert login(client).json()["player_id"] == player


def test_signup_with_confirmation_enabled_reports_configuration_error(auth):
    client, _, fake, _ = auth
    fake.confirmation_required = True
    response = client.post("/auth/signup", json={
        "email": "alice@example.com", "password": "correct-password", "name": "Alice"
    })
    assert response.status_code == 503
    assert "ofc_session" not in client.cookies
    assert "contact the administrator" in response.json()["detail"]


def test_email_delivery_endpoints_are_removed(auth):
    client, _, _, _ = auth
    assert client.post("/auth/recover", json={"email": "a@example.com"}).status_code == 404
    assert client.get("/auth/callback?code=valid").status_code == 404


def test_password_change_revokes_sessions(auth):
    client, _, fake, _ = auth
    login(client)
    old_token = client.cookies["ofc_session"]
    assert (
        client.post(
            "/auth/password", json={"password": "new-secure-password"}
        ).status_code
        == 200
    )
    assert client.get("/auth/session").status_code == 401
    client.cookies.set("ofc_session", old_token)
    assert client.get("/auth/session").status_code == 401
    assert any(
        path == "/auth/v1/user" and body.get("password") == "new-secure-password"
        for _, path, body in fake.calls
    )


def test_expired_sessions_and_flow_replay_are_rejected(auth):
    client, _, _, service = auth
    login(client)
    now = service.clock()
    service.clock = lambda: now + 8 * 24 * 3600
    assert client.get("/auth/session").status_code == 401


def test_refresh_is_serialized_and_preserves_player(auth):
    client, _, fake, service = auth
    player = login(client).json()["player_id"]
    token = client.cookies["ofc_session"]
    now = service.clock()
    service.clock = lambda: now + 3600
    with ThreadPoolExecutor(max_workers=2) as pool:
        profiles = list(pool.map(lambda _: service.session(token)[0], range(2)))
    assert all(p["player_id"] == player for p in profiles)
    assert fake.refreshes == 1


def test_concurrent_first_logins_create_one_player(auth):
    _, repo, _, service = auth
    tokens = {"access_token": "access", "refresh_token": "refresh", "expires_in": 3600}
    with ThreadPoolExecutor(max_workers=2) as pool:
        profiles = list(pool.map(lambda _: service.login(tokens)[1], range(2)))
    assert profiles[0]["player_id"] == profiles[1]["player_id"]
    with repo.transaction() as u:
        assert u.session.scalar(select(func.count()).select_from(PlayerRow)) == 1


def test_signup_and_password_validation_do_not_echo_password(auth):
    client, _, fake, _ = auth
    response = client.post(
        "/auth/signup",
        json={"name": "Alice", "email": "a@example.com", "password": "short-secret"},
    )
    assert response.status_code == 200
    body = next(body for _, path, body in fake.calls if path == "/auth/v1/signup")
    assert "code_challenge" not in body
    assert "short-secret" not in response.text
    response = client.post("/auth/password", json={"password": "secret"})
    assert response.status_code == 422
    assert "secret" not in response.text


def test_google_endpoint_is_not_available(auth):
    client, _, _, _ = auth
    assert client.post("/auth/google", json={}).status_code == 404


def test_websocket_uses_cookie_and_rejects_other_origins(auth):
    from starlette.websockets import WebSocketDisconnect

    client, _, _, _ = auth
    login(client)
    game = client.post("/games", json={"name": "socket"}).json()["game_id"]
    with client.websocket_connect(f"/games/{game}/events") as ws:
        assert ws.receive_json()["type"] == "snapshot"
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect(
            f"/games/{game}/events", headers={"Origin": "https://evil.example"}
        ) as ws,
    ):
        ws.receive_json()


def test_session_cookie_is_secure_on_https(auth):
    from dataclasses import replace

    client, _, _, service = auth
    service.settings = replace(service.settings, origin="https://example.com")
    response = client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "correct-password"},
        headers={"Origin": "https://example.com"},
    )
    assert response.status_code == 200
    assert "Secure" in response.headers["set-cookie"]


def test_auth_rate_limit(auth):
    client, _, _, _ = auth
    for _ in range(30):
        response = client.post(
            "/auth/login", json={"email": "a@example.com", "password": "incorrect"}
        )
        assert response.status_code == 401
    assert (
        client.post(
            "/auth/login", json={"email": "a@example.com", "password": "incorrect"}
        ).status_code
        == 429
    )


def test_logout_closes_an_existing_websocket(auth):
    from starlette.websockets import WebSocketDisconnect

    client, _, _, _ = auth
    login(client)
    game = client.post("/games", json={"name": "logout socket"}).json()["game_id"]
    with client.websocket_connect(f"/games/{game}/events") as ws:
        assert ws.receive_json()["type"] == "snapshot"
        assert client.post("/auth/logout").status_code == 200
        with pytest.raises(WebSocketDisconnect) as error:
            ws.receive_json()
        assert error.value.code == 1008


def test_rotated_encryption_key_requests_reauthentication(auth):
    client, _, _, service = auth
    login(client)
    service.cipher = Fernet(Fernet.generate_key())
    assert client.get("/auth/session").status_code == 401


def test_mounted_auth_keeps_origin_checks_and_cache_protection(auth):
    from fastapi import FastAPI

    client, _, _, _ = auth
    parent = FastAPI()
    parent.mount("/api", client.app)
    with TestClient(parent) as mounted:
        response = mounted.post(
            "/api/auth/login",
            json={"email": "alice@example.com", "password": "correct-password"},
        )
        assert response.status_code == 403
        response = mounted.post(
            "/api/auth/login",
            json={"email": "alice@example.com", "password": "correct-password"},
            headers={"Origin": "http://testserver", "X-OFC-Request": "1"},
        )
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
