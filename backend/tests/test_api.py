from fastapi.testclient import TestClient

from app.api import create_app


def test_health(tmp_path):
    app = create_app(db_path=str(tmp_path / "t.db"))
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
