# OFC Python backend

Table chat stores the latest 100 messages with the game state. Members can send up to 1,000 characters and add/remove emoji reactions. Chat uses the existing authenticated WebSocket snapshots with an independent revision counter, so it does not invalidate gameplay commands. Existing databases need no schema migration.

A Python 3.13+ rules engine and FastAPI backend for persistent multiplayer
open-face Chinese poker. Uses uv for environments, dependency locking, and tools.
The React JavaScript frontend lives in `frontend/`; see [frontend setup](frontend/README.md).

## Authentication

Google and email/password login are implemented locally. See [AUTH.md](AUTH.md)
for isolated development setup, provider settings, identity linking, and sessions.
The production deployment has not been updated with this authentication change.

## Run

```sh
uv sync --directory server --locked
# configure OFC_DATABASE_URL in server/.env first
uv run --directory server python -m ofc.schema upgrade
uv run --directory server uvicorn ofc.api:app --reload
```

Open http://127.0.0.1:8000/docs for the interactive API schema.
Configure `OFC_DATABASE_URL` in the environment or ignored `server/.env` file
using your Supabase PostgreSQL direct or session-pooler URI. Migrations create
tables in the private `ofc` schema before application startup.
For local React development, proxy `/players`, `/games`, and
`/health` to the backend, including WebSocket upgrade requests.

```sh
uv run --directory server pytest
uv run --directory server ruff check .
uv run --directory server ruff format --check .
```

`server/.python-version` selects Python 3.13; `server/uv.lock` pins dependencies.

## Client workflow

1. `POST /players` with `{"name": "Alice"}`. Save the returned `player_id` and
   secret `token`. This is a lightweight guest identity, without password recovery.
2. Send `Authorization: Bearer <token>` with subsequent HTTP requests.
3. `POST /games` with a name and optional rules. The creator receives a secret
   invitation code, which they can share with friends.
4. Each friend registers and calls `POST /games/{game_id}/join` with `invite`
   and a unique `request_id`. This endpoint does not require reading a private
   game version before joining. The versioned `join` command remains available.
5. The owner submits `start` with the active player IDs. Game membership can
   exceed table capacity; the selected active seats are fixed for the hand.
6. Read your private draw and the current turn from `GET /games/{game_id}`.
7. Submit a complete `place` command. Cards can be rearranged locally before
   submission; accepted placements cannot move.
8. Completed hands automatically score and update cumulative unit balances.
   The owner starts the next hand when players are ready.

Commands use `POST /games/{game_id}/commands`:

```json
{
  "request_id": "a-client-generated-uuid",
  "version": 0,
  "command": {"type": "join", "invite": "invitation-from-owner"}
}
```

```json
{
  "request_id": "another-client-generated-uuid",
  "version": 1,
  "command": {"type": "start", "players": ["alice-id", "bob-id"]}
}
```

Example placement for a player whose actual five-card draw matches these cards:

```json
{
  "request_id": "unique-placement-id",
  "version": 2,
  "command": {
    "type": "place",
    "placements": {"top": ["Qc", "Qd"], "middle": ["5s"], "bottom": ["Ac", "Kc"]},
    "discards": []
  }
}
```

Use the latest game `version`. A stale command returns 409. Retrying the same
request ID and command returns its original `applied_version` plus the current
private snapshot, without applying it twice. Reusing an ID for different command
content returns 409. A new attempt after changing a rejected move needs a fresh ID.
Cards are rank plus lowercase suit: `23456789TJQKA` and `cdhs`.

For updates, connect to `/games/{game_id}/events`, then send
`{"token": "your-player-token"}` as the first frame within ten seconds.
The server sends `{"type": "snapshot", "state": {...}}` initially and whenever
the game version changes. Credentials never go in the URL. Reconnect to get the
latest snapshot. Commands remain HTTP requests. This initial implementation
checks durable state every 500 ms, so updates also work across backend processes.

`GET /games/{game_id}/hands?after=0&limit=50` returns completed boards, rules,
evaluations, pairwise breakdowns, and unit changes. Opponent discards stay private.

## Rules implemented

Game creation accepts this rules object (shown with defaults):

```json
{
  "name": "Friday game",
  "rules": {
    "variant": "pineapple",
    "fantasyland": "progressive",
    "moon": false,
    "candyland": false
  }
}
```

- Classic: five initial cards, then eight single cards; 2–4 active players.
  Select `fantasyland: "standard"` or `"off"` explicitly for Classic.
- Pineapple: five initial cards, then four draws of three, placing two and
  discarding one each time; 2–3 active players.
- Rows: top 3, middle 5, bottom 5. Bottom must rank at least as high as middle,
  and middle at least as high as top. A completed foul is allowed but penalised.
- Standard poker categories and kickers; ace-low straights count. Top straights
  and flushes do not count as ordinary poker categories. Missing top kickers are
  padded with zero when comparing against middle.
- Each row wins/loses one unit; tied rows score zero. Winning all three adds a
  three-unit scoop bonus. Royalties are netted per opponent.
- A foul loses six units plus the valid opponent's royalties; two fouls tie.
  Fouls earn no royalties or Fantasyland.

| Row | Royalties in units |
| --- | --- |
| Top pair | 66 through AA: 1 through 9 |
| Top trips | 222 through AAA: 10 through 22 |
| Middle | trips 2, straight 4, flush 8, full house 12, quads 20, straight flush 30, royal flush 50 |
| Bottom | straight 2, flush 4, full house 6, quads 10, straight flush 15, royal flush 25 |

Royal flush replaces the straight-flush royalty; bonuses do not stack within a
row. The schedule is currently a fixed preset in `ofc.rules.royalties`.

Fantasyland requires QQ+ at the top on a valid board. Classic standard grants
13 cards; Pineapple standard grants 14. Progressive Pineapple grants QQ=14,
KK=15, AA=16, trips=17. Set 13 and discard the remainder.
To stay: top trips or bottom quads+; Classic additionally allows middle full
house+. Staying grants 13 cards in Classic or 14 in Pineapple, except Candyland.
At the start of each street, all normal players receive their private draws and
can arrange cards early; only the current player may confirm. Draft placements
remain local until confirmation.
Fantasy players arrange and confirm independently while normal turns continue.
Their boards remain hidden, and they cannot see opponents’ boards until showdown.
Showdown waits for all normal turns and Fantasyland confirmations; normal players
can still see each other’s placements during play. The button holds while an active player earns
Fantasyland and otherwise advances through membership order. An inactive player's
Fantasyland award is preserved until they next play.

### Optional house-rule presets

These are explicit provisional choices, disabled by default, pending confirmation
of the group's rules. Precedence is Candyland, then moon, then ordinary scoring.

- **Moon:** a non-fouled J-high bottom qualifies. Receive 20 units per opponent
  instead of normal row, foul, and royalty scoring. Two moon players tie.
- **Candyland:** each row consists entirely of one suit, including the top's
  three-card flush. Normal row-order fouling is waived. Against a non-Candyland
  board, receive six units plus your middle/bottom royalties; ignore the
  opponent's royalties. Two Candyland boards tie. Earn 15-card Fantasyland,
  including on repeated Candyland hands. No repeat limit is imposed.
- Candyland requires Fantasyland enabled and limits active seats to three,
  including in Classic, so its 15-card award remains dealable.

Capacity is checked again before every deal, including actual Fantasyland awards.
Discards never return to the deck. Special scoring and tie policies can be changed
centrally in `ofc.rules` once the house rules are settled.

Rule references: [Pagat OFC](https://www.pagat.com/partition/openface.html),
[OFC Strategy](https://www.ofcstrategy.com/rules.html),
[moon description](https://en.wikipedia.org/wiki/Open-face_Chinese_poker), and
[Candyland house-rule discussion](https://forumserver.twoplustwo.com/21/other-poker-games/pineapple-open-face-chinese-rules-1347685/index2.html).

## Structure and persistence

- `ofc/rules.py`: pure evaluation, royalties, special awards, and pairwise scoring.
- `ofc/engine.py`: immutable command transitions, deal schedules, and private views.
- `ofc/store.py`: application service for identities, commands, and scoring;
  depends only on repository protocols, with no SQL or ORM imports.
- `ofc/persistence/ports.py`: typed repository and unit-of-work contracts.
- `ofc/persistence/models.py`: SQLAlchemy ORM mappings.
- `ofc/persistence/sqlalchemy.py`: SQLite/PostgreSQL adapter and locking.
- `ofc/bootstrap.py`: adapter selection and local database setup.
- `migrations/`: versioned Alembic schema migrations.
- `ofc/api.py`: validated HTTP API and authenticated WebSocket snapshots.

A repository write transaction covers command validation, state changes, hand results,
and ledger posting. There is one ledger entry per player per completed hand.
The engine never trusts client-supplied cards, scores, turn ownership, or balances.
Only a player's own draw/discards and publicly visible boards are returned.
The shuffled deck is server-only, persisted so a restart cannot change the deal.
Engine transitions copy state before applying an action, preserving the original
on rejection. Rules are fixed for a game and copied into completed hand records.

This is a local/private-game backend foundation. Full
account management/token recovery, invitation rotation, custom royalty tables,
ledger corrections, timers, and administrative game lifecycle controls remain
future work. Live games are untimed: disconnecting leaves the turn pending.
Use TLS when exposing the service outside localhost and protect the database,
which contains private cards and action history.


## Switching persistence

`Store(repository)` contains the application operations. Its repository exposes
`transaction(write=...)`, returning a unit of work with domain-specific storage
operations. ORM entities, SQL queries, locks, and connection management stay in
the adapter. `create_app(repository=...)` accepts a custom adapter; the caller
owns its lifecycle. The default composition root constructs a SQLAlchemy adapter.

## Supabase PostgreSQL

The main game database uses Supabase PostgreSQL, in the private `ofc` schema.
Supabase's `auth`, `storage`, and `public` schemas are outside Alembic's scope.
The app accesses game data through SQLAlchemy; do not expose `ofc` through the
Supabase Data API. Migrations revoke schema access from PUBLIC and, when present,
the `anon` and `authenticated` roles. Use the same database role for migration
and runtime until dedicated role grants are configured.

Set `OFC_DATABASE_URL` in the environment or the ignored `server/.env` file.
Environment configuration takes precedence. Copy the direct or session-pooler
URI from Supabase's Connect panel, substitute a URL-encoded password, and use
TLS. `postgresql://` URIs automatically use psycopg; remote connections default
to `sslmode=require`. The transaction pooler on port 6543 is not supported.
The backend keeps at most seven pooled connections per process.

There is no implicit SQLite fallback. For explicit local SQLite tests, set
`OFC_DATABASE_URL=sqlite:///data/test.sqlite3` and run migrations first.

For managed PostgreSQL:

```sh
uv sync --directory server --locked --extra postgres
export OFC_DATABASE_URL='postgresql+psycopg://user:password@host:5432/ofc?sslmode=require'
uv run --directory server alembic upgrade head
uv run --directory server uvicorn ofc.api:app
```

Use your provider's connection credentials and TLS settings. Both SQLite and
PostgreSQL use Alembic migrations. Application startup checks the revision and
fails clearly when the schema is missing or behind; it never creates tables.

## Schema versions and resets

Run from the repository root:

```sh
uv run --directory server python -m ofc.schema upgrade
uv run --directory server python -m ofc.schema current
uv run --directory server python -m ofc.schema check
```

After changing the SQLAlchemy models, generate and review a migration:

```sh
uv run --directory server alembic revision --autogenerate -m "describe the change"
uv run --directory server python -m ofc.schema upgrade
```

Commit migrations alongside model changes. Review generated changes, especially
renames and data transformations. CI upgrades a blank database and checks it
against the models; tests also exercise upgrades and resets. Docker runs upgrades
before the server starts. With multiple app instances, run migrations once as a
separate deployment step before bringing up the new application version.

To discard all players, games, history, scores, and command receipts, first stop
the server, then explicitly name the database and acknowledge deletion:

```sh
uv run --directory server python -m ofc.schema reset --database-url sqlite:///data/ofc.sqlite3 --delete-all-data
```

The SQLite path is relative to `server` when using `uv run --directory server`.
The reset command drops application tables and replays migrations. On PostgreSQL
it acts only inside `ofc`; it leaves Supabase authentication and all other schemas
untouched. It refuses unexpected tables within the target schema. This is a separate administrative operation, never part of startup or
ordinary deployment. Existing browser player keys become invalid after a reset.
For an old unversioned development database whose data is disposable, use reset
rather than stamping an unknown schema as current.

PostgreSQL commands lock the game row with `SELECT FOR UPDATE`; SQLite uses
`BEGIN IMMEDIATE`. Read operations use a consistent transaction snapshot so
boards and balances cannot come from different commits. Connections are pooled,
checked before reuse, and each operation has its own short-lived session.
See [SQLAlchemy transaction handling](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)
and [SQLite transaction handling](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html).

A non-SQL cloud adapter implements the same `Repository` and `UnitOfWork`
protocols. It must support atomic state/result/ledger/receipt writes, consistent
reads, and per-game concurrency control; swapping in independent eventually
consistent writes would violate the contract. Provider-specific authentication,
SDK calls, and retry handling belong in that adapter. No cloud SDK is required
by the rules engine or service.

Contract tests cover rollback and detached reads. Set `OFC_TEST_DATABASE_URL` to
a **dedicated PostgreSQL test database** to run the same checks there; those tests
create tables and leave uniquely identified fixture records. PostgreSQL is not
required for the local suite, and live PostgreSQL validation is skipped unless
that variable is set.

## CPU practice players

The host can send a versioned `{"type": "add_cpu"}` command between hands. The
response includes `cpu_players`, whose IDs can be included in the next `start`
command. CPU seats persist in the game's JSON state, so no schema migration is
needed; existing games default to zero CPUs. CPU identities have no exposed login
token. At least one human must participate in each hand.

`server/ofc/cpu.py` provides a bounded, deterministic heuristic over legal
placements. It searches ordinary draws and uses a beam search for Fantasyland,
favouring pairs, lower-row flush/straight potential, valid boards, and royalties.
It receives only `public_view(game, cpu_id)`, not the private deck or opponents'
draws. It is intended for basic practice and can foul.

CPU replies are applied within the triggering command's transaction, stopping
at the next human turn. State, scoring, and the command receipt commit together,
so retries and reconnects cannot apply CPU moves twice or strand a CPU turn.
The frontend receives the resulting snapshot through the existing API/WebSocket
protocol. A command may advance several game versions when CPUs act.
# CPU strategy

## Trained CPU

`ofc/trained_cpu.py` exposes `TrainedCPU(path).choose_move(view, actor, rules)`, interchangeable with the other CPU move functions. It loads a trusted SB3 ZIP once, uses CPU inference, and reuses the exact observation encoder and action mask used in training.

Enable it locally from the repository root:

```sh
OFC_CPU_MODEL=/absolute/path/to/checkpoint.zip \
  uv run --directory server --extra trained-cpu uvicorn ofc.api:app --reload
```

With no `OFC_CPU_MODEL`, search remains the default. Invalid paths or incompatible observation/action dimensions fail at startup. Only load checkpoints produced by your trusted training pipeline; SB3 checkpoint loading is not a safe format for untrusted uploads.

The current models support two-player Pineapple with Fantasyland, moon and Candyland **disabled**. Other tables use the search/heuristic fallback automatically, including tables with more than two members. Turn timers do not change inference. The engine still validates each completed move. Existing 421-input/208-action checkpoints keep their encoding unchanged.

For direct use:

```python
from ofc.trained_cpu import TrainedCPU

cpu = TrainedCPU("/absolute/path/to/checkpoint.zip")
move = cpu.choose_move(view, actor, rules)
```

Inference dependencies are optional; the normal Docker image does not install them. A trained-model deployment needs the `trained-cpu` extra installed in both Docker sync steps, a checkpoint available on the machine, and `OFC_CPU_MODEL` pointing at it. Changing the checkpoint requires a backend restart.

Website CPUs use bounded Monte Carlo search on ordinary Pineapple turns: up to 16 heuristic-shortlisted candidate placements, 8 shared sampled futures each, scored by valid royalties and foul risk. Final draws are exhaustive. Classic and Fantasyland turns use the existing heuristic. The shared implementation is `ofc/search.py`; it uses only public information and requires no training dependencies. Moon/Candyland awards are approximated against an ordinary opponent; future Fantasyland value is not modelled. Restart or redeploy the backend to activate code changes.
