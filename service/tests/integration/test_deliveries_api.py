import uuid

import pytest
from sqlalchemy import text


def at(city, node):
    lat, lon = city.coordinates([node])[0]
    return {"lat": lat, "lon": lon}


def trip(city, pickup_node, dropoff_node):
    return {"pickup": at(city, pickup_node), "dropoff": at(city, dropoff_node)}


def flat(points):
    return [x for p in points for x in p]


def test_creates_delivery_with_nearest_vehicle_and_both_legs(client, place_vehicle, city):
    near = place_vehicle(0)
    place_vehicle(5)
    res = client.post("/deliveries", json=trip(city, 1, 3))
    assert res.status_code == 201
    body = res.json()
    assert body["vehicle_id"] == str(near)
    assert body["status"] == "assigned"
    assert body["eta"] is None
    assert body["pickup"] == at(city, 1)
    assert body["dropoff"] == at(city, 3)
    to_pickup, to_dropoff = body["legs"]
    assert (to_pickup["leg"], to_dropoff["leg"]) == ("to_pickup", "to_dropoff")
    assert to_pickup["distance_m"] == pytest.approx(85.0)
    assert to_dropoff["distance_m"] == pytest.approx(170.0)
    assert to_pickup["duration_sec"] is None
    assert flat(to_pickup["path"]) == pytest.approx(flat(city.coordinates([0, 1])))
    assert flat(to_dropoff["path"]) == pytest.approx(flat(city.coordinates([1, 2, 3])))


def test_assigned_vehicle_becomes_to_pickup_and_others_stay_idle(client, place_vehicle, city):
    near = place_vehicle(0)
    place_vehicle(5)
    client.post("/deliveries", json=trip(city, 1, 3))
    statuses = {v["id"]: v["status"] for v in client.get("/vehicles").json()}
    assert statuses[str(near)] == "to_pickup"
    assert sorted(statuses.values()) == ["idle", "to_pickup"]


def test_get_returns_the_same_body_as_post(client, place_vehicle, city):
    place_vehicle(0)
    created = client.post("/deliveries", json=trip(city, 1, 3)).json()
    res = client.get(f"/deliveries/{created['id']}")
    assert res.status_code == 200
    assert res.json() == created


def test_delivery_and_route_rows_are_persisted(client, clean_db, place_vehicle, city):
    place_vehicle(0)
    client.post("/deliveries", json=trip(city, 1, 3))
    with clean_db.connect() as conn:
        deliveries = conn.execute(text("SELECT count(*) FROM deliveries")).scalar()
        legs = conn.execute(text(
            "SELECT leg, ST_NumPoints(geometry), ST_SRID(geometry) FROM routes ORDER BY leg"
        )).all()
    assert deliveries == 1
    assert [tuple(r) for r in legs] == [("to_dropoff", 3, 4326), ("to_pickup", 2, 4326)]


def test_zero_length_first_leg_has_no_path_and_null_geometry(client, clean_db, place_vehicle, city):
    place_vehicle(1)  # already standing at the pickup
    body = client.post("/deliveries", json=trip(city, 1, 3)).json()
    assert body["legs"][0]["distance_m"] == 0.0
    assert body["legs"][0]["path"] == []
    with clean_db.connect() as conn:
        null_geometries = conn.execute(text(
            "SELECT count(*) FROM routes WHERE leg = 'to_pickup' AND geometry IS NULL"
        )).scalar()
    assert null_geometries == 1


def test_next_request_gets_the_next_nearest_vehicle(client, place_vehicle, city):
    a, b = place_vehicle(0), place_vehicle(5)
    first = client.post("/deliveries", json=trip(city, 1, 3))
    second = client.post("/deliveries", json=trip(city, 2, 4))
    third = client.post("/deliveries", json=trip(city, 2, 4))
    assert first.json()["vehicle_id"] == str(a)
    assert second.json()["vehicle_id"] == str(b)
    assert third.status_code == 409
    assert third.json()["detail"]["code"] == "no_idle_vehicle"


def test_no_vehicles_is_409(client, city):
    res = client.post("/deliveries", json=trip(city, 1, 3))
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "no_idle_vehicle"


def test_all_vehicles_busy_is_409(client, place_vehicle, city):
    place_vehicle(0, "to_pickup")
    place_vehicle(5, "to_dropoff")
    res = client.post("/deliveries", json=trip(city, 1, 3))
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "no_idle_vehicle"


def test_idle_vehicle_that_cannot_reach_the_pickup_is_route_not_found(client, place_vehicle, city):
    place_vehicle(7)  # on the island
    res = client.post("/deliveries", json=trip(city, 1, 3))
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "route_not_found"


BAD_REQUESTS = [
    ("outside_map", lambda c: {"pickup": {"lat": 41.0, "lon": -74.0}, "dropoff": at(c, 3)}),
    ("too_far_from_road", lambda c: {"pickup": {"lat": 40.76, "lon": -74.01}, "dropoff": at(c, 3)}),
    ("same_location", lambda c: trip(c, 2, 2)),
    ("route_not_found", lambda c: trip(c, 1, 6)),
]


@pytest.mark.parametrize("code, make_body", BAD_REQUESTS)
def test_rejected_requests_change_nothing(client, clean_db, place_vehicle, city, code, make_body):
    place_vehicle(0)
    res = client.post("/deliveries", json=make_body(city))
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == code
    assert isinstance(res.json()["detail"]["message"], str)
    with clean_db.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM deliveries")).scalar() == 0
        assert conn.execute(text("SELECT status FROM vehicles")).scalars().all() == ["idle"]


@pytest.mark.parametrize(
    "body",
    [
        {"pickup": {"lat": 100.0, "lon": -74.0}, "dropoff": {"lat": 40.73, "lon": -73.99}},
        {"pickup": {"lat": 40.73, "lon": -74.0}},
    ],
)
def test_invalid_body_gets_fastapi_validation_error(client, body):
    res = client.post("/deliveries", json=body)
    assert res.status_code == 422
    assert isinstance(res.json()["detail"], list)


def test_get_unknown_delivery_is_404(client):
    res = client.get(f"/deliveries/{uuid.uuid4()}")
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "delivery_not_found"


def test_get_malformed_id_is_422(client):
    assert client.get("/deliveries/not-a-uuid").status_code == 422