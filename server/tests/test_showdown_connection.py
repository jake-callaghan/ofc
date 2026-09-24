"""postgres bigint totals must remain serializable when a hand reaches showdown."""

from decimal import Decimal
from uuid import uuid4

from db_helpers import create_app
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from test_engine import auto_command

from ofc.rules import Rules


def test_websocket_survives_showdown_and_next_hand(tmp_path, monkeypatch):
    execute = Session.execute

    def postgres_totals(session, statement, *args, **kwargs):
        result = execute(session, statement, *args, **kwargs)
        if "sum(ledger.units)" not in str(statement):
            return result
        # postgres sum(bigint) returns numeric, which psycopg exposes as decimal.
        rows = [(player, Decimal(units)) for player, units in result.all()]

        class Totals:
            def all(self):
                return rows

        return Totals()

    monkeypatch.setattr(Session, "execute", postgres_totals)
    app = create_app(f"sqlite:///{tmp_path / 'showdown.sqlite3'}")
    with TestClient(app) as client:
        app.state.updates.interval = 0
        a = client.post("/players", json={"name": "alice"}).json()
        b = client.post("/players", json={"name": "bob"}).json()
        store = app.state.store
        created = store.create(a["player_id"], "showdown", Rules())
        gid = created["game_id"]
        store.join(gid, b["player_id"], "join", created["invite"])
        with client.websocket_connect(f"/games/{gid}/events") as ws:
            ws.send_json({"token": a["token"]})
            snapshot = ws.receive_json()["state"]
            for number in (1, 2):
                store.command(
                    gid,
                    a["player_id"],
                    str(uuid4()),
                    snapshot["version"],
                    {"type": "start", "players": [a["player_id"], b["player_id"]]},
                )
                with store.repository.transaction() as uow:
                    state = uow.get_game(gid).state
                while state["hand"]["status"] != "complete":
                    actor, move = auto_command(state)
                    store.command(gid, actor, str(uuid4()), state["version"], move)
                    with store.repository.transaction() as uow:
                        state = uow.get_game(gid).state
                while snapshot["version"] < state["version"]:
                    snapshot = ws.receive_json()["state"]
                assert snapshot["hand"]["status"] == "complete"
                assert snapshot["hand"]["number"] == number
                assert all(
                    type(value) is int for value in snapshot["balances"].values()
                )
                assert len(store.history(gid, a["player_id"])) == number
