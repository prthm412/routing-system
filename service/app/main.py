from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.api import health, vehicles
from app.config import Settings, get_settings
from app.core.engine_bridge import load_city
from app.db.session import create_db_engine, create_session_factory

def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.city = load_city(settings.graph_path)
        app.state.engine = create_db_engine(settings)
        app.state.session_factory = create_session_factory(app.state.engine)
        yield
        app.state.engine.dispose()

    app = FastAPI(title="Conduit", lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(vehicles.router)
    return app