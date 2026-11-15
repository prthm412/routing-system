import logging
import math
import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.assignment import create_delivery
from app.db.session import create_session_factory
from app.models import Delivery, Vehicle
from app.schemas.geo import Point
from app.sim import vehicles as sim
from app.sim.vehicles import step_fleet

STEP_M = 17.0  # the legs below are 170 m on chain.graph, so 10 ticks per leg


def _coords(city, node):
    return city.coordinates([node])[0]


def _point(city, node):
    lat, lon = _coords(city, node)
    return Point(lat=lat, lon=lon)


def _request(engine, city, pickup_node, dropoff_node):
    with Session(engine) as session:
        return create_delivery(
            session, city, _point(city, pickup_node), _point(city, dropoff_node), 300.0
        )


def _vehicle_row(engine, vehicle_id):
    with Session(engine) as s:
        v = s.get(Vehicle, vehicle_id)
        return v.status, v.leg_progress_m, (v.current_lat, v.current_lon)


def _snapshot(engine, vehicle_id, delivery_id):
    with Session(engine) as s:
        v, d = s.get(Vehicle, vehicle_id), s.get(Delivery, delivery_id)
        return v.status, d.status, (v.current_lat, v.current_lon), v.leg_progress_m


def _run(engine, vehicle_id, delivery_id, ticks):
    factory = create_session_factory(engine)
    trace = []
    for _ in range(ticks):
        step_fleet(factory, STEP_M)
        trace.append(_snapshot(engine, vehicle_id, delivery_id))
    return trace


def _haversine_m(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 6_371_000.0 * math.asin(min(1.0, math.sqrt(h)))


def test_first_tick_moves_the_car_along_the_first_leg(clean_db, place_vehicle, city):
    vehicle = place_vehicle(0)
    delivery = _request(clean_db, city, 2, 4)
    assert step_fleet(create_session_factory(clean_db), STEP_M) == 1
    status, d_status, pos, progress = _snapshot(clean_db, vehicle, delivery)
    assert (status, d_status, progress) == ("to_pickup", "assigned", 17.0)
    # 17 of 170 m is a tenth of the way from node 0 to node 2, due east
    assert pos == pytest.approx((40.7300, -73.9898), abs=1e-9)


def test_trip_goes_through_every_status_in_order(clean_db, place_vehicle, city):
    vehicle = place_vehicle(0)
    delivery = _request(clean_db, city, 2, 4)
    trace = _run(clean_db, vehicle, delivery, 20)
    assert [(v, d) for v, d, _, _ in trace] == (
        [("to_pickup", "assigned")] * 9
        + [("to_dropoff", "picked_up")] * 10
        + [("idle", "delivered")]
    )


def test_the_pickup_cannot_be_skipped(clean_db, place_vehicle, city):
    vehicle = place_vehicle(0)
    delivery = _request(clean_db, city, 2, 4)
    trace = _run(clean_db, vehicle, delivery, 20)
    first_dropoff_leg = next(i for i, t in enumerate(trace) if t[0] == "to_dropoff")
    assert first_dropoff_leg == 9  # tick 10: the car has driven the whole first leg
    assert trace[first_dropoff_leg][2] == pytest.approx(_coords(city, 2), abs=1e-9)
    for _, d_status, pos, _ in trace[:first_dropoff_leg]:
        assert d_status == "assigned"
        assert pos != pytest.approx(_coords(city, 2), abs=1e-9)


def test_car_ends_exactly_on_the_dropoff_node_and_is_idle_again(clean_db, place_vehicle, city):
    vehicle = place_vehicle(0)
    delivery = _request(clean_db, city, 2, 4)
    trace = _run(clean_db, vehicle, delivery, 20)
    status, d_status, pos, progress = trace[-1]
    assert (status, d_status, progress) == ("idle", "delivered", 0.0)
    assert pos == pytest.approx(_coords(city, 4), abs=1e-9)
    assert city.snap(*pos).distance_m < 1e-3
    assert step_fleet(create_session_factory(clean_db), STEP_M) == 0  # idle cars are not touched


def test_a_car_never_jumps_more_than_one_step(clean_db, place_vehicle, city):
    vehicle = place_vehicle(0)
    delivery = _request(clean_db, city, 2, 4)
    last = _coords(city, 0)
    for _, _, pos, _ in _run(clean_db, vehicle, delivery, 20):
        assert _haversine_m(last, pos) <= STEP_M + 1e-6
        last = pos


def test_a_vehicle_already_at_the_pickup_still_passes_through_picked_up(
    clean_db, place_vehicle, city
):
    vehicle = place_vehicle(2)  # standing on the pickup node
    delivery = _request(clean_db, city, 2, 4)
    trace = _run(clean_db, vehicle, delivery, 11)
    assert trace[0][:2] == ("to_dropoff", "picked_up")
    assert trace[0][2] == pytest.approx(_coords(city, 2), abs=1e-9)
    assert trace[0][3] == 0.0
    assert [t[:2] for t in trace[1:10]] == [("to_dropoff", "picked_up")] * 9
    assert trace[10][:2] == ("idle", "delivered")


def test_the_vehicle_can_take_a_new_delivery_after_delivering(clean_db, place_vehicle, city):
    vehicle = place_vehicle(0)
    first = _request(clean_db, city, 2, 4)
    _run(clean_db, vehicle, first, 20)
    second = _request(clean_db, city, 5, 3)  # the car is idle on node 4 now
    with Session(clean_db) as s:
        assert s.get(Delivery, second).vehicle_id == vehicle
        assert s.get(Delivery, first).status == "delivered"
        assert s.get(Vehicle, vehicle).status == "to_pickup"


def test_a_busy_vehicle_without_a_delivery_is_logged_and_skipped(
    clean_db, place_vehicle, city, caplog
):
    vehicle = place_vehicle(0, "to_pickup")
    with caplog.at_level(logging.WARNING, logger="app.sim.vehicles"):
        moved = step_fleet(create_session_factory(clean_db), STEP_M)
    assert moved == 0
    status, progress, pos = _vehicle_row(clean_db, vehicle)
    assert (status, progress) == ("to_pickup", 0.0)
    assert pos == pytest.approx(_coords(city, 0), abs=1e-9)
    assert "no matching delivery" in caplog.text
    assert str(vehicle) in caplog.text


def test_a_vehicle_whose_delivery_is_in_the_wrong_state_is_skipped(
    clean_db, place_vehicle, city, caplog
):
    vehicle = place_vehicle(0)
    _request(clean_db, city, 2, 4)  # the delivery is 'assigned'
    with clean_db.begin() as conn:
        conn.execute(
            text("UPDATE vehicles SET status = 'to_dropoff' WHERE id = :id"), {"id": vehicle}
        )
    with caplog.at_level(logging.WARNING, logger="app.sim.vehicles"):
        moved = step_fleet(create_session_factory(clean_db), STEP_M)
    assert moved == 0
    assert _vehicle_row(clean_db, vehicle)[:2] == ("to_dropoff", 0.0)
    assert "no matching delivery" in caplog.text


def test_one_failing_vehicle_does_not_stop_the_others(
    clean_db, place_vehicle, city, monkeypatch, caplog
):
    place_vehicle(0)
    place_vehicle(5)
    _request(clean_db, city, 1, 3)  # the car at node 0 is nearest
    _request(clean_db, city, 4, 2)  # the car at node 5 is nearest of those left
    real = sim.position_on_line
    calls = []

    def fail_on_the_first_call(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return real(*args, **kwargs)

    monkeypatch.setattr(sim, "position_on_line", fail_on_the_first_call)
    with caplog.at_level(logging.ERROR, logger="app.sim.vehicles"):
        moved = step_fleet(create_session_factory(clean_db), STEP_M)
    assert moved == 1
    with Session(clean_db) as s:
        assert sorted(s.scalars(select(Vehicle.leg_progress_m)).all()) == [0.0, STEP_M]
    assert "boom" in caplog.text  # the failed car was rolled back and logged


def test_idle_vehicles_are_never_touched(clean_db, place_vehicle, city):
    nodes = (0, 3, 5)
    ids = [place_vehicle(n) for n in nodes]
    assert step_fleet(create_session_factory(clean_db), STEP_M) == 0
    for vehicle, node in zip(ids, nodes):
        status, progress, pos = _vehicle_row(clean_db, vehicle)
        assert (status, progress) == ("idle", 0.0)
        assert pos == pytest.approx(_coords(city, node), abs=1e-9)