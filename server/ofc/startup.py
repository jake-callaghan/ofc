"""migrate the mounted database before accepting traffic on the single app server."""

import os
import sqlite3
import sys
from pathlib import Path

from ofc.database import connection_url, database_url
from ofc.schema import upgrade


def prepare():
    url = database_url()
    target = connection_url(url)
    volume = os.environ.get("OFC_SQLITE_VOLUME")
    if volume:
        mount = Path(volume).resolve()
        if not os.path.ismount(mount):
            raise RuntimeError(
                "SQLite volume is not mounted; refusing ephemeral storage"
            )
        if target.get_backend_name() != "sqlite" or not target.database:
            raise RuntimeError(
                "mounted-volume deployment requires a SQLite database URL"
            )
        path = Path(target.database)
        if not path.is_absolute() or not path.resolve().is_relative_to(mount):
            raise RuntimeError("SQLite database must be inside the persistent volume")
    if target.get_backend_name() == "sqlite":
        if not target.database or target.database == ":memory:":
            raise RuntimeError("SQLite requires a persistent database file")
        path = Path(target.database)
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, timeout=30)
        try:
            # wal lets snapshot readers run while a move is being committed.
            connection.execute("PRAGMA journal_mode=WAL")
        finally:
            connection.close()
    upgrade(url)


def main():
    prepare()
    os.execv(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "ofc.web:create_app",
            "--factory",
            "--host",
            "0.0.0.0",
            "--port",
            "8080",
        ],
    )


if __name__ == "__main__":
    main()
