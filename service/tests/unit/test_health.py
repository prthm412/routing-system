import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def _settings(**overrides):
    values = dict(
        postgres_user="u", postgres_password="p", postgres_db="d",
        postgres_host="127.0.0.1", postgres_port=1,  # nothing listens here
        graph_path="/data/samples/tiny.graph",
    )
    values.update(overrides)
    return Settings(**values)


def test_health_reports_database_down_but_graph_loaded():
    with TestClient(create_app(_settings())) as client:
        res = client.get("/health")
    assert res.status_code == 503
    assert res.json() == {
        "status": "degraded",
        "database": "unavailable",
        "graph": {"nodes": 7, "edges": 13},
    }


def test_startup_fails_when_graph_file_is_missing():
    with pytest.raises(RuntimeError, match="cannot open"):
        with TestClient(create_app(_settings(graph_path="/no/such.graph"))):
            pass