import uuid

from sqlalchemy.orm import Session

from app.db.seed import choose_start_nodes, seed_vehicles


def _seed(engine, city, count=3):
    with Session(engine) as s, s.begin():
        seed_vehicles(s, city, count, seed=1)


def test_empty_fleet_returns_an_empty_list(client):
    res = client.get("/vehicles")
    assert res.status_code == 200
    assert res.json() == []


def test_vehicles_have_the_documented_shape(client, clean_db, city):
    _seed(clean_db, city, 3)
    body = client.get("/vehicles").json()
    assert len(body) == 3
    for v in body:
        assert set(v) == {"id", "position", "status"}
        assert set(v["position"]) == {"lat", "lon"}
        assert v["status"] == "idle"
        uuid.UUID(v["id"])


def test_vehicles_are_ordered_by_id(client, clean_db, city):
    _seed(clean_db, city, 5)
    ids = [v["id"] for v in client.get("/vehicles").json()]
    assert ids == sorted(ids)


def test_vehicle_positions_are_the_seeded_node_coordinates(client, clean_db, city):
    _seed(clean_db, city, 3)
    expected = sorted(city.coordinates(choose_start_nodes(city.node_count, 3, 1)))
    body = client.get("/vehicles").json()
    got = sorted((v["position"]["lat"], v["position"]["lon"]) for v in body)
    assert got == expected