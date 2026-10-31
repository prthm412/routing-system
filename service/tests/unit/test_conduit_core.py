import pytest
import math
from pathlib import Path

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