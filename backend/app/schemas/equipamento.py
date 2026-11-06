from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models import StatusEquipamento, TipoMovimentacao
from app.schemas.responsavel import ResponsavelResumo

CODIGO_PATTERN = r"^[A-Za-z0-9._/\-]+$"

Codigo = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_upper=True, min_length=1, max_length=50, pattern=CODIGO_PATTERN),
]
NomeEquipamento = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=150)]
Texto80 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Valor = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class TipoBuscaCodigo(str, Enum):
    QUALQUER = "qualquer"
    PATRIMONIO = "patrimonio"
    INTERNO = "interno"


# --------------------------------------------------------------------------- #
# Acessórios
# --------------------------------------------------------------------------- #
class AcessorioIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: int | None = Field(
        default=None,
        description="Informe o id para manter/atualizar um acessório já vinculado (apenas no PUT).",
    )
    nome: str = Field(min_length=1, max_length=120)
    descricao: str | None = Field(default=None, max_length=255)
    numero_serie: str | None = Field(default=None, max_length=100)
    quantidade: int = Field(default=1, ge=1, le=1000)


class AcessorioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    descricao: str | None
    numero_serie: str | None
    quantidade: int
    vinculado_em: datetime


# --------------------------------------------------------------------------- #
# Equipamentos
# --------------------------------------------------------------------------- #
class EquipamentoCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    codigo_patrimonio: Codigo
    codigo_interno: Codigo
    nome: NomeEquipamento
    descricao: str | None = Field(default=None, max_length=2000)
    categoria: Texto80 | None = None
    marca: Texto80 | None = None
    modelo: Texto80 | None = None
    numero_serie: str | None = Field(default=None, max_length=100)
    status: StatusEquipamento = StatusEquipamento.DISPONIVEL
    localizacao: str | None = Field(default=None, max_length=120)
    data_aquisicao: date | None = None
    valor_aquisicao: Valor | None = None
    responsavel_id: int | None = Field(default=None, ge=1)
    acessorios: list[AcessorioIn] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _acessorios_novos_sem_id(self) -> "EquipamentoCreate":
        if any(a.id is not None for a in self.acessorios):
            raise ValueError("Acessórios de um novo equipamento não devem informar 'id'.")
        return self


class EquipamentoUpdate(BaseModel):
    """Atualização parcial. Se ``acessorios`` for enviado, a lista de vínculos é sincronizada."""

    model_config = ConfigDict(str_strip_whitespace=True)

    codigo_patrimonio: Codigo | None = None
    codigo_interno: Codigo | None = None
    nome: NomeEquipamento | None = None
    descricao: str | None = Field(default=None, max_length=2000)
    categoria: Texto80 | None = None
    marca: Texto80 | None = None
    modelo: Texto80 | None = None
    numero_serie: str | None = Field(default=None, max_length=100)
    status: StatusEquipamento | None = None
    localizacao: str | None = Field(default=None, max_length=120)
    data_aquisicao: date | None = None
    valor_aquisicao: Valor | None = None
    responsavel_id: int | None = Field(default=None, ge=1)
    acessorios: list[AcessorioIn] | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def _campos_obrigatorios_nao_nulos(self) -> "EquipamentoUpdate":
        for campo in ("codigo_patrimonio", "codigo_interno", "nome", "status"):
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"O campo '{campo}' não pode ser nulo.")
        return self


class EquipamentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo_patrimonio: str
    codigo_interno: str
    nome: str
    descricao: str | None
    categoria: str | None
    marca: str | None
    modelo: str | None
    numero_serie: str | None
    status: StatusEquipamento
    localizacao: str | None
    data_aquisicao: date | None
    valor_aquisicao: Decimal | None
    responsavel_id: int | None
    responsavel: ResponsavelResumo | None
    acessorios: list[AcessorioOut]
    criado_em: datetime
    atualizado_em: datetime


class MovimentacaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    equipamento_id: int
    tipo: TipoMovimentacao
    descricao: str
    detalhes: dict[str, Any] | None
    usuario_id: int | None
    criado_em: datetime

