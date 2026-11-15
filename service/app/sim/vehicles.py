"""Vehicle movement"""

import math
import json
import logging
import math
import uuid
from collections.abc import Sequence
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Delivery, DeliveryStatus, Route, RouteLeg, Vehicle, VehicleStatus

log = logging.getLogger(__name__)

# Same earth radius as engine/include/geo.hpp
EARTH_RADIUS_M = 6371000.0

Point = tuple[float, float]     # (lat, lon), the same order as the API paths

def _haversine_m(a: Point, b: Point) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))

def advance_progress(progress_m: float, step_m: float, distance_m: float) -> tuple[float, bool]:
    """Drive `step_m` further along a leg that is `distance_m` long.
       Returns (new progress, finished). Progress never goes past the end of the leg."""
    if progress_m < 0 or step_m < 0 or distance_m < 0:
        raise ValueError("progress, step and distance must not be negative")
    new = progress_m + step_m
    if new >= distance_m:
        return distance_m, True
    return new, False

def position_on_line(points: Sequence[Point], progress_m: float, distance_m: float) -> Point:
    """Where a car is after `progress_m` of a leg that is `distance_m` long.
       The same fraction of the drawn line. At or past the end it is exactly the last point."""
    if len(points) < 2:
        raise ValueError("a line needs at least two points")
    if distance_m <= 0:
        raise ValueError("distance_m must be positive")
    if progress_m < 0:
        raise ValueError("progress_m must not be negative")
    if progress_m == 0:
        return points[0]
    if progress_m >= distance_m:
        return points[-1]

    pairs = list(zip(points, points[1:]))
    lengths = [_haversine_m(a, b) for a, b in pairs]
    total = sum(lengths)
    if total == 0:
        return points[-1]

    target = progress_m / distance_m * total
    walked = 0.0
    for (a, b), length in zip(pairs, lengths):
        if length > 0 and walked + length >= target:
            t = (target - walked) / length
            if t >= 1.0:
                return b
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        walked += length
    return points[-1]

def _points_from_geojson(geojson) -> list[Point] | None:
    if geojson is None:
        return None
    data = geojson if isinstance(geojson, dict) else json.loads(geojson)
    # GeoJSON is [lon, lat]; this module uses (lat, lon)
    return [(lat, lon) for lon, lat in data["coordinates"]]

def advance_vehicle(session: Session, vehicle_id: uuid.UUID, step_m: float) -> bool:
    """Move one vehicle `step_m` along its current leg in one transaction.
       `session` must be fresh. True if vehicle moved, False if it was skipped."""
    with session.begin():
        vehicle = session.get(Vehicle, vehicle_id)
        if vehicle is None or vehicle.status == VehicleStatus.IDLE.value:
            return False

        to_pickup = vehicle.status == VehicleStatus.TO_PICKUP.value
        leg = RouteLeg.TO_PICKUP if to_pickup else RouteLeg.TO_DROPOFF
        expected = DeliveryStatus.ASSIGNED if to_pickup else DeliveryStatus.PICKED_UP

        delivery = session.scalar(
            select(Delivery).where(
                Delivery.vehicle_id == vehicle.id, Delivery.status == expected.value
            )
        )
        if delivery is None:
            log.warning("vehicle %s is %s but has no matching delivery (%s); skipped", vehicle.id, vehicle.status, expected.value)
            return False

        row = session.execute(
            select(Route.distance_m, func.ST_AsGeoJSON(Route.geometry)).where(
                Route.delivery_id == delivery.id, Route.leg == leg.value
            )
        ).one_or_none()
        if row is None:
            log.warning("delivery %s has no %s route; vehicle %s skipped", delivery.id, leg.value, vehicle.id)
            return False
        distance_m, geojson = row
        points = _points_from_geojson(geojson)
        if distance_m > 0 and points is None:
            log.warning("delivery %s %s route has no geometry; vehicle %s skipped", delivery.id, leg.value, vehicle.id)
            return False

        progress, finished = advance_progress(vehicle.leg_progress_m, step_m, distance_m)
        if finished:
            if points:  # a zero-length leg has no line; the car is already there
                vehicle.current_lat, vehicle.current_lon = points[-1]
            progress = 0.0
            if to_pickup:
                    delivery.status = DeliveryStatus.PICKED_UP.value
                    vehicle.status = VehicleStatus.TO_DROPOFF.value
            else:
                delivery.status = DeliveryStatus.DELIVERED.value
                vehicle.status = VehicleStatus.IDLE.value
        else:
            vehicle.current_lat, vehicle.current_lon = position_on_line(points, progress, distance_m)
        vehicle.leg_progress_m = progress
        return True

def step_fleet(session_factory: sessionmaker[Session], step_m: float) -> int:
    """One tick: move every busy vehicle `step_m`. A vehicle that fails is logged and
       skipped, so the others still movoe.
       Returns how many vehicles moved."""
    with session_factory() as session, session.begin():
        busy = session.scalars(select(Vehicle.id).where(Vehicle.status != VehicleStatus.IDLE.value).order_by(Vehicle.id)).all()

    moved = 0
    for vehicle_id in busy:
        try:
            with session_factory() as session:
                if advance_vehicle(session, vehicle_id, step_m):
                    moved += 1
        except Exception:
            log.exception("vehicle %s failed this tick; skipped", vehicle_id)
    return moved