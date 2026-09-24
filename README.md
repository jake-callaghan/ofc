# Open Face Chinese Poker http://ofcpoker.live

Multiplayer OFC with Pineapple, Fantasyland, house-rule royalties and CPU practice. React frontend, Python/FastAPI backend, scores in units.

- [Backend](server/README.md)
- [Authentication development](server/AUTH.md)
- [Frontend](frontend/README.md)
- [CPU reinforcement learning](training/README.md)

## Gameplay

![alt text](gameplay.gif)

## Development

Requires Python 3.13+, uv, Node 22.12+ and pnpm. Commands run from the repository root.

Backend: copy `server/.env.example` to `server/.env`, then replace the password
with your URL-encoded Supabase database password. Use a direct connection or the
session pooler on port 5432. The file is ignored by Git and Docker.

```sh
uv run --directory server python -m ofc.schema upgrade
uv run --directory server uvicorn ofc.api:app --reload
```

Frontend, in a second terminal:

```sh
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend dev
```

Frontend: http://localhost:5173 · API docs: http://localhost:8000/docs

## Docker

```sh
docker build -t ofc .
docker run --rm -p 8080:8080 --env-file server/.env ofc
```

App: http://localhost:8080 · API docs: http://localhost:8080/api/docs

One container serves the React build, API and WebSockets. Game data lives in the
private `ofc` schema in Supabase PostgreSQL. Alembic migrations run at startup.
Supabase owns its separate `auth` schema; these migrations never alter it.

## Fly.io

The `ofc` app runs in London and connects to Supabase PostgreSQL. It no longer
mounts the old SQLite volume. Before the first PostgreSQL deployment, store
`OFC_DATABASE_URL` as a Fly secret (do not put credentials in `fly.toml`):

```sh
fly secrets import --stage < server/.env
```

Keep only deployment secrets in that file. Staging avoids restarting the previous
SQLite deployment before the PostgreSQL-ready image is available. The next deploy
runs migrations against the shared database in its release command.

Deploy updates:

```sh
fly deploy --ha=false
```

Status and logs:

```sh
fly status
fly logs
```

For a new deployment, set a unique app name in `fly.toml`, then provision it before deploying:

```sh
fly auth login
fly apps create YOUR_APP_NAME
```

The old SQLite data is not copied. Existing player keys and game links refer to
the old database and will no longer work. Retire the old Fly volume separately
after verifying the new deployment. Email/password authentication is implemented locally; follow the separate
[authentication setup](server/AUTH.md) before enabling it. The current production
deployment still uses player keys.

For isolated local tests, SQLite remains available only with an explicit
`OFC_DATABASE_URL=sqlite:///data/test.sqlite3`. Without configuration, startup
fails instead of silently creating a local database.

## Lobby access

Signed-in players can browse and watch every active table. New tables default to
Open, so anyone can join from the lobby or with an invite. Private tables are
also listed and watchable, but joining requires an invitation. Hosts can change
access between hands. Existing tables without an access setting remain Private.
Spectators receive no private draws, discards, unrevealed Fantasyland boards, or
member chat; joining a table makes a player eligible for a future hand.
