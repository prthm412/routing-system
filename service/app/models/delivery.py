import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DeliveryStatus(StrEnum):
    ASSIGNED = "assigned"
    PICKED_UP = "picked_up"
    DELIVERED = "delivered"


class Delivery(Base):
    __tablename__ = "deliveries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id"))
    pickup_lat: Mapped[float]
    pickup_lon: Mapped[float]
    dropoff_lat: Mapped[float]
    dropoff_lon: Mapped[float]
    status: Mapped[str] = mapped_column(String(16), server_default=DeliveryStatus.ASSIGNED.value)
    eta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))