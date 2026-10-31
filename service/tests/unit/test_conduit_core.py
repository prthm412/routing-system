import pytest

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