import math
import pytest
from app.sim.vehicles import advance_progress, position_on_line

A = (40.7300, -73.9900)
B = (40.7300, -73.9890)
C = (40.7300, -73.9880)
D = (40.7310, -73.9890)

STRAIGHT = [A, B, C]  # two equal segments, about 84.4 m each
BENT = [A, B, D]  # east about 84 m, then north about 111 m


def _haversine_m(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 6_371_000.0 * math.asin(min(1.0, math.sqrt(h)))


# advance_progress


def test_advance_moves_forward_without_finishing():
    progress, finished = advance_progress(0.0, 12.0, 170.0)
    assert progress == 12.0
    assert finished is False

def test_advance_reaching_the_end_exactly_finishes():
    progress, finished = advance_progress(158.0, 12.0, 170.0)
    assert progress == 170.0
    assert finished is True

def test_advance_never_goes_past_the_end():
    assert advance_progress(165.0, 12.0, 170.0) == (170.0, True)


def test_zero_length_leg_finishes_at_once():
    assert advance_progress(0.0, 12.0, 0.0) == (0.0, True)


@pytest.mark.parametrize(
    "progress, step, distance", [(-1.0, 12.0, 170.0), (0.0, -1.0, 170.0), (0.0, 12.0, -5.0)]
)
def test_advance_rejects_negative_numbers(progress, step, distance):
    with pytest.raises(ValueError):
        advance_progress(progress, step, distance)


# position_on_line


def test_start_of_the_leg_is_the_first_point():
    assert position_on_line(STRAIGHT, 0.0, 170.0) == A


def test_end_of_the_leg_is_exactly_the_last_point():
    assert position_on_line(STRAIGHT, 170.0, 170.0) == C
    assert position_on_line(STRAIGHT, 220.0, 170.0) == C  # past the end is clamped


def test_halfway_on_the_odometer_is_halfway_along_the_line():
    assert position_on_line(STRAIGHT, 85.0, 170.0) == pytest.approx(B, abs=1e-9)


def test_quarter_of_the_way_is_halfway_along_the_first_segment():
    lat, lon = position_on_line(STRAIGHT, 42.5, 170.0)
    assert lat == pytest.approx(40.7300, abs=1e-9)
    assert lon == pytest.approx(-73.9895, abs=1e-9)


def test_position_follows_the_corner():
    lat, lon = position_on_line(BENT, 120.0, 200.0)  # 60% of the way, past the corner
    assert lon == pytest.approx(-73.9890, abs=1e-9)  # on the northbound segment
    assert 40.7300 < lat < 40.7310


@pytest.mark.parametrize("line, leg_m", [(STRAIGHT, 170.0), (BENT, 200.0)])
def test_a_car_never_jumps_more_than_one_step(line, leg_m):
    step = 17.0
    progress, finished = 0.0, False
    last = line[0]
    while not finished:
        progress, finished = advance_progress(progress, step, leg_m)
        here = position_on_line(line, progress, leg_m)
        assert _haversine_m(last, here) <= step + 1e-6
        last = here
    assert last == line[-1]


def test_a_line_needs_two_points():
    with pytest.raises(ValueError):
        position_on_line([A], 1.0, 170.0)
    with pytest.raises(ValueError):
        position_on_line([], 1.0, 170.0)


@pytest.mark.parametrize("progress, distance", [(1.0, 0.0), (1.0, -5.0), (-1.0, 170.0)])
def test_position_rejects_impossible_numbers(progress, distance):
    with pytest.raises(ValueError):
        position_on_line(STRAIGHT, progress, distance)