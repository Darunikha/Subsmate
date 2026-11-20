import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db


@pytest.fixture()
def spa_client(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>app shell</html>")
    (tmp_path / "assets" / "main.js").write_text("console.log(1)")

    class Config(TestConfig):
        FRONTEND_DIST = str(tmp_path)

    app = create_app(Config)
    with app.app_context():
        yield app.test_client()
        db.session.remove()
        db.engine.dispose()


def test_root_and_client_routes_serve_the_app_shell(spa_client):
    assert b"app shell" in spa_client.get("/").data
    assert b"app shell" in spa_client.get("/subscriptions/3").data


def test_static_assets_are_served(spa_client):
    response = spa_client.get("/assets/main.js")
    assert response.status_code == 200
    assert b"console.log" in response.data


def test_api_routes_still_work_and_unknown_api_paths_return_json_404(spa_client):
    assert spa_client.get("/api/health").get_json() == {"status": "ok"}
    missing = spa_client.get("/api/does-not-exist")
    assert missing.status_code == 404
    assert missing.is_json
    assert spa_client.get("/metrics").status_code == 200


def test_without_frontend_dist_root_is_not_served(client):
    assert client.get("/").status_code == 404
