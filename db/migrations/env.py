import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import URL

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# No models yet: the schema is defined directly in migration scripts.
target_metadata = None


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} must be set to run migrations.")
    return value


def get_database_url() -> URL:
    """Build the DB URL from the same POSTGRES_* variables the API uses."""
    return URL.create(
        drivername="postgresql+psycopg",
        username=_require("POSTGRES_USER"),
        password=_require("POSTGRES_PASSWORD"),
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=_require("POSTGRES_DB"),
    )


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of connecting to the database."""
    context.configure(
        url=get_database_url().render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(get_database_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
