"""serve the browser build and game api from one production process."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ofc.api import create_app as create_api


def create_app(*, static_dir: str | Path | None = None, database_url: str | None = None):
    api = create_api(database_url)
    directory = Path(static_dir or os.environ.get("OFC_STATIC_DIR", "../frontend/dist"))
    if not (directory / "index.html").is_file():
        raise RuntimeError(f"frontend build missing in {directory}; run pnpm build first")

    @asynccontextmanager
    async def lifespan(app):
        # mounted applications need their lifespan started explicitly.
        async with api.router.lifespan_context(api):
            yield

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/api", api)
    # navigation uses url fragments, so only actual static paths need serving.
    app.mount("/", StaticFiles(directory=directory, html=True), name="frontend")
    return app
