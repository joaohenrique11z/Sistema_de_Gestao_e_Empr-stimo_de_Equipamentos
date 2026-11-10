from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.equipamento import StatusEquipamento


class EmprestimoCreate(BaseModel):
    responsavel_id: int = Field(..., gt=0, description="ID do responsável que está retirando os equipamentos")
    equipamento_ids: list[int] = Field(..., min_length=1, description="Lista de IDs dos equipamentos a emprestar")
    previsao_devolucao: datetime | None = Field(default=None, description="Previsão de devolução")
    observacoes: str | None = Field(default=None, max_length=500, description="Observações do empréstimo")


class ItemEmprestadoOut(BaseModel):
    equipamento_id: int
    codigo_patrimonio: str
    codigo_interno: str
    nome: str
    acessorios: list[str] = Field(default_factory=list, description="Nomes dos acessórios que acompanham o equipamento")


class EmprestimoResponse(BaseModel):
    responsavel_id: int
    responsavel_nome: str
    data_emprestimo: datetime
    previsao_devolucao: datetime | None = None
    observacoes: str | None = None
    itens: list[ItemEmprestadoOut]


class DevolucaoRequest(BaseModel):
    equipamento_id: int = Field(..., gt=0, description="ID do equipamento sendo devolvido")
    status_destino: Literal["DISPONIVEL", "MANUTENCAO", "BAIXADO"] = Field(
        default="DISPONIVEL",
        description="Status para o qual o equipamento deve ir após a devolução (DISPONIVEL por padrão, MANUTENCAO se houver avaria)"
    )
    avarias: str | None = Field(default=None, max_length=500, description="Descrição de eventuais avarias ou danos")
    observacoes: str | None = Field(default=None, max_length=500, description="Observações da devolução")


class DevolucaoResponse(BaseModel):
    equipamento_id: int
    codigo_patrimonio: str
    status_novo: str
    data_devolucao: datetime
    avarias: str | None = None
    observacoes: str | None = None


class EmprestimoAbertoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    equipamento_id: int
    codigo_patrimonio: str
    codigo_interno: str
    nome: str
    categoria: str | None = None
    localizacao: str | None = None
    responsavel_id: int
    responsavel_nome: str
    responsavel_matricula: str | None = None
    responsavel_email: str
    data_emprestimo: datetime
    acessorios: list[str] = Field(default_factory=list)
