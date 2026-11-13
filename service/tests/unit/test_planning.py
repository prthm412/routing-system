import uuid

import pytest

from app.core.engine_bridge import load_city
from app.core.errors import DomainError
from app.core.planning import check_inside_map, plan_trip, rank_candidates, snap_to_road
from app.schemas.geo import Point

MAX_SNAP_M = 300.0
FAR_INSIDE_MAP = Point(lat=40.76, lon=-74.01)  # inside the box, kilometers from every node


@pytest.fixture(scope="module")
def city():
    return load_city("/data/samples/chain.graph")


def at(city, node, dlat=0.0):
    lat, lon = city.coordinates([node])[0]
    return Point(lat=lat + dlat, lon=lon)


def uid(n):
    return uuid.UUID(int=n)


def vehicle_at(city, n, node):
    lat, lon = city.coordinates([node])[0]
    return (uid(n), lat, lon)


def test_chain_fixture_has_the_expected_shape(city):
    assert (city.node_count, city.edge_count) == (8, 12)
    assert city.find_route(0, 5).distance_m == pytest.approx(425.0)
    assert not city.find_route(0, 6).found


@pytest.mark.parametrize(
    "lat, lon", [(40.700, -74.020), (40.700, -73.965), (40.765, -74.020), (40.765, -73.965)]
)
def test_map_corners_count_as_inside(lat, lon):
    check_inside_map("pickup", Point(lat=lat, lon=lon))


@pytest.mark.parametrize(
    "lat, lon", [(40.699, -74.0), (40.766, -74.0), (40.73, -74.021), (40.73, -73.964)]
)
def test_points_outside_the_map_are_rejected(lat, lon):
    with pytest.raises(DomainError) as exc:
        check_inside_map("pickup", Point(lat=lat, lon=lon))
    assert (exc.value.code, exc.value.status_code) == ("outside_map", 422)
    assert "pickup" in exc.value.message


def test_snap_to_road_returns_the_nearest_node(city):
    assert snap_to_road(city, "pickup", at(city, 2, dlat=0.0001), MAX_SNAP_M) == 2


def test_snap_to_road_rejects_a_point_far_from_every_road(city):
    with pytest.raises(DomainError) as exc:
        snap_to_road(city, "dropoff", FAR_INSIDE_MAP, MAX_SNAP_M)
    assert (exc.value.code, exc.value.status_code) == ("too_far_from_road", 422)
    assert "dropoff" in exc.value.message


def test_snap_limit_is_what_rejects_far_points(city):
    node = snap_to_road(city, "dropoff", FAR_INSIDE_MAP, max_snap_m=1e7)
    assert 0 <= node < city.node_count


def test_plan_trip_finds_the_pickup_to_dropoff_leg(city):
    plan = plan_trip(city, at(city, 1), at(city, 4), MAX_SNAP_M)
    assert (plan.pickup_node, plan.dropoff_node) == (1, 4)
    assert plan.dropoff_leg.nodes == [1, 2, 3, 4]
    assert plan.dropoff_leg.distance_m == pytest.approx(255.0)


def test_plan_trip_rejects_pickup_and_dropoff_on_the_same_node(city):
    with pytest.raises(DomainError) as exc:
        plan_trip(city, at(city, 2), at(city, 2, dlat=0.0001), MAX_SNAP_M)
    assert (exc.value.code, exc.value.status_code) == ("same_location", 422)


def test_plan_trip_rejects_an_unreachable_dropoff(city):
    with pytest.raises(DomainError) as exc:
        plan_trip(city, at(city, 1), at(city, 6), MAX_SNAP_M)
    assert (exc.value.code, exc.value.status_code) == ("route_not_found", 422)


def test_plan_trip_checks_the_dropoff_is_inside_the_map(city):
    with pytest.raises(DomainError) as exc:
        plan_trip(city, at(city, 1), Point(lat=41.0, lon=-74.0), MAX_SNAP_M)
    assert exc.value.code == "outside_map"
    assert "dropoff" in exc.value.message


def test_candidates_are_ordered_by_road_distance(city):
    vehicles = [vehicle_at(city, 2, 5), vehicle_at(city, 1, 0)]  # nodes 5 and 0, pickup at 2
    ranked = rank_candidates(city, vehicles, pickup_node=2)
    assert [c.vehicle_id for c in ranked] == [uid(1), uid(2)]
    assert [c.leg.distance_m for c in ranked] == pytest.approx([170.0, 255.0])
    assert ranked[0].leg.nodes == [0, 1, 2]


def test_equal_distances_go_to_the_lowest_vehicle_id(city):
    vehicles = [vehicle_at(city, 2, 1), vehicle_at(city, 1, 3)]  # both 85 m from node 2
    ranked = rank_candidates(city, vehicles, pickup_node=2)
    assert [c.vehicle_id for c in ranked] == [uid(1), uid(2)]


def test_unreachable_vehicles_are_skipped(city):
    vehicles = [vehicle_at(city, 1, 0), vehicle_at(city, 2, 7)]  # pickup 6 is on the island
    ranked = rank_candidates(city, vehicles, pickup_node=6)
    assert [c.vehicle_id for c in ranked] == [uid(2)]


def test_no_candidates_when_nobody_can_reach_the_pickup(city):
    assert rank_candidates(city, [vehicle_at(city, 1, 0)], pickup_node=6) == []


def test_vehicle_already_at_the_pickup_has_a_zero_length_leg(city):
    ranked = rank_candidates(city, [vehicle_at(city, 1, 2)], pickup_node=2)
    assert ranked[0].leg.distance_m == 0.0
    assert ranked[0].leg.nodes == [2]


def test_no_vehicles_means_no_candidates(city):
    assert rank_candidates(city, [], pickup_node=2) == []