import random
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.engine_bridge import City, load_city
from app.db.session import create_db_engine
from app.models.vehicle import Vehicle, VehicleStatus

def choose_start_nodes(node_count: int, count: int, seed: int) -> list[int]:
    # Same seed, same nodes. All distinct.
    if count < 1 or count > node_count:
        raise ValueError(f"fleet size must be between 1 and {node_count}, got {count}")
    return random.Random(seed).sample(range(node_count), count)

def seed_vehicles(session: Session, city: City, count: int, seed: int) -> int:
    # Put `count` idle vehicles on graph nodes. Does nothing if vehicles exist.
    # The caller commits. Returns how many vehicles were created.
    if session.scalar(select(func.count()).select_from(Vehicle)):
        return 0
    nodes = choose_start_nodes(city.node_count, count, seed)
    for lat, lon in city.coordinates(nodes):
        session.add(
            Vehicle(current_lat=lat, current_lon=lon, status=VehicleStatus.IDLE.value)
        )
    return count

def main() -> None:
    settings = get_settings()
    city = load_city(settings.graph_path)
    engine = create_db_engine(settings)
    with Session(engine) as session, session.begin():
        created = seed_vehicles(session, city, settings.fleet_size, settings.fleet_seed)
    engine.dispose()
    print(f"created {created} vehicles" if created else "vehicles already exist; nothing changed")

if __name__ == "__main__":
    main()