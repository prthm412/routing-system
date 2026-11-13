from alembic import context
from sqlalchemy import create_engine, pool

from app.config import get_settings

config = context.config


def run_migrations_online() -> None:
    # tests pass a URL through config.attributes; otherwise use the app settings
    url = config.attributes.get("url") or get_settings().database_url()
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


# Online mode only; `alembic upgrade --sql` is not supported here.
run_migrations_online()