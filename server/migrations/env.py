"""migrate application tables only; supabase owns its auth and storage schemas."""

from alembic import context
from sqlalchemy import pool, text

from ofc.database import (
    POSTGRES_SCHEMA,
    connection_url,
    create_database_engine,
    database_url,
)
from ofc.persistence.models import Base

config = context.config
url = config.attributes.get("database_url") or database_url()
target = connection_url(url)
postgres = target.get_backend_name() == "postgresql"


def options():
    return {
        "target_metadata": Base.metadata,
        # postgres reflects the version table through our default search path;
        # it is migration bookkeeping, never an application table to remove.
        "include_name": lambda name, kind, parent: not (
            kind == "table" and name == "alembic_version"
        ),
        "version_table_schema": POSTGRES_SCHEMA if postgres else None,
        "render_as_batch": not postgres,
    }


if context.is_offline_mode():
    context.configure(url=target, literal_binds=True, **options())
    with context.begin_transaction():
        if postgres:
            context.execute('CREATE SCHEMA IF NOT EXISTS "ofc"')
            context.execute('SET search_path TO "ofc"')
        context.run_migrations()
else:
    engine = create_database_engine(target, poolclass=pool.NullPool)
    with engine.connect() as connection:
        if postgres:
            connection.execute(text('CREATE SCHEMA IF NOT EXISTS "ofc"'))
            connection.execute(text('REVOKE ALL ON SCHEMA "ofc" FROM PUBLIC'))
            for role in ("anon", "authenticated"):
                if connection.scalar(
                    text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": role}
                ):
                    connection.execute(
                        text(f'REVOKE ALL ON SCHEMA "ofc" FROM "{role}"')
                    )
            connection.commit()
            # the first connection may precede schema creation; reflection must
            # compare only our schema rather than supabase's public tables.
            connection.dialect.default_schema_name = POSTGRES_SCHEMA
        context.configure(connection=connection, **options())
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
