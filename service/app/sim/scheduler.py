"""Starts and stops the simulation: one scheduler per database, two asyncio loops."""
import asyncio
import logging
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.core.engine_bridge import City
from app.sim.delivery_generator import RequestGenerator, request_delivery
from app.sim.vehicles import step_fleet

log = logging.getLogger(__name__)

# Any number works, as long as every process uses the same.
# Postgres keeps advisory locks per database, so tests on conduit_test_* never meet the dev app
SIMULATOR_LOCK_KEY = 7_283_419

class SimulatorLock:
    """Postgres session level advisory lock on its own connection.
       Held until release() is called or the connection dies, so a crashed process frees it by itself."""

    def __init__(self, engine: Engine, key: int = SIMULATOR_LOCK_KEY) -> None:
        self._engine = engine
        self._key = key
        self._conn = None

    def acquire(self) -> bool:
        """True if we now hold the lock, False if another process holds it."""
        if self._conn is not None:
            return True
        conn = self._engine.connect().execution_options(isolation_level="AUTOCOMMIT")
        try:
            got = conn.execute(text("SELECT pg_try_advisory_lock(CAST(:key AS bigint))"), {"key": self._key}).scalar()
        except BaseException:
            conn.close()
            raise
        if not got:
            conn.close()
            return False
        self._conn = conn
        return True

    def release(self) -> None:
        """Give the lock back. Safe to call when we don't hold it."""
        conn, self._conn = self._conn, None
        if conn is None:
            return
        try:
            conn.execute(text("SELECT pg_advisory_unlock(CAST(:key AS bigint))"), {"key": self._key})
        except Exception:
            # a pooled connection must never keep the lock, so drop the connection itself
            log.exception("could not release the simulator lock; closing its connection")
            conn.invalidate()
        finally:
            conn.close()

class Simulation:
    """The vehicle loop and the request-generator loop, started once, stopped cleanly."""
    def __init__(self, engine: Engine, session_factory: sessionmaker[Session], city: City, settings: Settings) -> None:
        self._session_factory = session_factory
        self._city = city
        self._settings = settings
        self._lock = SimulatorLock(engine)
        # built here so bad settings fail before the lock is taken
        self._generator = RequestGenerator(
            city, settings.generator_seed, settings.generator_min_interval_s,
            settings.generator_max_interval_s,
        )
        self._stop: asyncio.Event | None = None
        self._tasks: list[asyncio.Task] = []

    @property
    def tasks(self) -> list[asyncio.Task]:
        return list(self._tasks)

    async def start(self) -> bool:
        """Take the lock and start both loops.
           False if another process alreay runs the simulation or the database could not be reached."""
        if self._tasks:
            return True
        try:
            got = await asyncio.to_thread(self._lock.acquire)
        except SQLAlchemyError:
            log.exception("simulation not started: could not take the simulator lock")
            return False
        if not got:
            log.warning("simulation not started: another process already runs it")
            return False
        self._stop = asyncio.Event()
        self._tasks = [
            asyncio.create_task(self._vehicle_loop(), name="sim-vehicles"),
            asyncio.create_task(self._generator_loop(), name="sim-generator"),
        ]
        log.info(
            "simulation started: %.1f m/s, tick %.2f s", self._settings.vehicle_speed_mps,
            self._settings.sim_tick_s,
        )
        return True

    async def stop(self, timeout_s: float = 10.0) -> None:
        """Ask both loops to finish their current step, cancel any that take longer than
           `timeout_s`, then give the lock back. Safe to call twice or before start."""
        if self._stop is not None:
            self._stop.set()
        if self._tasks:
            _, pending = await asyncio.wait(self._tasks, timeout=timeout_s)
            for task in pending:
                task.cancel()
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks = []
        await asyncio.to_thread(self._lock.release)
        log.info("simulation stopped")

    async def _sleep(self, seconds: float) -> None:
        """Sleep, but wake up at once when stop() is called."""
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
        except TimeoutError:
            pass

    async def _vehicle_loop(self) -> None:
        loop = asyncio.get_running_loop()
        tick_s = self._settings.sim_tick_s
        step_m = self._settings.vehicle_speed_mps * tick_s  # a fixed step per tick
        while not self._stop.is_set():
            started = loop.time()
            try:
                await asyncio.to_thread(step_fleet, self._session_factory, step_m)
            except Exception:
                log.exception("vehicle tick failed; carrying on")
            await self._sleep(max(0.0, tick_s - (loop.time() - started)))

    async def _generator_loop(self) -> None:
        while not self._stop.is_set():
            await self._sleep(self._generator.next_interval_s())
            if self._stop.is_set():
                break
            try:
                trip = self._generator.next_trip()
                await asyncio.to_thread(
                    request_delivery, self._session_factory, self._city, trip,
                    self._settings.max_snap_distance_m,
                )
            except Exception:
                log.exception("generator step failed; carrying on")