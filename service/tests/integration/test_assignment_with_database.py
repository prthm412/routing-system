import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import assignment
from app.core.assignment import claim_first_available, create_delivery
from app.core.planning import Candidate, Leg
from app.models import Delivery, Vehicle
from app.schemas.geo import Point


def _candidates(ids):
    return [Candidate(i, Leg(10.0 * n, [0])) for n, i in enumerate(ids)]


def _status(engine, vehicle_id):
    with Session(engine) as s:
        return s.get(Vehicle, vehicle_id).status


def _set_status(engine, vehicle_id, status):
    with Session(engine) as s, s.begin():
        s.get(Vehicle, vehicle_id).status = status


def test_claim_takes_the_first_candidate(clean_db, place_vehicle):
    a, b = place_vehicle(0), place_vehicle(1)
    with Session(clean_db) as s, s.begin():
        chosen = claim_first_available(s, _candidates([a, b]))
    assert chosen.vehicle_id == a
    assert (_status(clean_db, a), _status(clean_db, b)) == ("to_pickup", "idle")


def test_claim_skips_a_vehicle_that_is_no_longer_idle(clean_db, place_vehicle):
    a, b = place_vehicle(0), place_vehicle(1)
    _set_status(clean_db, a, "to_dropoff")  # taken after the ranking was made
    with Session(clean_db) as s, s.begin():
        chosen = claim_first_available(s, _candidates([a, b]))
    assert chosen.vehicle_id == b
    assert (_status(clean_db, a), _status(clean_db, b)) == ("to_dropoff", "to_pickup")


def test_claim_returns_none_when_everyone_is_taken(clean_db, place_vehicle):
    a, b = place_vehicle(0, "to_pickup"), place_vehicle(1, "to_dropoff")
    with Session(clean_db) as s, s.begin():
        assert claim_first_available(s, _candidates([a, b])) is None


def test_failure_after_the_claim_rolls_the_claim_back(clean_db, place_vehicle, city, monkeypatch):
    vehicle = place_vehicle(0)

    def boom(coords):
        raise RuntimeError("insert failed")

    monkeypatch.setattr(assignment, "linestring_wkt", boom)
    (lat1, lon1), (lat3, lon3) = city.coordinates([1])[0], city.coordinates([3])[0]
    with Session(clean_db) as s:
        with pytest.raises(RuntimeError, match="insert failed"):
            create_delivery(s, city, Point(lat=lat1, lon=lon1), Point(lat=lat3, lon=lon3), 300.0)
    assert _status(clean_db, vehicle) == "idle"
    with Session(clean_db) as s:
        assert s.scalar(select(func.count()).select_from(Delivery)) == 0