"""Configuração do SQLAlchemy: engine, sessão, base declarativa e unidade de trabalho."""

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings


class Base(DeclarativeBase):
    """Base declarativa de todos os modelos ORM."""


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _is_sqlite_memory(url: str) -> bool:
    return _is_sqlite(url) and (":memory:" in url or url.rstrip("/").endswith(":"))


def build_engine(url: str, echo: bool = False) -> Engine:
    kwargs: dict[str, Any] = {"echo": echo}

    if _is_sqlite(url):
        kwargs["connect_args"] = {"check_same_thread": False}
        if _is_sqlite_memory(url):
            # Mantém uma única conexão para que o banco em memória seja compartilhado.
            kwargs["poolclass"] = StaticPool
    else:
        kwargs["pool_pre_ping"] = True

    new_engine = create_engine(url, **kwargs)

    if _is_sqlite(url):

        @event.listens_for(new_engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _record) -> None:  # pragma: no cover
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return new_engine


settings = get_settings()

engine = build_engine(settings.DATABASE_URL, settings.DATABASE_ECHO)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Dependência do FastAPI que fornece uma sessão por requisição."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def transaction(db: Session) -> Iterator[Session]:
    """Unidade de trabalho atómica.

    Tudo o que for executado dentro do bloco é confirmado num único COMMIT.
    Qualquer exceção provoca ROLLBACK automático e é propagada.
    """
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise

