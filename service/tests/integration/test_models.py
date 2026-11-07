import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.vehicle import Vehicle


def test_vehicle_columns_match_the_migrated_table(db_engine):
    with db_engine.connect() as conn:
        cols = {r[0] for r in conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'vehicles'"
        ))}
    assert cols == set(Vehicle.__table__.columns.keys())


def test_vehicle_defaults_come_from_the_database(clean_db):
    with Session(clean_db) as s, s.begin():
        v = Vehicle(current_lat=40.7, current_lon=-74.0)
        s.add(v)
        s.flush()
        s.refresh(v)
        assert v.status == "idle"
        assert isinstance(v.id, uuid.UUID)