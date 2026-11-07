import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from fastapi.testclient import TestClient

from app.config import Settings
from app.core.engine_bridge import load_city
from app.main import create_app

SERVICE_DIR = Path(__file__).resolve().parents[2]


@contextmanager
def temporary_database(settings: Settings):
    """Create an empty database named conduit_test_<random>, drop it afterwards."""
    name = f"conduit_test_{uuid.uuid4().hex[:8]}"
    admin = create_engine(settings.database_url("postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
        try:
            yield settings.database_url(name)
        finally:
            with admin.connect() as conn:
                conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
    finally:
        admin.dispose()


@pytest.fixture(scope="session")
def settings():
    return Settings(graph_path="/data/samples/tiny.graph")


@pytest.fixture(scope="session")
def alembic_cfg():
    def make(url):
        cfg = Config(str(SERVICE_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(SERVICE_DIR / "alembic"))
        cfg.attributes["url"] = url
        return cfg

    return make


@pytest.fixture(scope="session")
def temp_db_url(settings, alembic_cfg):
    """One temporary database for the whole run, built by the real migrations."""
    with temporary_database(settings) as url:
        command.upgrade(alembic_cfg(url), "head")
        yield url


@pytest.fixture
def empty_db_url(settings):
    """A fresh, empty temporary database for one test."""
    with temporary_database(settings) as url:
        yield url


@pytest.fixture(scope="session")
def db_engine(temp_db_url):
    # safety guard: never hand out an engine for anything but a test database
    assert temp_db_url.database.startswith("conduit_test_")
    engine = create_engine(temp_db_url)
    yield engine
    engine.dispose()


@pytest.fixture
def clean_db(db_engine):
    with db_engine.begin() as conn:
        conn.execute(text("TRUNCATE routes, deliveries, vehicles"))
    return db_engine

@pytest.fixture(scope="session")
def city(settings):
    return load_city(settings.graph_path)


@pytest.fixture
def client(settings, clean_db):
    """The real app, pointed at the temporary database (tables emptied first)."""
    assert clean_db.url.database.startswith("conduit_test_")
    test_settings = settings.model_copy(update={"postgres_db": clean_db.url.database})
    with TestClient(create_app(test_settings)) as c:
        yield c