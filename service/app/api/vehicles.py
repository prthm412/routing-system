from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.models.vehicle import Vehicle
from app.schemas.geo import Point
from app.schemas.vehicle import VehicleOut

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.get("", response_model=list[VehicleOut])
def list_vehicles(session: Session = Depends(get_session)) -> list[VehicleOut]:
    vehicles = session.scalars(select(Vehicle).order_by(Vehicle.id)).all()
    return [
        VehicleOut(
            id=v.id,
            position=Point(lat=v.current_lat, lon=v.current_lon),
            status=v.status,
        )
        for v in vehicles
    ]