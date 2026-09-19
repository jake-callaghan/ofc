# Open Face Chinese Poker http://ofcpoker.live

Multiplayer OFC with Pineapple, Fantasyland, house-rule royalties and CPU practice. React frontend, Python/FastAPI backend, scores in units.

- [Backend](server/README.md)
- [Frontend](frontend/README.md)
- [CPU reinforcement learning](training/README.md)

## Gameplay

![alt text](gameplay.gif)

## Development

Requires Python 3.13+, uv, Node 22.12+ and pnpm. Commands run from the repository root.

Backend:

```sh
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
docker run --rm -p 8080:8080 -v ofc_data:/data ofc
```

App: http://localhost:8080 · API docs: http://localhost:8080/api/docs

One container serves the React build, API and WebSockets. SQLite is stored at `/data/ofc.sqlite3` on the named volume. Alembic migrations run at startup.

## Fly.io

The `ofc` app uses one Machine in London and an `ofc_data` volume, configured in `fly.toml`.

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
fly volumes create ofc_data --app YOUR_APP_NAME --region lhr --size 1
```

Keep a single Machine with SQLite and back up the database separately. Deployments briefly interrupt connections. Multiple Machines require a shared database such as PostgreSQL.
