"""a missing volume must never silently start a fresh ephemeral game database."""

import sqlite3

import pytest

from ofc.startup import prepare


def test_startup_migrates_and_preserves_sqlite_on_restart(tmp_path, monkeypatch):
    path = tmp_path / "data" / "game.sqlite3"
    monkeypatch.setenv("OFC_DATABASE_URL", f"sqlite:///{path}")
    monkeypatch.delenv("OFC_SQLITE_VOLUME", raising=False)
    prepare()
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert (
            db.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            == "0002"
        )
        db.execute(
            "INSERT INTO players (id, name, token_hash) VALUES ('alice', 'Alice', NULL)"
        )
    prepare()
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT name FROM players").fetchall() == [("Alice",)]


def test_startup_refuses_missing_volume(tmp_path, monkeypatch):
    monkeypatch.setenv("OFC_SQLITE_VOLUME", str(tmp_path))
    monkeypatch.setenv("OFC_DATABASE_URL", f"sqlite:///{tmp_path / 'game.sqlite3'}")
    with pytest.raises(RuntimeError, match="not mounted"):
        prepare()
    assert not (tmp_path / "game.sqlite3").exists()


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://user:secret@localhost/postgres",
        "sqlite:///relative.sqlite3",
        "sqlite:////tmp/outside.sqlite3",
    ],
)
def test_startup_requires_sqlite_inside_volume(tmp_path, monkeypatch, url):
    monkeypatch.setenv("OFC_SQLITE_VOLUME", str(tmp_path))
    monkeypatch.setenv("OFC_DATABASE_URL", url)
    monkeypatch.setattr("ofc.startup.os.path.ismount", lambda _: True)
    with pytest.raises(
        RuntimeError, match=r"requires a SQLite|inside the persistent volume"
    ):
        prepare()
