import uuid
from enum import StrEnum

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

class VehicleStatus(StrEnum):
    IDLE = "idle"
    TO_PICKUP = "to_pickup"
    TO_DROPOFF = "to_dropoff"

class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    current_lat: Mapped[float]
    current_lon: Mapped[float]
    status: Mapped[str] = mapped_column(String(16), server_default=VehicleStatus.IDLE.value)