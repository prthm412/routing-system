import pytest

from app.db.seed import choose_start_nodes


def test_same_seed_gives_same_nodes():
    assert choose_start_nodes(1000, 5, seed=42) == choose_start_nodes(1000, 5, seed=42)
    assert choose_start_nodes(1000, 5, seed=42) != choose_start_nodes(1000, 5, seed=43)


def test_nodes_are_distinct_and_in_range():
    nodes = choose_start_nodes(7, 7, seed=1)
    assert sorted(nodes) == list(range(7))


def test_more_vehicles_than_nodes_is_an_error():
    with pytest.raises(ValueError):
        choose_start_nodes(7, 8, seed=1)


def test_zero_vehicles_is_an_error():
    with pytest.raises(ValueError):
        choose_start_nodes(7, 0, seed=1)