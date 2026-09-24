"""share database polling among connected viewers without sharing private views."""

import asyncio
import time
from contextlib import asynccontextmanager

from fastapi.concurrency import run_in_threadpool


class GameUpdates:
    def __init__(self, store, *, interval=0.5, clock=time.monotonic):
        self.store = store
        self.interval = interval
        self.clock = clock
        self.games = {}

    @asynccontextmanager
    async def subscribe(self, game_id):
        entry = self.games.setdefault(
            game_id,
            {"users": 0, "lock": asyncio.Lock(), "snapshot": None, "checked": 0},
        )
        entry["users"] += 1
        try:
            yield entry
        finally:
            entry["users"] -= 1
            if not entry["users"]:
                del self.games[game_id]

    async def get(self, game_id, entry, actor):
        async with entry["lock"]:
            if (
                entry["snapshot"] is None
                or self.clock() - entry["checked"] >= self.interval
            ):
                # periodically reload names too, in case an account was renamed.
                previous = entry["snapshot"]
                if self.clock() - entry.get("metadata_checked", 0) >= 30:
                    previous = None
                snapshot = await run_in_threadpool(
                    self.store.shared_snapshot, game_id, previous
                )
                if snapshot is not entry["snapshot"]:
                    entry["metadata_checked"] = self.clock()
                entry["snapshot"] = snapshot
                entry["checked"] = self.clock()
            # membership and hidden cards are checked separately for every viewer.
            return self.store.snapshot_view(game_id, entry["snapshot"], actor)
