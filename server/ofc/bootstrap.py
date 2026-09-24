"""composition root: choose the persistence adapter without changing the service."""

import os

from ofc.database import database_url as configured_database_url
from ofc.persistence.sqlalchemy import SQLAlchemyRepository


def build_cpu():
    from ofc.search import choose_default_move

    path = os.environ.get("OFC_CPU_MODEL")
    if not path:
        return choose_default_move
    from ofc.trained_cpu import TrainedCPU

    return TrainedCPU(path).choose_move


def build_repository(database_url: str | None = None) -> SQLAlchemyRepository:
    url = database_url or configured_database_url()
    repository = SQLAlchemyRepository(url)
    from ofc.schema import check_revision

    try:
        check_revision(repository.engine)
    except Exception:
        repository.close()
        raise
    return repository
