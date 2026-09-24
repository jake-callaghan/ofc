"""connection configuration must never fall back silently to a local game database."""

import pytest

from ofc.database import connection_url, database_url


def test_supabase_uri_uses_psycopg_and_tls():
    url = connection_url(
        "postgresql://postgres:secret@db.example.supabase.co:5432/postgres"
    )
    assert url.drivername == "postgresql+psycopg"
    assert url.query["sslmode"] == "require"
    assert url.password == "secret"
    assert "secret" not in str(url)


def test_explicit_certificate_verification_is_preserved():
    url = connection_url(
        "postgres://user:secret@db.example.supabase.co/postgres?sslmode=verify-full"
    )
    assert url.query["sslmode"] == "verify-full"


def test_transaction_pooler_is_rejected():
    with pytest.raises(ValueError, match="session pooler"):
        connection_url(
            "postgresql://user:secret@aws-0-eu-west-2.pooler.supabase.com:6543/postgres"
        )


def test_missing_configuration_fails_instead_of_selecting_sqlite(monkeypatch, tmp_path):
    monkeypatch.delenv("OFC_DATABASE_URL", raising=False)
    monkeypatch.setattr("ofc.database.ROOT", tmp_path)
    with pytest.raises(RuntimeError, match="set OFC_DATABASE_URL"):
        database_url()
    (tmp_path / ".env").write_text(
        "OFC_DATABASE_URL=postgresql://user:secret@localhost/postgres\n"
    )
    assert database_url().startswith("postgresql://")
    monkeypatch.setenv("OFC_DATABASE_URL", "sqlite:///explicit-test.sqlite3")
    assert database_url() == "sqlite:///explicit-test.sqlite3"


def test_offline_postgres_migration_targets_private_schema():
    from io import StringIO

    from alembic import command

    from ofc.schema import configuration

    config = configuration("postgresql://user:secret@localhost/postgres")
    output = StringIO()
    config.output_buffer = output
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    assert 'CREATE SCHEMA IF NOT EXISTS "ofc"' in sql
    assert 'SET search_path TO "ofc"' in sql
    assert "CREATE TABLE ofc.alembic_version" in sql
    assert "CREATE TABLE players" in sql
    assert "auth." not in sql
    assert "secret" not in sql
