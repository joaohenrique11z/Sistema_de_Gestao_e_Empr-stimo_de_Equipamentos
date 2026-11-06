import enum
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Date, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.types import UTCDateTime, utcnow

if TYPE_CHECKING:
    from app.models.responsavel import Responsavel


class StatusEquipamento(str, enum.Enum):
    DISPONIVEL = "DISPONIVEL"
    EMPRESTADO = "EMPRESTADO"
    MANUTENCAO = "MANUTENCAO"
    BAIXADO = "BAIXADO"


class TipoMovimentacao(str, enum.Enum):
    CADASTRO = "CADASTRO"
    ATUALIZACAO = "ATUALIZACAO"
    VINCULO_ACESSORIO = "VINCULO_ACESSORIO"
    DESVINCULO_ACESSORIO = "DESVINCULO_ACESSORIO"


class Equipamento(Base):
    __tablename__ = "equipamentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo_patrimonio: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    codigo_interno: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(150), index=True)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    categoria: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    marca: Mapped[str | None] = mapped_column(String(80), nullable=True)
    modelo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    numero_serie: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[StatusEquipamento] = mapped_column(
        Enum(StatusEquipamento, native_enum=False, length=20, validate_strings=True),
        default=StatusEquipamento.DISPONIVEL,
        index=True,
    )
    localizacao: Mapped[str | None] = mapped_column(String(120), nullable=True)
    data_aquisicao: Mapped[date | None] = mapped_column(Date, nullable=True)
    valor_aquisicao: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    responsavel_id: Mapped[int | None] = mapped_column(
        ForeignKey("responsaveis.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    criado_em: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    atualizado_em: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    responsavel: Mapped["Responsavel | None"] = relationship(back_populates="equipamentos")
    acessorios: Mapped[list["Acessorio"]] = relationship(
        back_populates="equipamento",
        cascade="all, delete-orphan",
        order_by="Acessorio.id",
    )
    movimentacoes: Mapped[list["Movimentacao"]] = relationship(
        back_populates="equipamento",
        cascade="all, delete-orphan",
        order_by="Movimentacao.id",
    )


class Acessorio(Base):
    """Acessório vinculado a um equipamento (carregador, cabo, mala, etc.)."""

    __tablename__ = "acessorios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipamento_id: Mapped[int] = mapped_column(
        ForeignKey("equipamentos.id", ondelete="CASCADE"), index=True
    )
    nome: Mapped[str] = mapped_column(String(120))
    descricao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    numero_serie: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quantidade: Mapped[int] = mapped_column(Integer, default=1)
    vinculado_em: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    equipamento: Mapped[Equipamento] = relationship(back_populates="acessorios")


class Movimentacao(Base):
    """Registo histórico (auditoria) de todas as operações sobre um equipamento."""

    __tablename__ = "movimentacoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipamento_id: Mapped[int] = mapped_column(
        ForeignKey("equipamentos.id", ondelete="CASCADE"), index=True
    )
    tipo: Mapped[TipoMovimentacao] = mapped_column(
        Enum(TipoMovimentacao, native_enum=False, length=30, validate_strings=True)
    )
    descricao: Mapped[str] = mapped_column(String(255))
    detalhes: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True
    )
    criado_em: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    equipamento: Mapped[Equipamento] = relationship(back_populates="movimentacoes")

