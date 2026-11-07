import uuid

from pydantic import BaseModel

from app.schemas.geo import Point


class VehicleOut(BaseModel):
    id: uuid.UUID
    position: Point
    status: str