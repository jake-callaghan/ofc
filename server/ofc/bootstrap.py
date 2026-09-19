"""composition root: choose the persistence adapter without changing the service."""

import os

from ofc.persistence.sqlalchemy import SQLAlchemyRepository


def build_cpu():
    from ofc.search import choose_default_move

    path = os.environ.get("OFC_CPU_MODEL")
    if not path:
        return choose_default_move
    from ofc.trained_cpu import TrainedCPU

    return TrainedCPU(path).choose_move


def build_repository(database_url: str | None = None) -> SQLAlchemyRepository:
    url = database_url or os.environ.get(
        "OFC_DATABASE_URL", "sqlite:///data/ofc.sqlite3"
    )
    repository = SQLAlchemyRepository(url)
    # local development is zero-setup; managed sql deployments run migrations.
    if repository.sqlite:
        repository.create_schema()
    return repository
