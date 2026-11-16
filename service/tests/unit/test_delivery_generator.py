from pathlib import Path
import pytest

from app.core.engine_bridge import load_city
from app.core.planning import plan_trip
from app.sim.delivery_generator import RequestGenerator

CHAIN = "/data/samples/chain.graph"
NYC = Path("/data/processed/nyc.graph")


@pytest.fixture(scope="module")
def city():
    return load_city(CHAIN)


def make(city, seed=1, low=20.0, high=60.0):
    return RequestGenerator(city, seed, low, high)


def drawn(gen, count):
    return [(gen.next_trip(), gen.next_interval_s()) for _ in range(count)]


def test_same_seed_gives_the_same_trips_and_intervals(city):
    assert drawn(make(city, seed=7), 30) == drawn(make(city, seed=7), 30)


def test_different_seeds_give_different_trips(city):
    assert drawn(make(city, seed=7), 30) != drawn(make(city, seed=8), 30)


def test_trips_use_two_different_graph_nodes(city):
    node_coords = set(city.coordinates(list(range(city.node_count))))
    gen = make(city)
    for _ in range(50):
        pickup, dropoff = gen.next_trip()
        assert (pickup.lat, pickup.lon) in node_coords
        assert (dropoff.lat, dropoff.lon) in node_coords
        assert (pickup.lat, pickup.lon) != (dropoff.lat, dropoff.lon)


def test_intervals_stay_inside_the_bounds(city):
    gen = make(city, low=20.0, high=60.0)
    values = [gen.next_interval_s() for _ in range(200)]
    assert all(20.0 <= v <= 60.0 for v in values)
    assert len(set(values)) > 1


def test_equal_min_and_max_gives_a_fixed_interval(city):
    gen = make(city, low=30.0, high=30.0)
    assert {gen.next_interval_s() for _ in range(10)} == {30.0}


def test_trips_do_not_depend_on_how_many_intervals_were_drawn(city):
    plain, busy = make(city, seed=3), make(city, seed=3)
    expected = [plain.next_trip() for _ in range(20)]
    got = []
    for _ in range(20):
        busy.next_interval_s()
        busy.next_interval_s()
        got.append(busy.next_trip())
    assert got == expected


@pytest.mark.parametrize("low, high", [(0.0, 5.0), (-1.0, 5.0), (10.0, 5.0)])
def test_bad_intervals_are_refused(city, low, high):
    with pytest.raises(ValueError):
        make(city, low=low, high=high)


def test_a_graph_with_one_node_is_refused(tmp_path):
    one = tmp_path / "one.graph"
    one.write_text("conduit-graph v1\nnodes 1\nedges 0\n0 40.73 -73.99\n")
    with pytest.raises(ValueError):
        RequestGenerator(load_city(str(one)), 1, 20.0, 60.0)


@pytest.mark.skipif(
    not NYC.exists(), reason="no /data/processed/nyc.graph; run the data pipeline first"
)
def test_real_graph_trips_can_all_be_planned():
    city = load_city(str(NYC))
    gen = RequestGenerator(city, 42, 20.0, 60.0)
    for _ in range(300):
        pickup, dropoff = gen.next_trip()
        plan = plan_trip(city, pickup, dropoff, 300.0)  # raises DomainError for a bad trip
        assert plan.dropoff_leg.distance_m > 0