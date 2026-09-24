"""database configuration shared by runtime, migrations, and administrative commands."""

import os
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
POSTGRES_SCHEMA = "ofc"


def database_url():
    value = os.environ.get("OFC_DATABASE_URL") or dotenv_values(ROOT / ".env").get(
        "OFC_DATABASE_URL"
    )
    if not value:
        raise RuntimeError(
            "set OFC_DATABASE_URL in the environment or server/.env; "
            "use the Supabase direct or session-pooler PostgreSQL connection URI"
        )
    return value


def connection_url(value):
    url = make_url(value)
    if url.drivername == "postgres":
        url = url.set(drivername="postgresql+psycopg")
    if url.get_backend_name() == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
        if url.host not in {None, "localhost", "127.0.0.1", "::1"}:
            url = url.update_query_dict(
                {"sslmode": url.query.get("sslmode", "require")}
            )
        if url.port == 6543 and url.host and url.host.endswith("pooler.supabase.com"):
            raise ValueError(
                "use Supabase's direct connection or session pooler on port 5432"
            )
    elif url.get_backend_name() != "sqlite":
        raise ValueError("supported sql adapters are sqlite and postgresql")
    return url


def create_database_engine(value, **kwargs):
    url = connection_url(value)
    if url.get_backend_name() == "sqlite":
        if not url.database or url.database == ":memory:":
            raise ValueError("use a sqlite file for durable concurrent games")
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    else:
        kwargs.setdefault("connect_args", {"connect_timeout": 10})
    engine = create_engine(url, **kwargs)
    if url.get_backend_name() == "postgresql":

        @event.listens_for(engine, "connect")
        def set_schema(connection, record):
            # apply outside a transaction so rollback cannot undo the search path.
            previous = connection.autocommit
            connection.autocommit = True
            try:
                with connection.cursor() as cursor:
                    cursor.execute('SET SESSION search_path TO "ofc"')
            finally:
                connection.autocommit = previous

    return engine
