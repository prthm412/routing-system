import pytest
from pydantic import ValidationError

from app.schemas.geo import Point


@pytest.mark.parametrize(
    "lat, lon",
    [(91, 0), (-91, 0), (0, 181), (0, -181), (float("nan"), 0), (0, float("inf"))],
)
def test_impossible_coordinates_are_rejected(lat, lon):
    with pytest.raises(ValidationError):
        Point(lat=lat, lon=lon)


def test_extreme_but_valid_coordinates_are_accepted():
    Point(lat=90, lon=180)
    Point(lat=-90, lon=-180)