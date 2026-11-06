from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import EmailStr
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.exceptions import BusinessRuleError
from app.core.validators import cpf_valido, somente_digitos
from app.database import get_db
from app.models import Responsavel
from app.schemas.common import Pagina
from app.schemas.responsavel import (
    ResponsavelCreate,
    ResponsavelOut,
    ResponsavelUpdate,
    VerificacaoDuplicidade,
)
from app.services import ResponsavelService

router = APIRouter(
    prefix="/responsaveis",
    tags=["Responsáveis"],
    dependencies=[Depends(get_current_user)],
)


def get_service(db: Session = Depends(get_db)) -> ResponsavelService:
    return ResponsavelService(db)


Service = Annotated[ResponsavelService, Depends(get_service)]


@router.get("", response_model=Pagina[ResponsavelOut], summary="Lista e busca responsáveis")
def listar_responsaveis(
    service: Service,
    q: Annotated[str | None, Query(max_length=150, description="Busca por nome, e-mail, matrícula ou CPF")] = None,
    ativo: bool | None = None,
    departamento: Annotated[str | None, Query(max_length=100)] = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamanho_pagina: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Pagina[ResponsavelOut]:
    return service.listar(
        termo=q, ativo=ativo, departamento=departamento, pagina=pagina, tamanho_pagina=tamanho_pagina
    )


@router.get(
    "/verificar-duplicidade",
    response_model=VerificacaoDuplicidade,
    summary="Verifica previamente se CPF, e-mail ou matrícula já estão cadastrados",
)
def verificar_duplicidade(
    service: Service,
    cpf: str | None = None,
    email: EmailStr | None = None,
    matricula: Annotated[str | None, Query(max_length=30)] = None,
    excluir_id: Annotated[int | None, Query(ge=1, description="Ignora este responsável (edição)")] = None,
) -> VerificacaoDuplicidade:
    if not any((cpf, email, matricula)):
        raise BusinessRuleError("Informe ao menos um dos parâmetros: cpf, email ou matricula.")
    if cpf is not None and not cpf_valido(cpf):
        raise BusinessRuleError("CPF inválido.")
    return service.verificar_duplicidade(
        cpf=somente_digitos(cpf) if cpf else None,
        email=email,
        matricula=matricula.strip() if matricula else None,
        excluir_id=excluir_id,
    )


@router.post("", response_model=ResponsavelOut, status_code=status.HTTP_201_CREATED, summary="Cadastra responsável")
def criar_responsavel(dados: ResponsavelCreate, service: Service) -> Responsavel:
    return service.criar(dados)


@router.get("/{responsavel_id}", response_model=ResponsavelOut, summary="Obtém um responsável")
def obter_responsavel(responsavel_id: int, service: Service) -> Responsavel:
    return service.obter(responsavel_id)


@router.put("/{responsavel_id}", response_model=ResponsavelOut, summary="Atualiza um responsável")
def atualizar_responsavel(responsavel_id: int, dados: ResponsavelUpdate, service: Service) -> Responsavel:
    return service.atualizar(responsavel_id, dados)


@router.delete("/{responsavel_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove um responsável")
def remover_responsavel(responsavel_id: int, service: Service) -> Response:
    service.remover(responsavel_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

