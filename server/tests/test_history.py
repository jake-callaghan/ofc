"""completed history is visible to spectators and paginates newest first."""

from db_helpers import create_app
from fastapi.testclient import TestClient

from ofc.rules import Rules


def test_spectator_history_pagination_and_auth(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'history.sqlite3'}")
    with TestClient(app) as client:
        store = app.state.store
        owner = store.register("owner")
        spectator = store.register("spectator")
        gid = store.create(owner["player_id"], "history", Rules())["game_id"]
        with store.repository.transaction(write=True) as uow:
            for number in range(1, 54):
                uow.record_hand(
                    gid,
                    {
                        "number": number,
                        "result": {"units": {owner["player_id"]: 0}},
                        "boards": {},
                    },
                    {},
                )
        url = f"/games/{gid}/hands"
        assert client.get(url).status_code == 401
        headers = {"Authorization": f"Bearer {spectator['token']}"}
        first = client.get(url + "?newest=true&limit=50", headers=headers).json()
        assert [h["number"] for h in first] == list(range(53, 3, -1))
        older = client.get(url + "?newest=true&before=4", headers=headers).json()
        assert [h["number"] for h in older] == [3, 2, 1]
        assert client.get(url + "?after=52", headers=headers).json() == first[:1]
