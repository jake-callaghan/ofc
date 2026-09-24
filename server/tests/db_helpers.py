"""create disposable test databases through the same migrations as deployment."""

from ofc.api import create_app as api_app
from ofc.bootstrap import build_repository as repository
from ofc.schema import upgrade


def build_repository(url):
    upgrade(url)
    return repository(url)


def create_app(url=None, **kwargs):
    if url is not None:
        upgrade(url)
    kwargs.setdefault("allow_legacy_keys", True)
    return api_app(url, **kwargs)
