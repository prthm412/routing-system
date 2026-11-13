import pytest

from app.core.engine_bridge import load_city

SAMPLES = "/data/samples"


def test_load_city_returns_a_city():
    city = load_city(f"{SAMPLES}/tiny.graph")
    assert (city.node_count, city.edge_count) == (7, 13)


def test_missing_graph_raises_runtime_error():
    with pytest.raises(RuntimeError, match="cannot open"):
        load_city("/no/such/file.graph")