import os
import sys

from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from tgbot.database.database import Base
from tgbot.database.models import User
from tgbot.config import load_config

config = context.config


# if config.config_file_name is not None:
#     fileConfig(config.config_file_name, disable_existing_loggers=False)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

my_config = load_config()
config.set_main_option(
    "sqlalchemy.url",
    f"postgresql+asyncpg://{my_config.postgres.db_user}:{my_config.postgres.db_pass}"
    f"@{my_config.postgres.db_host}:5432/{my_config.postgres.db_name}",
)


# config.set_main_option(
#     "sqlalchemy.url",
#     f"postgresql+asyncpg://{my_config.postgres.db_user}:{my_config.postgres.db_pass}"
#     f"@localhost:5435/{my_config.postgres.db_name}",
# )

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    configuration = config.get_section(config.config_ini_section)
    url = configuration["sqlalchemy.url"]
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "+psycopg")
        configuration["sqlalchemy.url"] = url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
