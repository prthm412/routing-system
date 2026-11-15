"""Vehicle movement"""

import math
from collections.abc import Sequence

# Same earth radius as engine/include/geo.hpp
EARTH_RADIUS_M = 6371000.0

Point = tuple[float, float]     # (lat, lon), the same order as the API paths

def _haversine_m(a: Point, b: Point) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))

def advance_progress(progress_m: float, step_m: float, distance_m: float) -> tuple[float, bool]:
    """Drive `step_m` further along a leg that is `distance_m` long.
       Returns (new progress, finished). Progress never goes past the end of the leg."""
    if progress_m < 0 or step_m < 0 or distance_m < 0:
        raise ValueError("progress, step and distance must not be negative")
    new = progress_m + step_m
    if new >= distance_m:
        return distance_m, True
    return new, False

def position_on_line(points: Sequence[Point], progress_m: float, distance_m: float) -> Point:
    """Where a car is after `progress_m` of a leg that is `distance_m` long.
       The same fraction of the drawn line. At or past the end it is exactly the last point."""
    if len(points) < 2:
        raise ValueError("a line needs at least two points")
    if distance_m <= 0:
        raise ValueError("distance_m must be positive")
    if progress_m < 0:
        raise ValueError("progress_m must not be negative")
    if progress_m == 0:
        return points[0]
    if progress_m >= distance_m:
        return points[-1]

    pairs = list(zip(points, points[1:]))
    lengths = [_haversine_m(a, b) for a, b in pairs]
    total = sum(lengths)
    if total == 0:
        return points[-1]

    target = progress_m / distance_m * total
    walked = 0.0
    for (a, b), length in zip(pairs, lengths):
        if length > 0 and walked + length >= target:
            t = (target - walked) / length
            if t >= 1.0:
                return b
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        walked += length
    return points[-1]