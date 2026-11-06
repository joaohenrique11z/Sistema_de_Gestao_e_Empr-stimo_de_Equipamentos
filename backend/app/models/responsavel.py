from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.types import UTCDateTime, utcnow

if TYPE_CHECKING:
    from app.models.equipamento import Equipamento


class Responsavel(Base):
    __tablename__ = "responsaveis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(150), index=True)
    cpf: Mapped[str] = mapped_column(String(11), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    matricula: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    departamento: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    atualizado_em: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    equipamentos: Mapped[list["Equipamento"]] = relationship(back_populates="responsavel")

