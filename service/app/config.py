from functools import lru_cache

from pydantic_settings import BaseSettings
from sqlalchemy.engine import URL
from pydantic import Field

class Settings(BaseSettings):
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "db"
    postgres_port: int = 5432

    graph_path: str = "/data/processed/nyc.graph"
    # measured on real graph: land spots snapped within 74-218m
    max_snap_distance_m: float = 300.0
    fleet_size: int = 5
    fleet_seed: int = 42

    # Synthetic delivery requests. Placeholders until tuned by watching the cars.
    generator_seed: int = 42
    generator_min_interval_s: float = 20.0
    generator_max_interval_s: float = 60.0

    # Simulation. The speed is a simulation assumption, not observed traffic.
    simulation_enabled: bool = False
    vehicle_speed_mps: float = Field(default=12.0, gt=0)
    sim_tick_s: float = Field(default=1.0, gt=0)

    def database_url(self, database: str | None = None) -> URL:
        # URL.create escapes special characters in password
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=database or self.postgres_db,
        )

@lru_cache
def get_settings() -> Settings:
    return Settings()