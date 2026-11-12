import uuid
from dataclasses import dataclass

from app.core.engine_bridge import City
from app.core.errors import DomainError
from app.schemas.geo import Point

# Bounding box from ADR 0001
MAP_WEST = -74.020
MAP_SOUTH = 40.700
MAP_EAST = -73.965
MAP_NORTH = 40.765


@dataclass(frozen=True)
class Leg:
    distance_m: float
    nodes: list[int]


@dataclass(frozen=True)
class TripPlan:
    pickup_node: int
    dropoff_node: int
    dropoff_leg: Leg    # pickup --> dropoff


@dataclass(frozen=True)
class Candidate:
    vehicle_id: uuid.UUID
    leg: Leg            # vehicle --> pickup


def check_inside_map(name: str, point: Point) -> None:
    inside = MAP_SOUTH <= point.lat <= MAP_NORTH and MAP_WEST <= point.lon <= MAP_EAST
    if not inside:
        raise DomainError("outside_map", f"{name} is outside the supported map area", 422)

def snap_to_road(city: City, name: str, point: Point, max_snap_m: float) -> int:
    snap = city.snap(point.lat, point.lon)
    if snap.distance_m > max_snap_m:
        raise DomainError("too_far_from_road", f"{name} is {snap.distance_m:.0f} m from the nearest road node(limit {max_snap_m:.0f} m)", 422,)
    return snap.node

def plan_trip(city: City, pickup: Point, dropoff: Point, max_snap_m: float) -> TripPlan:
    check_inside_map("pickup", pickup)
    check_inside_map("dropoff", dropoff)
    pickup_node = snap_to_road(city, "pickup", pickup, max_snap_m)
    dropoff_node = snap_to_road(city, "dropoff", dropoff, max_snap_m)
    if pickup_node == dropoff_node:
        raise DomainError("same_location", "pickup and dropoff snap to the same road node", 422)
    route = city.find_route(pickup_node, dropoff_node)
    if not route.found:
        raise DomainError("route_not_found", "there is no route from pickup to dropoff", 422)
    return TripPlan(pickup_node, dropoff_node, Leg(route.distance_m, list(route.nodes)))

def rank_candidates(city: City, vehicles: list[tuple[uuid.UUID, float, float]], pickup_node: int) -> list[Candidate]:
    """Vehicles that can reach the pickup, nearest by road distance first, ties by lowest id.
       Each vehicle is (id, lat, lon)."""
    candidates = []
    for vehicle_id, lat, lon in vehicles:
        start = city.snap(lat, lon).node
        route = city.find_route(start, pickup_node)
        if route.found:
            candidates.append(Candidate(vehicle_id, Leg(route.distance_m, list(route.nodes))))
    candidates.sort(key=lambda c: (c.leg.distance_m, c.vehicle_id))
    return candidates