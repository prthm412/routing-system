import threading
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core import assignment
from app.core.assignment import create_delivery
from app.core.errors import DomainError
from app.models import Delivery, Route, Vehicle
from app.schemas.geo import Point

def _race(engine, city, threads, monkeypatch):
    """Run `threads` requests at  once. Each one ranks its candidates then waits at
       a barrier so every requet has seen the same idle vehicles before any claim happens"""
    barrier = threading.Barrier(threads, timeout=30)
    real_rank = assignment.rank_candidates

    def rank_then_wait(*args, **kwargs):
        ranked = real_rank(*args, **kwargs)
        barrier.wait()
        return ranked

    monkeypatch.setattr(assignment, "rank_candidates", rank_then_wait)

    plat, plon = city.coordinates([1])[0]
    dlat, dlon = city.coordinates([3])[0]
    pickup, dropoff = Point(lat=plat, lon=plon), Point(lat=dlat, lon=dlon)
    factory = sessionmaker(engine, expire_on_commit=False)
    outcomes = []

    def one_request():
        with factory() as session:
            try:
                outcomes.append(("created", create_delivery(session, city, pickup, dropoff, 300.0)))
            except DomainError as err:
                outcomes.append(("rejected", err.code, err.message))
            except Exception as err:    # anything else is bug
                outcomes.append(("error", repr(err)))

    workers = [threading.Thread(target=one_request) for _ in range(threads)]
    for w in workers:
        w.start()
    for w in workers:
        w.join(timeout=60)
    return outcomes


def test_eight_requests_for_one_idle_vehicle_create_exactly_one_delivery(
        clean_db, place_vehicle, city, monkeypatch
):
    vehicle = place_vehicle(0)
    outcomes = _race(clean_db, city, 8, monkeypatch)
    assert sorted(o[0] for o in outcomes) == ["created"] + ["rejected"] * 7
    for o in outcomes:
        if o[0] == "rejected":
            assert o[1] == "no_idle_vehicle"
            assert "taken by another request" in o[2]   # lost the claim
    with Session(clean_db) as s:
        assert s.scalar(select(func.count()).select_from(Delivery)) == 1
        assert s.scalar(select(func.count()).select_from(Route)) == 2
        assert s.get(Vehicle, vehicle).status == "to_pickup"


def test_four_requests_for_two_idle_vehicles_use_each_vehicle_once(
        clean_db, place_vehicle, city, monkeypatch
):
    a, b = place_vehicle(0), place_vehicle(5)
    outcomes = _race(clean_db, city, 4, monkeypatch)
    assert sorted(o[0] for o in outcomes) == ["created", "created", "rejected", "rejected"]
    with Session(clean_db) as s:
        used = s.scalars(select(Delivery.vehicle_id)).all()
        statuses = s.scalars(select(Vehicle.status)).all()
        routes = s.scalar(select(func.count()).select_from(Route))
    assert sorted(used) == sorted([a, b])
    assert statuses == ["to_pickup", "to_pickup"]
    assert routes == 4