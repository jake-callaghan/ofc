# Open-face Chinese poker

React frontend and Python/FastAPI backend. See [server/README.md](server/README.md) for the engine and [frontend/README.md](frontend/README.md) for the UI.

## Local development

Run in separate terminals from this directory:

```sh
uv run --directory server uvicorn ofc.api:app --reload
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend dev
```

Open http://127.0.0.1:5173. Requires Python 3.13+, uv, Node 22.12+ and pnpm.

## Production container

The Dockerfile builds React using Node, then copies the static files into a Python image. Only Uvicorn runs in production: `/` serves React, `/api` serves game requests and WebSockets, and `/api/docs` serves API documentation. No Compose or running Node server is needed.

```sh
docker build -t ofc .
docker volume create ofc_data
docker run --rm -p 8080:8080 -v ofc_data:/data ofc
```

Open http://localhost:8080. SQLite lives at `/data/ofc.sqlite3`; the volume preserves games across container replacements. Alembic migrations run at startup before the web server. Back up the database before deploying schema changes.

## Deploy to Fly.io

Install [flyctl](https://fly.io/docs/flyctl/install/) and sign in with `fly auth login`. A Fly account with billing enabled is required. Run these commands from this directory:

1. Choose a globally unique app name and replace `replace-with-your-ofc-app` in `fly.toml`.
2. Create the app and one persistent volume in London (change both region settings together if desired):

   ```sh
   fly apps create YOUR_APP_NAME
   fly volumes create ofc_data --app YOUR_APP_NAME --region lhr --size 1
   ```

3. Deploy a single Machine and open the app:

   ```sh
   fly deploy --ha=false
   fly open
   ```

Later updates use `fly deploy --ha=false` again. Inspect with `fly status` and `fly logs`. Fly provides HTTPS and secure WebSockets; the container listens on port 8080. The Machine stays running for long-lived game connections.

Keep **one Machine** while using SQLite: Fly volumes are local to a Machine and do not share database writes. This setup has brief downtime during deployments and is not highly available. Configure backups for the persistent database; a volume is not a backup. Migrations run in the Machine with its volume mounted, rather than a Fly release command (which has no access to that volume).

To scale later, use shared PostgreSQL: install the backend's `postgres` extra in the image, set `OFC_DATABASE_URL` with `fly secrets set`, remove the SQLite environment setting and volume mount, and arrange migrations before scaling. The repository abstraction already supports PostgreSQL.

See [Fly configuration](https://fly.io/docs/reference/configuration/) and [volume storage](https://fly.io/docs/launch/volume-storage/) for platform details.
