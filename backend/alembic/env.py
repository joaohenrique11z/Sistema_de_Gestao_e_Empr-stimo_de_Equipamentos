"""Ambiente do Alembic: usa DATABASE_URL das configurações da aplicação."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401  (regista todas as tabelas no metadata)
from app.config import get_settings
from app.database import Base
from app.models.types import UTCDateTime

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().DATABASE_URL.replace("%", "%%"))

target_metadata = Base.metadata


def render_item(type_, obj, autogen_context):
    """Renderiza o tipo customizado UTCDateTime como DateTime(timezone=True)."""
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime(timezone=True)"
    return False


def _is_sqlite() -> bool:
    return config.get_main_option("sqlalchemy.url", "").startswith("sqlite")


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_item=render_item,
        render_as_batch=_is_sqlite(),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_item=render_item,
            render_as_batch=_is_sqlite(),
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
