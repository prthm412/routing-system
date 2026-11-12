import uuid
from enum import StrEnum

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKBElement
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RouteLeg(StrEnum):
    TO_PICKUP = "to_pickup"
    TO_DROPOFF = "to_dropoff"


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    delivery_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("deliveries.id", ondelete="CASCADE"))
    leg: Mapped[str] = mapped_column(String(16))
    distance_m: Mapped[float]
    duration_sec: Mapped[int | None]
    geometry: Mapped[WKBElement | None] = mapped_column(Geometry("LINESTRING", srid=4326, spatial_index=False))