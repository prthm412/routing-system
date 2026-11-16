import asyncio
import logging
import threading
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.assignment import create_delivery
from app.db.session import create_db_engine, create_session_factory
from app.main import create_app
from app.models import Delivery, Vehicle
from app.schemas.geo import Point
from app.sim import scheduler as sched
from app.sim.scheduler import SIMULATOR_LOCK_KEY, Simulation, SimulatorLock

LOGGER = "app.sim.scheduler"


def _point(city, node):
    lat, lon = city.coordinates([node])[0]
    return Point(lat=lat, lon=lon)


def _sim_settings(settings, engine, **overrides):
    values = {
        "postgres_db": engine.url.database,
        "simulation_enabled": True,
        "sim_tick_s": 0.05,
        "vehicle_speed_mps": 340.0,  # 17 m per tick, so a 170 m leg takes 10 ticks
        "generator_min_interval_s": 3600.0,  # no random customer during a test
        "generator_max_interval_s": 3600.0,
    }
    values.update(overrides)
    return settings.model_copy(update=values)


def _simulation(engine, city, settings):
    return Simulation(
        engine, create_session_factory(engine), city, _sim_settings(settings, engine)
    )


def _lock_is_free(engine):
    """Ask from a brand-new connection with no pool, so a lock still held by a pooled
    connection can't hide."""
    probe = create_engine(engine.url, poolclass=NullPool)
    try:
        with probe.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            got = conn.execute(
                text("SELECT pg_try_advisory_lock(CAST(:k AS bigint))"), {"k": SIMULATOR_LOCK_KEY}
            ).scalar()
            if got:
                conn.execute(
                    text("SELECT pg_advisory_unlock(CAST(:k AS bigint))"), {"k": SIMULATOR_LOCK_KEY}
                )
            return bool(got)
    finally:
        probe.dispose()


# the lock


def test_the_second_holder_is_refused_until_the_first_releases(db_engine):
    first, second = SimulatorLock(db_engine), SimulatorLock(db_engine)
    try:
        assert first.acquire() is True
        assert second.acquire() is False
        assert _lock_is_free(db_engine) is False
        first.release()
        assert _lock_is_free(db_engine) is True
        assert second.acquire() is True
    finally:
        first.release()
        second.release()


def test_lock_spaces_are_per_database(db_engine, empty_db_url):
    other = create_engine(empty_db_url)
    first, second = SimulatorLock(db_engine), SimulatorLock(other)
    try:
        assert first.acquire() is True
        assert second.acquire() is True  # same key, different database
    finally:
        first.release()
        second.release()
        other.dispose()


# the loops


def test_start_and_stop_run_and_end_both_loops_cleanly(clean_db, city, settings):
    async def scenario():
        sim = _simulation(clean_db, city, settings)
        try:
            assert await sim.start() is True
            tasks = sim.tasks
            assert len(tasks) == 2
            await asyncio.sleep(0.2)
            assert not any(t.done() for t in tasks)
        finally:
            await sim.stop()
        return tasks

    tasks = asyncio.run(scenario())
    assert all(t.done() and not t.cancelled() for t in tasks)
    assert _lock_is_free(clean_db)


def test_a_second_simulation_on_the_same_database_does_not_start(clean_db, city, settings):
    async def scenario():
        first = _simulation(clean_db, city, settings)
        second = _simulation(clean_db, city, settings)
        try:
            assert await first.start() is True
            assert await second.start() is False
            assert second.tasks == []
            await first.stop()
            assert await second.start() is True  # the key was handed back
        finally:
            await first.stop()
            await second.stop()

    asyncio.run(scenario())
    assert _lock_is_free(clean_db)


def test_stop_cancels_a_tick_that_will_not_finish(clean_db, city, settings, monkeypatch):
    started = threading.Event()

    def stuck_tick(session_factory, step_m):
        started.set()
        time.sleep(0.5)
        return 0

    monkeypatch.setattr(sched, "step_fleet", stuck_tick)

    async def scenario():
        sim = _simulation(clean_db, city, settings)
        try:
            assert await sim.start() is True
            tasks = sim.tasks
            deadline = time.monotonic() + 5
            while not started.is_set() and time.monotonic() < deadline:
                await asyncio.sleep(0.01)
            assert started.is_set()
        finally:
            await sim.stop(timeout_s=0.05)
        return tasks

    vehicles_task, generator_task = asyncio.run(scenario())
    assert vehicles_task.cancelled()  # still inside its tick when the time ran out
    assert generator_task.done() and not generator_task.cancelled()
    assert _lock_is_free(clean_db)


def test_a_failing_tick_is_logged_and_the_loop_keeps_going(
    clean_db, city, settings, monkeypatch, caplog
):
    calls = []

    def flaky_tick(session_factory, step_m):
        calls.append(step_m)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return 0

    monkeypatch.setattr(sched, "step_fleet", flaky_tick)

    async def scenario():
        sim = _simulation(clean_db, city, settings)
        try:
            assert await sim.start() is True
            deadline = time.monotonic() + 5
            while len(calls) < 3 and time.monotonic() < deadline:
                await asyncio.sleep(0.01)
        finally:
            await sim.stop()

    with caplog.at_level(logging.ERROR, logger=LOGGER):
        asyncio.run(scenario())
    assert len(calls) >= 3
    assert calls[0] == pytest.approx(17.0)
    assert "boom" in caplog.text


def test_start_returns_false_when_the_database_is_unreachable(city, settings, caplog):
    bad = _sim_settings(
        settings, create_engine("postgresql+psycopg://u:p@127.0.0.1:1/d"),
        postgres_host="127.0.0.1", postgres_port=1,
    )
    engine = create_db_engine(bad)  # nothing listens on port 1

    async def scenario():
        sim = Simulation(engine, create_session_factory(engine), city, bad)
        return await sim.start(), sim.tasks

    try:
        with caplog.at_level(logging.ERROR, logger=LOGGER):
            started, tasks = asyncio.run(scenario())
    finally:
        engine.dispose()
    assert started is False
    assert tasks == []
    assert "could not take the simulator lock" in caplog.text


# the app


def test_the_app_runs_no_simulation_by_default(client):
    assert client.app.state.simulation is None


def test_cars_move_when_the_app_runs_with_simulation_enabled(
    clean_db, place_vehicle, city, settings
):
    vehicle = place_vehicle(0)
    with Session(clean_db) as s:
        delivery_id = create_delivery(s, city, _point(city, 2), _point(city, 4), 300.0)
    with TestClient(create_app(_sim_settings(settings, clean_db))) as client:
        assert client.app.state.simulation is not None
        deadline = time.monotonic() + 15
        status = None
        while time.monotonic() < deadline:
            with Session(clean_db) as s:
                status = s.get(Delivery, delivery_id).status
            if status == "delivered":
                break
            time.sleep(0.05)
        assert status == "delivered"
    with Session(clean_db) as s:
        v = s.get(Vehicle, vehicle)
        assert (v.status, v.leg_progress_m) == ("idle", 0.0)
        assert (v.current_lat, v.current_lon) == pytest.approx(city.coordinates([4])[0], abs=1e-9)
    assert _lock_is_free(clean_db)


def test_a_second_app_on_the_same_database_does_not_start_the_simulation(clean_db, settings):
    app_settings = _sim_settings(settings, clean_db)
    with TestClient(create_app(app_settings)) as first:
        with TestClient(create_app(app_settings)) as second:
            assert first.app.state.simulation is not None
            assert second.app.state.simulation is None
            assert second.get("/health").status_code == 200  # it still serves the API
    assert _lock_is_free(clean_db)