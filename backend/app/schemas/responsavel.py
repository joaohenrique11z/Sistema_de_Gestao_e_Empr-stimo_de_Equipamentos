from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.core.validators import normalizar_cpf

CPF = Annotated[
    str,
    Field(min_length=11, max_length=14, examples=["529.982.247-25"]),
    AfterValidator(normalizar_cpf),
]
Email = Annotated[EmailStr, AfterValidator(lambda v: v.lower())]
Nome = Annotated[str, Field(min_length=3, max_length=150)]
Matricula = Annotated[str, Field(min_length=1, max_length=30), AfterValidator(lambda v: v.upper())]
Telefone = Annotated[str, Field(min_length=8, max_length=20)]
Departamento = Annotated[str, Field(min_length=1, max_length=100)]


class _ResponsavelSchema(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class ResponsavelCreate(_ResponsavelSchema):
    nome: Nome
    cpf: CPF
    email: Email
    matricula: Matricula | None = None
    telefone: Telefone | None = None
    departamento: Departamento | None = None
    ativo: bool = True


class ResponsavelUpdate(_ResponsavelSchema):
    """Atualização parcial: apenas os campos enviados são alterados."""

    nome: Nome | None = None
    cpf: CPF | None = None
    email: Email | None = None
    matricula: Matricula | None = None
    telefone: Telefone | None = None
    departamento: Departamento | None = None
    ativo: bool | None = None

    @model_validator(mode="after")
    def _campos_obrigatorios_nao_nulos(self) -> "ResponsavelUpdate":
        for campo in ("nome", "cpf", "email", "ativo"):
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"O campo '{campo}' não pode ser nulo.")
        return self


class ResponsavelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    cpf: str
    email: str
    matricula: str | None
    telefone: str | None
    departamento: str | None
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime


class ResponsavelResumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: str


class ConflitoDuplicidade(BaseModel):
    campo: str
    valor: str
    responsavel_id: int


class VerificacaoDuplicidade(BaseModel):
    duplicado: bool
    conflitos: list[ConflitoDuplicidade]

