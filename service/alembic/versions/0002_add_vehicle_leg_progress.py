"""add vehicles.leg_progress_m

Revision ID: 0002
Revises: 0001"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vehicles",
        sa.Column("leg_progress_m", sa.Float(), server_default=sa.text("0"), nullable=False),
    )
    op.create_check_constraint("ck_vehicles_leg_progress_m", "vehicles", "leg_progress_m >= 0")


def downgrade() -> None:
    op.drop_constraint("ck_vehicles_leg_progress_m", "vehicles", type_="check")
    op.drop_column("vehicles", "leg_progress_m")