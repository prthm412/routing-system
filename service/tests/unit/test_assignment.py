from app.core.assignment import linestring_wkt


def test_linestring_wkt_puts_longitude_first():
    assert linestring_wkt([(40.7, -74.0), (40.71, -73.99)]) == (
        "LINESTRING(-74.0 40.7, -73.99 40.71)"
    )


def test_linestring_wkt_needs_two_points():
    assert linestring_wkt([]) is None
    assert linestring_wkt([(40.7, -74.0)]) is None


def test_linestring_wkt_keeps_full_precision():
    assert linestring_wkt([(40.7123456, -73.9876543), (40.7, -74.0)]) == (
        "LINESTRING(-73.9876543 40.7123456, -74.0 40.7)"
    )