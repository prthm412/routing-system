from contextlib import asynccontextmanager
from fastapi import FastAPI
import logging

from app.api import health, vehicles, deliveries
from app.config import Settings, get_settings
from app.core.engine_bridge import load_city
from app.db.session import create_db_engine, create_session_factory
from app.sim.scheduler import Simulation

def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    if settings.simulation_enabled:
        # uvicorn only configs its own loggers so show our INFO messages too
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.city = load_city(settings.graph_path)
        app.state.engine = create_db_engine(settings)
        app.state.session_factory = create_session_factory(app.state.engine)
        app.state.simulation = None
        if settings.simulation_enabled:
            simulation = Simulation(app.state.engine, app.state.session_factory, app.state.city, settings)
            if await simulation.start():
                app.state.simulation = simulation
        yield
        if app.state.simulation is not None:
            await app.state.simulation.stop()
        app.state.engine.dispose()

    app = FastAPI(title="Conduit", lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(vehicles.router)
    app.include_router(deliveries.router)
    return app