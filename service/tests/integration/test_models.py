import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Delivery, DeliveryStatus, Route, RouteLeg, Vehicle, VehicleStatus


@pytest.mark.parametrize("model", [Vehicle, Delivery, Route])
def test_model_columns_match_the_migrated_tables(db_engine, model):
    with db_engine.connect() as conn:
        cols = {r[0] for r in conn.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = :t"),
            {"t": model.__tablename__},
        )}
    assert cols == set(model.__table__.columns.keys())


def test_vehicle_defaults_come_from_the_database(clean_db):
    with Session(clean_db) as s, s.begin():
        v = Vehicle(current_lat=40.7, current_lon=-74.0)
        s.add(v)
        s.flush()
        s.refresh(v)
        assert v.status == "idle"
        assert isinstance(v.id, uuid.UUID)


def test_enum_values_match_the_check_constraints(clean_db):
    # a value the code defines but the database refuses would fail right here
    with Session(clean_db) as s, s.begin():
        for status in VehicleStatus:
            s.add(Vehicle(current_lat=40.7, current_lon=-74.0, status=status.value))
        for status in DeliveryStatus:
            vehicle = Vehicle(current_lat=40.7, current_lon=-74.0)
            s.add(vehicle)
            s.flush()
            delivery = Delivery(
                vehicle_id=vehicle.id,
                pickup_lat=40.70, pickup_lon=-74.00,
                dropoff_lat=40.71, dropoff_lon=-73.99,
                status=status.value,
            )
            s.add(delivery)
            s.flush()
            for leg in RouteLeg:
                s.add(Route(delivery_id=delivery.id, leg=leg.value, distance_m=1.0))
            s.flush()