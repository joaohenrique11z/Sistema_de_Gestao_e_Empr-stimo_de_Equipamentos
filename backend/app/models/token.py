from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import UTCDateTime, utcnow


class RefreshToken(Base):
    """Refresh tokens emitidos (permite rotação, revogação e deteção de reutilização)."""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )
    expira_em: Mapped[datetime] = mapped_column(UTCDateTime())
    revogado_em: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    substituido_por: Mapped[str | None] = mapped_column(String(64), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class TokenRevogado(Base):
    """Lista de bloqueio de access tokens invalidados no logout."""

    __tablename__ = "tokens_revogados"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expira_em: Mapped[datetime] = mapped_column(UTCDateTime())
    revogado_em: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

