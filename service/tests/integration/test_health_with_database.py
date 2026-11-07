from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_ok_when_database_is_up():
    settings = Settings(graph_path="/data/samples/tiny.graph")
    with TestClient(create_app(settings)) as client:
        res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {
        "status": "ok",
        "database": "ok",
        "graph": {"nodes": 7, "edges": 13},
    }