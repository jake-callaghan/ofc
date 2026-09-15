"""production routing keeps static assets separate from authenticated game traffic."""

import pytest
from fastapi.testclient import TestClient

from ofc.web import create_app


def test_production_static_api_and_websocket(tmp_path):
    static = tmp_path / "dist"
    static.mkdir()
    (static / "index.html").write_text("<html>poker</html>")
    (static / "assets").mkdir()
    (static / "assets" / "app.js").write_text("console.log('poker')")
    database_url = f"sqlite:///{tmp_path / 'game.sqlite3'}"
    app = create_app(static_dir=static, database_url=database_url)
    with TestClient(app) as client:
        assert client.get("/").text == "<html>poker</html>"
        assert client.get("/assets/app.js").status_code == 200
        assert client.get("/assets/missing.js").status_code == 404
        assert client.get("/api/missing").status_code == 404
        assert client.get("/api/health").json() == {"status": "ok"}
        assert client.get("/api/docs").status_code == 200
        player = client.post("/api/players", json={"name": "Alice"}).json()
        response = client.post(
            "/api/games",
            json={"name": "Practice"},
            headers={"Authorization": f"Bearer {player['token']}"},
        )
        assert response.status_code == 201
        game_id = response.json()["game_id"]
        with client.websocket_connect(f"/api/games/{game_id}/events") as socket:
            socket.send_json({"token": player["token"]})
            assert socket.receive_json()["type"] == "snapshot"

    # restarting the production app must reopen the same persistent database.
    with TestClient(create_app(static_dir=static, database_url=database_url)) as client:
        response = client.get(
            f"/api/games/{game_id}",
            headers={"Authorization": f"Bearer {player['token']}"},
        )
        assert response.status_code == 200


def test_missing_build_fails_clearly(tmp_path):
    with pytest.raises(RuntimeError, match="frontend build missing"):
        create_app(static_dir=tmp_path)
