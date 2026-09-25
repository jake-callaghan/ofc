"""development login must stay isolated from hosted auth and the production database."""

import pytest
from fastapi.testclient import TestClient

from ofc.api import create_app
from ofc.dev import application


def test_dev_login_ignores_production_settings(tmp_path, monkeypatch):
    monkeypatch.setattr("ofc.dev.ROOT", tmp_path)
    monkeypatch.setenv(
        "OFC_DATABASE_URL", "postgresql://invalid:invalid@invalid/postgres"
    )
    monkeypatch.setenv("OFC_SUPABASE_URL", "https://invalid.example")
    monkeypatch.setattr(
        "ofc.api.AuthSettings.load", lambda: pytest.fail("dev must not load Supabase")
    )
    with TestClient(application()) as client:
        assert client.get("/auth/config").json() == {
            "enabled": False,
            "legacy": True,
            "dev_login": True,
        }
        player = client.post("/players", json={"name": "Dev player"}).json()
        response = client.post(
            "/games",
            json={"name": "Dev table"},
            headers={"Authorization": "Bearer " + player["token"]},
        )
        assert response.status_code == 201
    assert (tmp_path / "data" / "development.sqlite3").exists()


@pytest.mark.parametrize("marker", ["FLY_APP_NAME", "OFC_SQLITE_VOLUME"])
def test_dev_login_refuses_deployment(marker, monkeypatch):
    monkeypatch.setenv(marker, "production")
    with pytest.raises(RuntimeError, match="deployed server"):
        create_app("sqlite:///dev.sqlite3", dev_login=True)


def test_dev_login_requires_explicit_sqlite():
    with pytest.raises(RuntimeError, match="explicit local SQLite"):
        create_app(dev_login=True)
    with pytest.raises(RuntimeError, match="explicit local SQLite"):
        create_app("postgresql://invalid:invalid@localhost/postgres", dev_login=True)
