"""Criação do utilizador administrador inicial a partir das variáveis de ambiente.

Uso manual: ``python -m app.seed``
"""

import structlog
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.services import AuthService

logger = structlog.get_logger()


def bootstrap_admin() -> None:
    settings = get_settings()
    if not settings.FIRST_ADMIN_EMAIL or not settings.FIRST_ADMIN_PASSWORD:
        return

    from app.database import SessionLocal

    db = SessionLocal()
    try:
        service = AuthService(db)
        if service.usuarios.get_by_email(settings.FIRST_ADMIN_EMAIL) is None:
            service.criar_usuario(
                settings.FIRST_ADMIN_NOME, settings.FIRST_ADMIN_EMAIL, settings.FIRST_ADMIN_PASSWORD
            )
            logger.info("admin_inicial_criado", email=settings.FIRST_ADMIN_EMAIL)
    except SQLAlchemyError as exc:
        logger.warning("admin_inicial_nao_criado", erro=str(exc), dica="Execute 'alembic upgrade head'.")
    finally:
        db.close()


if __name__ == "__main__":  # pragma: no cover
    from app.logging_config import configure_logging

    configure_logging()
    bootstrap_admin()

