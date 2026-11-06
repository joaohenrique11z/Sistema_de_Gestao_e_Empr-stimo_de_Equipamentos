from datetime import datetime

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import UTCDateTime, utcnow


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    tentativas_falhas: Mapped[int] = mapped_column(Integer, default=0)
    bloqueado_ate: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    atualizado_em: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

