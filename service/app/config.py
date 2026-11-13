from functools import lru_cache

from pydantic_settings import BaseSettings
from sqlalchemy.engine import URL

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