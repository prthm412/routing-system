from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.config import Settings

def create_db_engine(settings: Settings) -> Engine:
    # create_engine does not connect yet, so app starts even if the db is down
    return create_engine(settings.database_url(), pool_pre_ping=True)