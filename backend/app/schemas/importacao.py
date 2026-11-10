from pydantic import BaseModel, ConfigDict, Field


class ErroImportacao(BaseModel):
    linha: int
    campo: str | None = None
    erro: str


class ResultadoImportacao(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_linhas: int = Field(..., description="Total de registros processados")
    sucessos: int = Field(..., description="Total de registros inseridos ou atualizados com sucesso")
    inseridos: int = Field(..., description="Novos equipamentos cadastrados")
    atualizados: int = Field(..., description="Equipamentos existentes atualizados")
    falhas: int = Field(..., description="Total de linhas rejeitadas por erro")
    erros: list[ErroImportacao] = Field(default_factory=list, description="Detalhamento das falhas encontradas")
