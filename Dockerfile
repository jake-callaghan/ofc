FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
RUN npm install --global pnpm@12.4.1
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM ghcr.io/astral-sh/uv:0.12.1 AS uv
FROM python:3.13-slim-bookworm
COPY --from=uv /uv /uvx /usr/local/bin/
WORKDIR /app/server
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    PATH="/app/server/.venv/bin:$PATH" \
    OFC_STATIC_DIR=/app/frontend/dist \
    OFC_DATABASE_URL=sqlite:////data/ofc.sqlite3 \
    PYTHONUNBUFFERED=1
COPY server/pyproject.toml server/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY server/ ./
RUN uv sync --locked --no-dev && mkdir -p /data
COPY --from=frontend /build/frontend/dist /app/frontend/dist
EXPOSE 8080
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn ofc.web:create_app --factory --host 0.0.0.0 --port 8080"]
