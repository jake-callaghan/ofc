# Open Face frontend

React JavaScript + Vite. Uses the Python backend for all dealing, validation,
private game state, and scoring. Node.js 22.12+ and pnpm are required.

From the repository root, run the backend and frontend in separate terminals:

```sh
uv run --directory server uvicorn ofc.api:app --reload
```

```sh
pnpm --dir frontend install
pnpm --dir frontend dev
```

Open the URL Vite prints (normally http://127.0.0.1:5173).
Vite proxies `/api` HTTP and WebSocket requests to port 8000. Set
`OFC_API_TARGET=http://127.0.0.1:PORT` when starting Vite to use another backend.
No CORS configuration is needed for this local setup.

## Playing

1. Choose a display name. Your player key is stored in this browser.
2. Create a table, select Classic or Pineapple and the desired Fantasyland mode.
3. Copy the invitation link and share it. Your friend opens it in another
   browser/profile, chooses a name, and joins. Tabs in the same browser share
   one identity; use a separate profile or private window to play both sides.
4. The host selects active players and deals. Each player selects a drawn card,
   then an empty row slot. Pending cards can be returned and rearranged.
5. Assign every drawn card, including required discards, then confirm the move.
6. The completed hand shows pairwise scoring and updates the running ledger.
   The host can deal another hand; players may sit out between hands.

A single authenticated WebSocket supplies player-specific snapshots. It
reconnects with backoff and restores state after a refresh. Moves use HTTP with
version checks and stable request IDs for transport retries. Uncommitted drafts
are local and reset on refresh; accepted moves are durable. Backend private-card
filtering keeps opponents' draws/discards and hidden Fantasyland cards out of
responses. The frontend does not calculate authoritative poker scores.

The clubhouse remembers tables locally. Download your player key from the
clubhouse to restore an identity in a fresh browser using the welcome screen's
file input. Keep this file private: it contains your authentication token.
This is guest identity storage, not a full account/password system.

House-rule toggles use the backend's documented provisional moon/Candyland
presets. The table's rules panel explains their payout behavior.

## Validation

```sh
pnpm --dir frontend test
pnpm --dir frontend build
pnpm --dir frontend exec playwright install chromium
pnpm --dir frontend test:e2e
```

Browser tests start isolated servers on ports 8011 and 5174 and use a temporary
SQLite database; they do not write to your normal game database. They cover
registration, invitations, live two-player play, an entire Pineapple hand,
reconnect, history, and mobile layout. Python `uv` must be on PATH.

For production, serve `dist/` from your frontend host and route `/api/*` to the
Python service, stripping `/api` and supporting WebSocket upgrades. Vite's dev
proxy is not included in the build. Use HTTPS/WSS on a public deployment. The
production preview command only previews static assets and does not proxy the
API. Display fonts use Google Fonts with local serif/sans-serif fallbacks.

## CPU practice

Create a table, then click **+ Add CPU player** in the seats panel. Select yourself
and one or more CPUs and click **Deal next hand**. The host can add CPUs between
hands (up to two for Pineapple, three for Classic; Candyland limits Classic to two).
Uncheck a CPU to sit it out. At least one human must be selected.

CPUs automatically play after each human action, including the initial deal and
Fantasyland. They favour pairs and suited/connected lower rows, and prioritise
valid completed boards and royalties. This is a limited heuristic, not a solver;
it can make mistakes and foul. CPU turns use only their own filtered view.

## Source layout

- `src/App.jsx`: application shell, saved identity, and page selection.
- `src/components/`: shared header, footer, error message, and card/board components.
- `src/features/player/`: welcome screen and identity creation/restoration.
- `src/features/lobby/`: table creation, invitations, and saved tables.
- `src/features/table/`: table page, sidebar/CPU seats, turn editor, history,
  score breakdown, and the `useGame` connection/command hook.
- `src/lib/`: HTTP client, pure placement helpers, browser storage, and URL helpers.
- `src/styles/`: base, lobby, table, card, turn, and responsive styles. `index.css`
  imports them in cascade order; global class names are retained.

Use `pnpm --dir frontend format` to format source files or
`pnpm --dir frontend format:check` to check formatting without edits.
