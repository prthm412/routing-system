"""create vehicles, deliveries and routes

Revision ID: 0001
Revises:
"""
import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A database created from the default template does not have PostGIS yet
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "vehicles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("current_lat", sa.Float(), nullable=False),
        sa.Column("current_lon", sa.Float(), nullable=False),
        sa.Column("status", sa.String(16), server_default="idle", nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_vehicles"),
        sa.CheckConstraint(
            "status IN ('idle', 'to_pickup', 'to_dropoff')", name="ck_vehicles_status"
        ),
    )

    op.create_table(
        "deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_id", sa.Uuid(), nullable=False),
        sa.Column("pickup_lat", sa.Float(), nullable=False),
        sa.Column("pickup_lon", sa.Float(), nullable=False),
        sa.Column("dropoff_lat", sa.Float(), nullable=False),
        sa.Column("dropoff_lon", sa.Float(), nullable=False),
        sa.Column("status", sa.String(16), server_default="assigned", nullable=False),
        sa.Column("eta", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_deliveries"),
        sa.ForeignKeyConstraint(
            ["vehicle_id"], ["vehicles.id"], name="fk_deliveries_vehicle_id_vehicles"
        ),
        sa.CheckConstraint(
            "status IN ('assigned', 'picked_up', 'delivered')", name="ck_deliveries_status"
        ),
    )
    # A vehicle can have at most one active delivery, enforced by the database itself
    op.create_index(
        "uq_deliveries_one_active_per_vehicle",
        "deliveries",
        ["vehicle_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('assigned', 'picked_up')"),
    )

    op.create_table(
        "routes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("delivery_id", sa.Uuid(), nullable=False),
        sa.Column("leg", sa.String(16), nullable=False),
        sa.Column("distance_m", sa.Float(), nullable=False),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column(
            "geometry",
            geoalchemy2.Geometry(geometry_type="LINESTRING", srid=4326, spatial_index=False),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_routes"),
        sa.ForeignKeyConstraint(
            ["delivery_id"],
            ["deliveries.id"],
            name="fk_routes_delivery_id_deliveries",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("delivery_id", "leg", name="uq_routes_delivery_leg"),
        sa.CheckConstraint("leg IN ('to_pickup', 'to_dropoff')", name="ck_routes_leg"),
    )
    op.create_index("idx_routes_geometry", "routes", ["geometry"], postgresql_using="gist")


def downgrade() -> None:
    # The postgis extension is left in place on purpose; other tables may use it.
    op.drop_index("idx_routes_geometry", table_name="routes")
    op.drop_table("routes")
    op.drop_index("uq_deliveries_one_active_per_vehicle", table_name="deliveries")
    op.drop_table("deliveries")
    op.drop_table("vehicles")