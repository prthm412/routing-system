import uuid
from datetime import datetime
from pydantic import BaseModel

from app.schemas.geo import Point


class DeliveryCreate(BaseModel):
    pickup: Point
    dropoff: Point


class LegOut(BaseModel):
    leg: str
    distance_m: float
    duration_sec: int | None
    path: list[tuple[float, float]] # [lat, lon] pairs


class DeliveryOut(BaseModel):
    id: uuid.UUID
    status: str
    vehicle_id: uuid.UUID
    pickup: Point
    dropoff: Point
    eta: datetime | None
    legs: list[LegOut]  # to_pickup first