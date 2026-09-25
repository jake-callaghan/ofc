"""run local development with display-name login and an isolated sqlite database."""

import os

import uvicorn

from ofc.api import create_app
from ofc.database import ROOT
from ofc.schema import upgrade


def application():
    # never inherit the production database URI or Supabase credentials from .env.
    url = f"sqlite:///{ROOT / 'data' / 'development.sqlite3'}"
    app = create_app(url, dev_login=True)
    upgrade(url)
    return app


def main():
    if os.environ.get("FLY_APP_NAME") or os.environ.get("OFC_SQLITE_VOLUME"):
        raise RuntimeError("development login cannot run on the deployed server")
    uvicorn.run(
        "ofc.dev:application",
        factory=True,
        host="127.0.0.1",
        port=8000,
        reload=True,
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()
