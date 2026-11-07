import pytest
from pydantic import ValidationError

from app.config import Settings

ENV_NAMES = [
    "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "POSTGRES_HOST",
    "POSTGRES_PORT", "GRAPH_PATH", "MAX_SNAP_DISTANCE_M", "FLEET_SIZE", "FLEET_SEED",
]


@pytest.fixture
def env(monkeypatch):
    # start from a known environment, whatever compose put in the container
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("POSTGRES_USER", "conduit")
    monkeypatch.setenv("POSTGRES_PASSWORD", "change-me")
    monkeypatch.setenv("POSTGRES_DB", "conduit")
    return monkeypatch

def test_database_url_defaults(env):
    url = Settings().database_url()
    assert url.drivername == "postgresql+psycopg"
    assert (url.host, url.port) == ("db", 5432)
    assert (url.username, url.password, url.database) == ("conduit", "change-me", "conduit")


def test_database_url_escapes_special_characters(env):
    env.setenv("POSTGRES_PASSWORD", "p@ss/w:rd")
    url = Settings().database_url()
    assert url.password == "p@ss/w:rd"
    assert "p%40ss%2Fw%3Ard" in url.render_as_string(hide_password=False)


def test_database_url_can_swap_database_name(env):
    url = Settings().database_url("conduit_test_abc")
    assert url.database == "conduit_test_abc"
    assert url.username == "conduit"


def test_missing_password_is_an_error(env):
    env.delenv("POSTGRES_PASSWORD")
    with pytest.raises(ValidationError):
        Settings()


def test_defaults_for_graph_and_snap_limit(env):
    s = Settings()
    assert s.graph_path == "/data/processed/nyc.graph"
    assert s.max_snap_distance_m == 300.0


def test_snap_limit_can_be_overridden_by_env(env):
    env.setenv("MAX_SNAP_DISTANCE_M", "250")
    assert Settings().max_snap_distance_m == 250.0

def test_fleet_defaults(env):
    s = Settings()
    assert (s.fleet_size, s.fleet_seed) == (5, 42)