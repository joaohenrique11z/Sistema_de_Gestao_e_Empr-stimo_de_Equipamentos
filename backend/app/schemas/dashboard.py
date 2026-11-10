from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DashboardContadores(BaseModel):
    total_equipamentos: int = Field(..., description="Total de equipamentos cadastrados")
    disponiveis: int = Field(..., description="Equipamentos disponíveis para empréstimo")
    emprestados: int = Field(..., description="Equipamentos atualmente emprestados")
    em_manutencao: int = Field(..., description="Equipamentos em manutenção")
    baixados: int = Field(..., description="Equipamentos baixados/descartados")
    total_responsaveis_ativos: int = Field(..., description="Total de responsáveis ativos aptos a empréstimos")


class UltimaMovimentacaoOut(BaseModel):
    id: int
    equipamento_id: int
    equipamento_nome: str
    tipo: str
    descricao: str
    criado_em: datetime
    usuario_id: int | None = None


class PendenciaEmprestimoOut(BaseModel):
    equipamento_id: int
    codigo_patrimonio: str
    codigo_interno: str
    nome: str
    responsavel_id: int
    responsavel_nome: str
    data_emprestimo: datetime
    dias_emprestado: int


class DashboardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    contadores: DashboardContadores
    pendencias: list[PendenciaEmprestimoOut]
    ultimas_movimentacoes: list[UltimaMovimentacaoOut]
