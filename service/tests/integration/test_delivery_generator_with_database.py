import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import create_session_factory
from app.models import Delivery, Vehicle
from app.schemas.geo import Point
from app.sim import delivery_generator as gen_module
from app.sim.delivery_generator import RequestGenerator, request_delivery

LOGGER = "app.sim.delivery_generator"


def _point(city, node):
    lat, lon = city.coordinates([node])[0]
    return Point(lat=lat, lon=lon)


def _trip(city, pickup_node, dropoff_node):
    return _point(city, pickup_node), _point(city, dropoff_node)


def _count(engine, model):
    with Session(engine) as s:
        return s.scalar(select(func.count()).select_from(model))


def _ours(caplog):
    return [r for r in caplog.records if r.name == LOGGER]


def test_a_generated_request_goes_through_create_delivery(clean_db, place_vehicle, city):
    vehicle = place_vehicle(0)
    factory = create_session_factory(clean_db)
    delivery_id = request_delivery(factory, city, _trip(city, 1, 3), 300.0)
    assert delivery_id is not None
    with Session(clean_db) as s:
        delivery = s.get(Delivery, delivery_id)
        assert (delivery.vehicle_id, delivery.status) == (vehicle, "assigned")
        assert s.get(Vehicle, vehicle).status == "to_pickup"


def test_no_idle_vehicle_is_logged_at_info_and_skipped(clean_db, city, caplog):
    factory = create_session_factory(clean_db)
    with caplog.at_level(logging.INFO, logger=LOGGER):
        assert request_delivery(factory, city, _trip(city, 1, 3), 300.0) is None
    record = _ours(caplog)[-1]
    assert record.levelno == logging.INFO
    assert "no_idle_vehicle" in record.getMessage()
    assert _count(clean_db, Delivery) == 0


def test_any_other_domain_error_is_logged_as_a_warning_and_skipped(
    clean_db, place_vehicle, city, caplog
):
    place_vehicle(0)
    factory = create_session_factory(clean_db)
    outside = (Point(lat=41.0, lon=-74.0), _point(city, 3))
    with caplog.at_level(logging.INFO, logger=LOGGER):
        assert request_delivery(factory, city, outside, 300.0) is None
    record = _ours(caplog)[-1]
    assert record.levelno == logging.WARNING
    assert "outside_map" in record.getMessage()
    assert _count(clean_db, Delivery) == 0


def test_an_unexpected_error_is_logged_with_a_traceback_and_skipped(
    clean_db, place_vehicle, city, caplog, monkeypatch
):
    place_vehicle(0)

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(gen_module, "create_delivery", boom)
    factory = create_session_factory(clean_db)
    with caplog.at_level(logging.INFO, logger=LOGGER):
        assert request_delivery(factory, city, _trip(city, 1, 3), 300.0) is None
    record = _ours(caplog)[-1]
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None
    assert "boom" in caplog.text


def test_generated_trips_either_create_a_delivery_or_are_skipped(clean_db, place_vehicle, city):
    for node in (0, 3, 5):
        place_vehicle(node)
    factory = create_session_factory(clean_db)
    generator = RequestGenerator(city, 7, 20.0, 60.0)
    results = [
        request_delivery(factory, city, generator.next_trip(), 300.0) for _ in range(12)
    ]
    created = [r for r in results if r is not None]
    assert 1 <= len(created) <= 3  # the island trips are skipped; only 3 cars exist
    assert _count(clean_db, Delivery) == len(created)
    with Session(clean_db) as s:
        busy = s.scalar(
            select(func.count()).select_from(Vehicle).where(Vehicle.status == "to_pickup")
        )
    assert busy == len(created)