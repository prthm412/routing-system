import pytest
import math
from pathlib import Path
import gc
import random

import conduit_core

SAMPLES = "/data/samples"


def test_load_city_reads_tiny_graph():
    city = conduit_core.load_city(f"{SAMPLES}/tiny.graph")
    assert city.node_count == 7
    assert city.edge_count == 13


def test_two_cities_are_independent():
    tiny = conduit_core.load_city(f"{SAMPLES}/tiny.graph")
    detour = conduit_core.load_city(f"{SAMPLES}/detour.graph")
    assert (tiny.node_count, detour.node_count) == (7, 3)


def test_missing_file_raises_runtime_error():
    with pytest.raises(RuntimeError, match="cannot open"):
        conduit_core.load_city("/no/such/file.graph")


def test_malformed_file_raises_runtime_error_with_line_number(tmp_path):
    bad = tmp_path / "bad.graph"
    bad.write_text("conduit-graph v2\nnodes 0\nedges 0\n")
    with pytest.raises(RuntimeError, match="line 1"):
        conduit_core.load_city(str(bad))


def test_empty_graph_is_refused(tmp_path):
    empty = tmp_path / "empty.graph"
    empty.write_text("conduit-graph v1\nnodes 0\nedges 0\n")
    with pytest.raises(RuntimeError, match="no nodes"):
        conduit_core.load_city(str(empty))


def test_city_cannot_be_constructed_directly():
    with pytest.raises(TypeError):
        conduit_core.City()

# Hand-written coordinates of data/samples/tiny.graph.
TINY_NODES = [
    (0, 40.7000, -74.0000),
    (1, 40.7000, -73.9990),
    (2, 40.7000, -73.9980),
    (3, 40.7010, -74.0000),
    (4, 40.7010, -73.9990),
    (5, 40.7010, -73.9980),
    (6, 40.7020, -73.9970),
]

PROCESSED = Path("/data/processed")


@pytest.fixture
def tiny():
    return conduit_core.load_city(f"{SAMPLES}/tiny.graph")


@pytest.mark.parametrize("node_id, lat, lon", TINY_NODES)
def test_exact_coordinates_return_their_own_node(tiny, node_id, lat, lon):
    assert tiny.nearest_node(lat, lon) == node_id


def test_point_near_a_node_snaps_to_it(tiny):
    # ~4 m north and ~2 m east of node 1; every other node is 80+ m away.
    assert tiny.nearest_node(lat=40.70004, lon=-73.99898) == 1


def test_far_away_point_still_returns_a_node(tiny):
    # Documented behaviour: the index never says "too far". The API (Phase 3) must.
    assert tiny.nearest_node(41.0, -73.0) == 6


@pytest.mark.parametrize(
    "lat, lon",
    [
        (math.nan, -74.0),
        (40.7, math.nan),
        (math.inf, -74.0),
        (40.7, -math.inf),
        (91.0, -74.0),
        (-91.0, -74.0),
        (40.7, 181.0),
        (40.7, -181.0),
    ],
)
def test_invalid_coordinates_raise_value_error(tiny, lat, lon):
    with pytest.raises(ValueError):
        tiny.nearest_node(lat, lon)


def test_wrong_argument_type_raises_type_error(tiny):
    with pytest.raises(TypeError):
        tiny.nearest_node("40.7", -74.0)


def _read_node_coords(path):
    # Plain text format: 3 header lines, then N lines of "<id> <lat> <lon>".
    with open(path) as f:
        f.readline()
        node_total = int(f.readline().split()[1])
        f.readline()
        coords = []
        for _ in range(node_total):
            _, lat, lon = f.readline().split()
            coords.append((float(lat), float(lon)))
    return coords


@pytest.mark.skipif(
    not (PROCESSED / "nyc.graph").exists(),
    reason="no /data/processed/nyc.graph; run the data pipeline first",
)
def test_real_graph_nodes_find_themselves():
    path = PROCESSED / "nyc.graph"
    coords = _read_node_coords(path)
    city = conduit_core.load_city(str(path))
    assert city.node_count == len(coords)
    for i in range(0, len(coords), 40):  # about 54 of the nodes
        found = city.nearest_node(*coords[i])
        assert coords[found] == coords[i]  # same place (an id swap is fine only for duplicate points)

# Hand-worked answer key for data/samples/tiny.graph (same numbers as the C++ tests).
ANSWER_KEY = [
    (0, 5, 282.0, [0, 1, 4, 5]),
    (4, 3, 309.0, [4, 1, 0, 3]),  # one-way street 3 -> 4 forces the long way back
    (3, 4, 87.0, [3, 4]),
    (0, 2, 175.0, [0, 1, 2]),
    (2, 2, 0.0, [2]),  # start equals destination
]


@pytest.mark.parametrize("src, dst, meters, path", ANSWER_KEY)
def test_tiny_routes_match_the_hand_worked_answer_key(tiny, src, dst, meters, path):
    route = tiny.find_route(src, dst)
    assert route.found is True
    assert route.distance_m == pytest.approx(meters)
    assert route.nodes == path


@pytest.mark.parametrize("src, dst", [(0, 6), (6, 0)])
def test_unreachable_destination_is_a_result_not_an_error(tiny, src, dst):
    route = tiny.find_route(src, dst)
    assert route.found is False
    assert route.distance_m == 0.0
    assert route.nodes == []


def test_shorter_beats_fewer_streets():
    city = conduit_core.load_city(f"{SAMPLES}/detour.graph")
    route = city.find_route(0, 2)
    assert route.distance_m == pytest.approx(180.0)
    assert route.nodes == [0, 1, 2]


def test_find_route_accepts_keyword_arguments(tiny):
    assert tiny.find_route(from_node=0, to_node=5).nodes == [0, 1, 4, 5]


@pytest.mark.parametrize("src, dst", [(99, 0), (0, 99), (7, 0), (0, 4294967295)])
def test_unknown_node_id_raises_index_error(tiny, src, dst):
    # 7 is one past the last node (the graph has 7 nodes, ids 0..6);
    # 4294967295 is the engine's internal "no node" marker.
    with pytest.raises(IndexError):
        tiny.find_route(src, dst)


@pytest.mark.parametrize("src, dst", [(-1, 0), (0, -1), (0, 2**32), (1.5, 0), ("0", 1)])
def test_ids_that_are_not_valid_node_numbers_raise_type_error(tiny, src, dst):
    with pytest.raises(TypeError):
        tiny.find_route(src, dst)


def test_route_stays_valid_after_the_city_is_gone(tiny):
    route = tiny.find_route(0, 5)
    del tiny
    gc.collect()
    assert route.nodes == [0, 1, 4, 5]
    assert route.distance_m == pytest.approx(282.0)


def test_route_cannot_be_constructed_directly():
    with pytest.raises(TypeError):
        conduit_core.Route()


def test_route_repr_is_readable(tiny):
    assert repr(tiny.find_route(0, 5)).startswith("<Route found=True")


def _read_edge_weights(path):
    # Same text format as _read_node_coords. Keeps the shortest weight per (from, to).
    with open(path) as f:
        f.readline()
        node_total = int(f.readline().split()[1])
        edge_total = int(f.readline().split()[1])
        for _ in range(node_total):
            f.readline()
        weights = {}
        for _ in range(edge_total):
            src, dst, meters = f.readline().split()
            key = (int(src), int(dst))
            weights[key] = min(weights.get(key, math.inf), float(meters))
    return weights


def _straight_line_m(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 6_371_000.0 * math.asin(math.sqrt(h))


@pytest.mark.skipif(
    not (PROCESSED / "nyc.graph").exists(),
    reason="no /data/processed/nyc.graph; run the data pipeline first",
)
def test_real_graph_routes_are_walkable_and_not_shorter_than_straight_line():
    path = PROCESSED / "nyc.graph"
    coords = _read_node_coords(path)
    weights = _read_edge_weights(path)
    city = conduit_core.load_city(str(path))
    rng = random.Random(2024)
    for _ in range(50):
        src = rng.randrange(len(coords))
        dst = rng.randrange(len(coords))
        route = city.find_route(src, dst)
        assert route.found, f"{src} -> {dst}"  # the pipeline keeps a strongly connected graph
        assert route.nodes[0] == src and route.nodes[-1] == dst
        walked = sum(weights[(a, b)] for a, b in zip(route.nodes, route.nodes[1:]))
        assert route.distance_m == pytest.approx(walked, abs=1e-6)
        # 1e-4 slack in case this Earth radius differs a little from the engine's constant.
        assert route.distance_m >= _straight_line_m(coords[src], coords[dst]) * (1 - 1e-4)