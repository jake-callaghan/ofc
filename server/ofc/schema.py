"""explicit schema upgrades and resets; application startup never creates tables."""

import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData, inspect

from ofc.database import POSTGRES_SCHEMA, create_database_engine, database_url
from ofc.persistence.models import Base

ROOT = Path(__file__).resolve().parents[1]


def configuration(url=None):
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["database_url"] = url or database_url()
    return config


def upgrade(url=None):
    command.upgrade(configuration(url), "head")


def check_revision(engine):
    expected = set(
        ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini"))).get_heads()
    )
    with engine.connect() as connection:
        actual = set(
            MigrationContext.configure(
                connection,
                opts={
                    "version_table_schema": POSTGRES_SCHEMA
                    if engine.dialect.name == "postgresql"
                    else None
                },
            ).get_current_heads()
        )
    if actual != expected:
        raise RuntimeError(
            "database schema is not current; run python -m ofc.schema upgrade "
            "before starting the server"
        )


def reset(url):
    """drop only a dedicated application's schema, then replay all migrations."""
    engine = create_database_engine(url)
    schema = POSTGRES_SCHEMA if engine.dialect.name == "postgresql" else None
    try:
        with engine.begin() as connection:
            tables = set(inspect(connection).get_table_names(schema=schema))
            unknown = tables - set(Base.metadata.tables) - {"alembic_version"}
            if unknown:
                raise ValueError("refusing to reset a database with non-OFC tables")
            metadata = MetaData()
            metadata.reflect(connection, schema=schema)
            # reflection can follow foreign keys into another service's schema.
            # only our own tables may be reset, even when such references exist.
            metadata.drop_all(
                connection,
                tables=[
                    table
                    for table in metadata.tables.values()
                    if table.schema == schema
                ],
            )
    finally:
        engine.dispose()
    upgrade(url)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["upgrade", "check", "current", "reset"])
    parser.add_argument("--database-url")
    parser.add_argument("--delete-all-data", action="store_true")
    args = parser.parse_args()
    url = args.database_url or database_url()
    if args.action == "reset":
        if not args.database_url or not args.delete_all_data:
            parser.error(
                "reset requires --database-url and --delete-all-data; stop the server first"
            )
        reset(url)
    elif args.action == "upgrade":
        upgrade(url)
    elif args.action == "check":
        command.check(configuration(url))
    else:
        command.current(configuration(url), verbose=True)


if __name__ == "__main__":
    main()
