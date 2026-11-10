from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models import Usuario
from app.schemas.emprestimo import (
    DevolucaoRequest,
    DevolucaoResponse,
    EmprestimoAbertoOut,
    EmprestimoCreate,
    EmprestimoResponse,
)
from app.services import EmprestimoService

router = APIRouter(prefix="/emprestimos", tags=["Empréstimos e Devoluções"])


@router.post(
    "",
    response_model=EmprestimoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Realiza o empréstimo transacional de equipamentos",
)
def realizar_emprestimo(
    dados: EmprestimoCreate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmprestimoResponse:
    """Empresta equipamentos a um responsável com verificação de disponibilidade e vínculo automático de acessórios."""
    return EmprestimoService(db).realizar_emprestimo(dados, usuario=usuario)


@router.post(
    "/devolver",
    response_model=DevolucaoResponse,
    summary="Registra a devolução de um equipamento",
)
def realizar_devolucao(
    dados: DevolucaoRequest,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DevolucaoResponse:
    """Devolve equipamento emprestado, permitindo direcioná-lo para MANUTENCAO se houver danos ou DISPONIVEL."""
    return EmprestimoService(db).realizar_devolucao(dados, usuario=usuario)


@router.get(
    "/abertos",
    response_model=list[EmprestimoAbertoOut],
    summary="Consulta empréstimos em aberto",
)
def listar_emprestimos_abertos(
    responsavel_id: int | None = Query(None, description="Filtrar por responsável"),
    equipamento_id: int | None = Query(None, description="Filtrar por equipamento"),
    _usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[EmprestimoAbertoOut]:
    """Retorna a lista de todos os equipamentos que estão atualmente emprestados."""
    return EmprestimoService(db).listar_abertos(
        responsavel_id=responsavel_id, equipamento_id=equipamento_id
    )
