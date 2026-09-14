"""composition root: choose the persistence adapter without changing the service."""

import os

from ofc.persistence.sqlalchemy import SQLAlchemyRepository


def build_repository(database_url: str | None = None) -> SQLAlchemyRepository:
    url = database_url or os.environ.get(
        "OFC_DATABASE_URL", "sqlite:///data/ofc.sqlite3"
    )
    repository = SQLAlchemyRepository(url)
    # local development is zero-setup; managed sql deployments run migrations.
    if repository.sqlite:
        repository.create_schema()
    return repository
