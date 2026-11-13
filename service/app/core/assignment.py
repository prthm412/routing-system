import uuid
from geoalchemy2.elements import WKTElement
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.engine_bridge import City
from app.core.errors import DomainError
from app.core.planning import Candidate, Leg, plan_trip, rank_candidates
from app.models import Delivery, Route, RouteLeg, Vehicle, VehicleStatus
from app.schemas.geo import Point

def linestring_wkt(coords: list[tuple[float, float]]) -> str | None:
    """WKT line through (lat, lon) pairs. WKT wants lon first. None if under two points."""
    if len(coords) < 2:
        return None
    return "LINESTRING(" + ", ".join(f"{lon!r} {lat!r}" for lat, lon in coords) + ")"

def claim_first_available(session: Session, candidates: list[Candidate]) -> Candidate:
    """Claim the first candidate which is still idle with one atomic UPDATE per try.
       0 rows updated means someone else got that vehicle first so try next one."""
    for candidate in candidates:
        result = session.execute(
            update(Vehicle)
            .where(Vehicle.id == candidate.vehicle_id, Vehicle.status == VehicleStatus.IDLE.value)
            .values(status=VehicleStatus.TO_PICKUP.value)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 1:
            return candidate
    return None

def _route_row(city: City, delivery_id: uuid.UUID, leg_name: RouteLeg, leg: Leg) -> Route:
    wkt = linestring_wkt(city.coordinates(leg.nodes))
    return Route(
        delivery_id=delivery_id,
        leg=leg_name.value,
        distance_m=leg.distance_m,
        geometry=WKTElement(wkt, srid=4326) if wkt else None,
    )

def create_delivery(session: Session, city: City, pickup: Point, dropoff: Point, max_snap_m: float) -> uuid.UUID:
    """Plan, pick the nearest idle vehicle, save everything. `session` must be fresh."""
    plan = plan_trip(city, pickup, dropoff, max_snap_m)

    with session.begin():
        idle = session.execute(
            select(Vehicle.id, Vehicle.current_lat, Vehicle.current_lon)
            .where(Vehicle.status == VehicleStatus.IDLE.value)
        ).all()
    if not idle:
        raise DomainError("no_idle_vehicle", "no idle vehicle is available", 409)

    candidates = rank_candidates(city, [(r.id, r.current_lat, r.current_lon) for r in idle], plan.pickup_node)
    if not candidates:
        raise DomainError("route_not_found", "no idle vehicle can reach the pickup", 422)

    with session.begin():
        chosen = claim_first_available(session, candidates)
        if chosen is None:
            raise DomainError("no_idle_vehicle", "every candidate vehicle was taken by another request", 409)
        delivery = Delivery(
            vehicle_id=chosen.vehicle_id,
            pickup_lat=pickup.lat, pickup_lon=pickup.lon,
            dropoff_lat=dropoff.lat, dropoff_lon=dropoff.lon,
        )
        session.add(delivery)
        session.flush()
        session.add(_route_row(city, delivery.id, RouteLeg.TO_PICKUP, chosen.leg))
        session.add(_route_row(city, delivery.id, RouteLeg.TO_DROPOFF, plan.dropoff_leg))
    return delivery.id