"""Synthetic delivery requests. Seeded: the same seed gives the same trips and waits."""

import logging
import random
import uuid
from sqlalchemy.orm import Session, sessionmaker

from app.core.assignment import create_delivery
from app.core.engine_bridge import City
from app.core.errors import DomainError
from app.schemas.geo import Point

log = logging.getLogger(__name__)

Trip = tuple[Point, Point]      # (pickup, dropoff)


class RequestGenerator:
    def __init__(self, city: City, seed: int, min_interval_s: float, max_interval_s: float) -> None:
        if city.node_count < 2:
            raise ValueError("need at least two graph nodes to make a trip")
        if not 0 < min_interval_s <= max_interval_s:
            raise ValueError("intervals must satisfy 0 < min <= max")
        self._city = city
        self._min = min_interval_s
        self._max = max_interval_s
        # two separate streams, so the trips don't change if the waits are drawn differently
        self._trip_rng = random.Random(f"{seed}:trips")
        self._interval_rng = random.Random(f"{seed}:intervals")

    def next_trip(self) -> Trip:
        """Two different graph nodes, as their exact coordinates: 
           always inside the map and on a road."""
        pickup, dropoff = self._trip_rng.sample(range(self._city.node_count), 2)
        (plat, plon), (dlat, dlon) = self._city.coordinates([pickup, dropoff])
        return Point(lat=plat, lon=plon), Point(lat=dlat, lon=dlon)

    def next_interval_s(self) -> float:
        """Seconds to wait before the next request."""
        return self._interval_rng.uniform(self._min, self._max)


def request_delivery(session_factory: sessionmaker[Session], city: City, trip: Trip, max_snap_m: float) -> uuid.UUID | None:
    """Send one generated trip through create_delivery. Returns the delivery id, or None
       if the request was skipped. Never raises, so the generator loop never dies on one request."""
    pickup, dropoff = trip
    try:
        with session_factory() as session:  # create_delivery needs a fresh session
            delivery_id = create_delivery(session, city, pickup, dropoff, max_snap_m)
    except DomainError as err:
        # no idle vehicle is expected when the fleet is busy; anything else is unusual
        level = logging.INFO if err.code == "no_idle_vehicle" else logging.WARNING
        log.log(level, "generated request skipped: %s (%s)", err.code, err.message)
        return None
    except Exception:
        log.exception("generated request failed; skipped")
        return None
    log.info("generated delivery %s", delivery_id)
    return delivery_id