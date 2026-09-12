from __future__ import annotations

from logging.config import fileConfig

import alembic.context as alembic_context  # pyright: ignore[reportMissingImports]
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.core.database import Base

config = alembic_context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    alembic_context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with alembic_context.begin_transaction():
        alembic_context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        alembic_context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with alembic_context.begin_transaction():
            alembic_context.run_migrations()


if alembic_context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
