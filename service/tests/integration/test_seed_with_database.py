import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.seed import seed_vehicles
from app.models.vehicle import Vehicle


def _seed(engine, city, count, seed=1):
    with Session(engine) as s, s.begin():
        return seed_vehicles(s, city, count, seed)


def test_seeds_the_requested_number_of_idle_vehicles(clean_db, city):
    assert _seed(clean_db, city, 5) == 5
    with Session(clean_db) as s:
        statuses = s.scalars(select(Vehicle.status)).all()
    assert statuses == ["idle"] * 5


def test_seeded_vehicles_sit_exactly_on_graph_nodes(clean_db, city):
    _seed(clean_db, city, 5)
    with Session(clean_db) as s:
        vehicles = s.scalars(select(Vehicle)).all()
    for v in vehicles:
        assert city.snap(v.current_lat, v.current_lon).distance_m == pytest.approx(0.0, abs=1e-6)


def test_seeding_twice_changes_nothing(clean_db, city):
    assert _seed(clean_db, city, 5) == 5
    assert _seed(clean_db, city, 3) == 0
    with Session(clean_db) as s:
        assert s.scalar(select(func.count()).select_from(Vehicle)) == 5