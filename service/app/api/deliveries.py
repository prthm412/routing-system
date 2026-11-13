import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.core.assignment import create_delivery
from app.core.errors import DomainError
from app.models import Delivery, Route, RouteLeg
from app.schemas.delivery import DeliveryCreate, DeliveryOut, LegOut
from app.schemas.geo import Point

router = APIRouter(prefix="/deliveries", tags=["deliveries"])

_LEG_ORDER = [RouteLeg.TO_PICKUP.value, RouteLeg.TO_DROPOFF.value]

def _path(geojson) -> list[tuple[float, float]]:
    if geojson is None:
        return []
    data = geojson if isinstance(geojson, dict) else json.loads(geojson)
    # GeoJSON is [lon, lat]; this API speaks [lat, lon] which is what Leaflet wants
    return [(lat, lon) for lon, lat in data["coordinates"]]

def load_delivery(session: Session, delivery_id: uuid.UUID) -> DeliveryOut | None:
    delivery = session.get(Delivery, delivery_id)
    if delivery is None:
        return None
    rows = session.execute(
        select(Route.leg, Route.distance_m, Route.duration_sec, func.ST_AsGeoJSON(Route.geometry))
        .where(Route.delivery_id == delivery_id)
    ).all()
    rows.sort(key=lambda r: _LEG_ORDER.index(r[0]))
    return DeliveryOut(
        id=delivery.id,
        status=delivery.status,
        vehicle_id=delivery.vehicle_id,
        pickup=Point(lat=delivery.pickup_lat, lon=delivery.pickup_lon),
        dropoff=Point(lat=delivery.dropoff_lat, lon=delivery.dropoff_lon),
        eta=delivery.eta,
        legs=[LegOut(leg=r[0], distance_m=r[1], duration_sec=r[2], path=_path(r[3])) for r in rows],
    )


@router.post(
    "",
    response_model=DeliveryOut,
    status_code=201,
    responses={
        409: {"description": "detail.code is no_idle_vehicle"},
        422: {
            "description": "detail.code is outside_map, too_far_from_road, same_location "
            "or route_not_found; FastAPI's own validation errors have a list as detail"
        },
    },
)
def create(body: DeliveryCreate, request: Request, session: Session = Depends(get_session)) -> DeliveryOut:
    try:
        delivery_id = create_delivery(session, request.app.state.city, body.pickup, body.dropoff, request.app.state.settings.max_snap_distance_m)
    except DomainError as err:
        raise HTTPException(err.status_code, detail={"code": err.code, "message": err.message}) from err
    return load_delivery(session, delivery_id)


@router.get("/{delivery_id}", response_model=DeliveryOut)
def get_delivery(delivery_id: uuid.UUID, session: Session = Depends(get_session)) -> DeliveryOut:
    out = load_delivery(session, delivery_id)
    if out is None:
        raise HTTPException(404, detail={"code": "delivery_not_found", "message": f"no delivery {delivery_id}"})
    return out