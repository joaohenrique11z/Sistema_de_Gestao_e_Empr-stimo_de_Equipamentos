from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models import Equipamento, Movimentacao, StatusEquipamento, Usuario
from app.repositories import FiltrosEquipamento
from app.schemas.common import Pagina
from app.schemas.equipamento import (
    EquipamentoCreate,
    EquipamentoOut,
    EquipamentoUpdate,
    MovimentacaoOut,
    TipoBuscaCodigo,
)
from app.services import EquipamentoService

router = APIRouter(
    prefix="/equipamentos",
    tags=["Equipamentos"],
    dependencies=[Depends(get_current_user)],
)


def get_service(db: Session = Depends(get_db)) -> EquipamentoService:
    return EquipamentoService(db)


Service = Annotated[EquipamentoService, Depends(get_service)]
UsuarioAtual = Annotated[Usuario, Depends(get_current_user)]


def filtros_equipamento(
    busca: Annotated[
        str | None,
        Query(max_length=150, description="Texto em nome, descrição, códigos, marca, modelo ou nº de série"),
    ] = None,
    status_: Annotated[
        list[StatusEquipamento] | None,
        Query(alias="status", description="Um ou mais status (repita o parâmetro)"),
    ] = None,
    categoria: Annotated[str | None, Query(max_length=80)] = None,
    marca: Annotated[str | None, Query(max_length=80)] = None,
    localizacao: Annotated[str | None, Query(max_length=120)] = None,
    responsavel_id: Annotated[int | None, Query(ge=1)] = None,
    sem_responsavel: bool | None = None,
    possui_acessorios: bool | None = None,
    data_aquisicao_inicio: date | None = None,
    data_aquisicao_fim: date | None = None,
    valor_min: Annotated[Decimal | None, Query(ge=0)] = None,
    valor_max: Annotated[Decimal | None, Query(ge=0)] = None,
) -> FiltrosEquipamento:
    return FiltrosEquipamento(
        busca=busca,
        status=status_ or [],
        categoria=categoria,
        marca=marca,
        localizacao=localizacao,
        responsavel_id=responsavel_id,
        sem_responsavel=sem_responsavel,
        possui_acessorios=possui_acessorios,
        data_aquisicao_inicio=data_aquisicao_inicio,
        data_aquisicao_fim=data_aquisicao_fim,
        valor_min=valor_min,
        valor_max=valor_max,
    )


@router.post(
    "",
    response_model=EquipamentoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra equipamento, vincula acessórios e regista a movimentação (transação única)",
)
def criar_equipamento(dados: EquipamentoCreate, service: Service, usuario: UsuarioAtual) -> Equipamento:
    return service.criar(dados, usuario)


@router.get(
    "",
    response_model=Pagina[EquipamentoOut],
    summary="Lista equipamentos com paginação, filtros combinados e ordenação dinâmica",
)
def listar_equipamentos(
    service: Service,
    filtros: Annotated[FiltrosEquipamento, Depends(filtros_equipamento)],
    ordenar_por: Annotated[
        str | None,
        Query(
            max_length=200,
            description="Campos separados por vírgula; prefixo '-' para ordem decrescente. Ex.: -criado_em,nome",
        ),
    ] = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamanho_pagina: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Pagina[EquipamentoOut]:
    return service.listar(filtros, ordenar_por=ordenar_por, pagina=pagina, tamanho_pagina=tamanho_pagina)


@router.get(
    "/codigo/{codigo:path}",
    response_model=EquipamentoOut,
    summary="Busca equipamento pelo código de património ou código interno",
)
def buscar_por_codigo(
    service: Service,
    codigo: Annotated[str, Path(min_length=1, max_length=50)],
    tipo: TipoBuscaCodigo = TipoBuscaCodigo.QUALQUER,
) -> Equipamento:
    return service.obter_por_codigo(codigo, tipo)


@router.get("/{equipamento_id}", response_model=EquipamentoOut, summary="Obtém um equipamento")
def obter_equipamento(equipamento_id: int, service: Service) -> Equipamento:
    return service.obter(equipamento_id)


@router.put(
    "/{equipamento_id}",
    response_model=EquipamentoOut,
    summary="Atualiza equipamento, sincroniza acessórios e regista movimentações (transação única)",
)
def atualizar_equipamento(
    equipamento_id: int, dados: EquipamentoUpdate, service: Service, usuario: UsuarioAtual
) -> Equipamento:
    return service.atualizar(equipamento_id, dados, usuario)


@router.get(
    "/{equipamento_id}/movimentacoes",
    response_model=list[MovimentacaoOut],
    summary="Histórico de movimentações do equipamento",
)
def listar_movimentacoes(equipamento_id: int, service: Service) -> list[Movimentacao]:
    return service.listar_movimentacoes(equipamento_id)

