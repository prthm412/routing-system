import json
import uuid

import pytest
from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

TABLES_SQL = (
    "SELECT table_name FROM information_schema.tables "
    "WHERE table_schema = 'public' AND table_name IN ('vehicles', 'deliveries', 'routes')"
)
EXTENSIONS_SQL = "SELECT extname FROM pg_extension"


def _names(url, sql):
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            return {row[0] for row in conn.execute(text(sql))}
    finally:
        engine.dispose()


def _vehicle(conn, status="idle"):
    vid = uuid.uuid4()
    conn.execute(
        text("INSERT INTO vehicles (id, current_lat, current_lon, status) "
             "VALUES (:id, 40.7, -74.0, :status)"),
        {"id": vid, "status": status},
    )
    return vid


def _delivery(conn, vehicle_id, status="assigned"):
    did = uuid.uuid4()
    conn.execute(
        text("INSERT INTO deliveries (id, vehicle_id, pickup_lat, pickup_lon, "
             "dropoff_lat, dropoff_lon, status) "
             "VALUES (:id, :vid, 40.70, -74.00, 40.71, -73.99, :status)"),
        {"id": did, "vid": vehicle_id, "status": status},
    )
    return did


def _route(conn, delivery_id, leg):
    conn.execute(
        text("INSERT INTO routes (id, delivery_id, leg, distance_m) "
             "VALUES (:id, :did, :leg, 1.0)"),
        {"id": uuid.uuid4(), "did": delivery_id, "leg": leg},
    )


def test_core_tables_exist(temp_db_url):
    assert _names(temp_db_url, TABLES_SQL) == {"vehicles", "deliveries", "routes"}


def test_postgis_is_enabled_by_the_migration(temp_db_url):
    assert "postgis" in _names(temp_db_url, EXTENSIONS_SQL)


def test_geometry_column_is_linestring_4326(db_engine):
    with db_engine.connect() as conn:
        row = conn.execute(text(
            "SELECT type, srid FROM geometry_columns "
            "WHERE f_table_name = 'routes' AND f_geometry_column = 'geometry'"
        )).one()
    assert tuple(row) == ("LINESTRING", 4326)


def test_geometry_has_one_gist_index(db_engine):
    with db_engine.connect() as conn:
        defs = [r[0] for r in conn.execute(text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE tablename = 'routes' AND indexdef ILIKE '%gist%'"
        ))]
    assert len(defs) == 1
    assert "idx_routes_geometry" in defs[0]


def test_invalid_vehicle_status_is_rejected(clean_db):
    with pytest.raises(IntegrityError) as exc:
        with clean_db.begin() as conn:
            _vehicle(conn, status="flying")
    assert "ck_vehicles_status" in str(exc.value)


def test_second_active_delivery_for_same_vehicle_is_rejected(clean_db):
    with clean_db.begin() as conn:
        vid = _vehicle(conn)
        _delivery(conn, vid, "assigned")
    with pytest.raises(IntegrityError) as exc:
        with clean_db.begin() as conn:
            _delivery(conn, vid, "picked_up")
    assert "uq_deliveries_one_active_per_vehicle" in str(exc.value)


def test_new_delivery_is_allowed_after_the_previous_one_is_delivered(clean_db):
    with clean_db.begin() as conn:
        vid = _vehicle(conn)
        _delivery(conn, vid, "delivered")
        _delivery(conn, vid, "assigned")
        count = conn.execute(text("SELECT count(*) FROM deliveries")).scalar()
    assert count == 2


def test_duplicate_route_leg_is_rejected(clean_db):
    with clean_db.begin() as conn:
        did = _delivery(conn, _vehicle(conn))
        _route(conn, did, "to_pickup")
    with pytest.raises(IntegrityError) as exc:
        with clean_db.begin() as conn:
            _route(conn, did, "to_pickup")
    assert "uq_routes_delivery_leg" in str(exc.value)


def test_geometry_round_trip_is_lon_lat(clean_db):
    with clean_db.begin() as conn:
        did = _delivery(conn, _vehicle(conn))
        conn.execute(
            text("INSERT INTO routes (id, delivery_id, leg, distance_m, geometry) VALUES "
                 "(:id, :did, 'to_pickup', 85.0, "
                 "ST_GeomFromText('LINESTRING(-74.0 40.7, -73.999 40.7)', 4326))"),
            {"id": uuid.uuid4(), "did": did},
        )
        geojson, length_m = conn.execute(text(
            "SELECT ST_AsGeoJSON(geometry), ST_Length(geometry::geography) FROM routes"
        )).one()
    # GeoJSON and WKT are lon/lat; the API will swap to lat/lon for Leaflet
    assert json.loads(geojson)["coordinates"] == [[-74.0, 40.7], [-73.999, 40.7]]
    assert length_m == pytest.approx(84.4, abs=1.0)  # 0.001 degrees of longitude at 40.7 N


def test_upgrade_downgrade_upgrade_on_an_empty_database(empty_db_url, alembic_cfg):
    cfg = alembic_cfg(empty_db_url)
    assert "postgis" not in _names(empty_db_url, EXTENSIONS_SQL)
    command.upgrade(cfg, "head")
    assert _names(empty_db_url, TABLES_SQL) == {"vehicles", "deliveries", "routes"}
    command.downgrade(cfg, "base")
    assert _names(empty_db_url, TABLES_SQL) == set()
    command.upgrade(cfg, "head")
    assert _names(empty_db_url, TABLES_SQL) == {"vehicles", "deliveries", "routes"}