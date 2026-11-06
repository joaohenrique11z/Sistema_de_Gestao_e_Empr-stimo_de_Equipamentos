from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import Select, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import BusinessRuleError
from app.models import Acessorio, Equipamento, StatusEquipamento

# Campos permitidos na ordenação dinâmica (whitelist contra injeção).
CAMPOS_ORDENACAO = {
    "id": Equipamento.id,
    "nome": Equipamento.nome,
    "codigo_patrimonio": Equipamento.codigo_patrimonio,
    "codigo_interno": Equipamento.codigo_interno,
    "categoria": Equipamento.categoria,
    "marca": Equipamento.marca,
    "modelo": Equipamento.modelo,
    "status": Equipamento.status,
    "localizacao": Equipamento.localizacao,
    "data_aquisicao": Equipamento.data_aquisicao,
    "valor_aquisicao": Equipamento.valor_aquisicao,
    "criado_em": Equipamento.criado_em,
    "atualizado_em": Equipamento.atualizado_em,
}


def _like(termo: str) -> str:
    escapado = termo.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escapado}%"


@dataclass
class FiltrosEquipamento:
    busca: str | None = None
    status: list[StatusEquipamento] = field(default_factory=list)
    categoria: str | None = None
    marca: str | None = None
    localizacao: str | None = None
    responsavel_id: int | None = None
    sem_responsavel: bool | None = None
    possui_acessorios: bool | None = None
    data_aquisicao_inicio: date | None = None
    data_aquisicao_fim: date | None = None
    valor_min: Decimal | None = None
    valor_max: Decimal | None = None


class EquipamentoRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _base_query(self) -> Select:
        return select(Equipamento).options(
            selectinload(Equipamento.acessorios),
            selectinload(Equipamento.responsavel),
        )

    def get(self, equipamento_id: int) -> Equipamento | None:
        return self.db.scalar(self._base_query().where(Equipamento.id == equipamento_id))

    def get_by_codigo_patrimonio(self, codigo: str) -> Equipamento | None:
        return self.db.scalar(self._base_query().where(Equipamento.codigo_patrimonio == codigo.upper()))

    def get_by_codigo_interno(self, codigo: str) -> Equipamento | None:
        return self.db.scalar(self._base_query().where(Equipamento.codigo_interno == codigo.upper()))

    def add(self, equipamento: Equipamento) -> Equipamento:
        self.db.add(equipamento)
        self.db.flush()
        return equipamento

    def find_code_conflicts(
        self, codigos: dict[str, str], excluir_id: int | None = None
    ) -> list[tuple[str, str, int]]:
        """Verifica se algum código já está em uso (em qualquer das duas colunas).

        Um código nunca pode ser património de um equipamento e interno de outro,
        o que garante que a busca por código é sempre inequívoca.
        """
        conflitos: list[tuple[str, str, int]] = []
        for campo, valor in codigos.items():
            stmt = select(Equipamento.id).where(
                or_(Equipamento.codigo_patrimonio == valor, Equipamento.codigo_interno == valor)
            )
            if excluir_id is not None:
                stmt = stmt.where(Equipamento.id != excluir_id)
            existente = self.db.scalar(stmt.limit(1))
            if existente is not None:
                conflitos.append((campo, valor, existente))
        return conflitos

    # Listagem com filtros, ordenação e paginação ----------------------------- #
    def _aplicar_filtros(self, stmt: Select, f: FiltrosEquipamento) -> Select:
        if f.busca:
            like = _like(f.busca)
            stmt = stmt.where(
                or_(
                    *(
                        func.lower(coluna).like(like, escape="\\")
                        for coluna in (
                            Equipamento.nome,
                            Equipamento.descricao,
                            Equipamento.codigo_patrimonio,
                            Equipamento.codigo_interno,
                            Equipamento.marca,
                            Equipamento.modelo,
                            Equipamento.numero_serie,
                        )
                    )
                )
            )
        if f.status:
            stmt = stmt.where(Equipamento.status.in_(f.status))
        if f.categoria:
            stmt = stmt.where(func.lower(Equipamento.categoria) == f.categoria.strip().lower())
        if f.marca:
            stmt = stmt.where(func.lower(Equipamento.marca) == f.marca.strip().lower())
        if f.localizacao:
            stmt = stmt.where(func.lower(Equipamento.localizacao).like(_like(f.localizacao), escape="\\"))
        if f.responsavel_id is not None:
            stmt = stmt.where(Equipamento.responsavel_id == f.responsavel_id)
        if f.sem_responsavel is True:
            stmt = stmt.where(Equipamento.responsavel_id.is_(None))
        elif f.sem_responsavel is False:
            stmt = stmt.where(Equipamento.responsavel_id.is_not(None))
        if f.possui_acessorios is not None:
            tem_acessorio = exists().where(Acessorio.equipamento_id == Equipamento.id)
            stmt = stmt.where(tem_acessorio if f.possui_acessorios else ~tem_acessorio)
        if f.data_aquisicao_inicio:
            stmt = stmt.where(Equipamento.data_aquisicao >= f.data_aquisicao_inicio)
        if f.data_aquisicao_fim:
            stmt = stmt.where(Equipamento.data_aquisicao <= f.data_aquisicao_fim)
        if f.valor_min is not None:
            stmt = stmt.where(Equipamento.valor_aquisicao >= f.valor_min)
        if f.valor_max is not None:
            stmt = stmt.where(Equipamento.valor_aquisicao <= f.valor_max)
        return stmt

    @staticmethod
    def _ordenacao(ordenar_por: str | None) -> list:
        criterios = []
        usados: set[str] = set()
        for bruto in (ordenar_por or "").split(","):
            campo = bruto.strip()
            if not campo:
                continue
            desc = campo.startswith("-")
            nome = campo.lstrip("+-")
            coluna = CAMPOS_ORDENACAO.get(nome)
            if coluna is None:
                raise BusinessRuleError(
                    f"Campo de ordenação inválido: '{nome}'.",
                    campos_permitidos=sorted(CAMPOS_ORDENACAO),
                )
            if nome in usados:
                continue
            usados.add(nome)
            criterios.append(coluna.desc().nulls_last() if desc else coluna.asc().nulls_last())
        if "id" not in usados:
            criterios.append(Equipamento.id.asc())  # desempate estável
        return criterios

    def listar(
        self,
        filtros: FiltrosEquipamento,
        *,
        ordenar_por: str | None = None,
        pagina: int = 1,
        tamanho_pagina: int = 20,
    ) -> tuple[list[Equipamento], int]:
        ordem = self._ordenacao(ordenar_por)
        filtrado = self._aplicar_filtros(select(Equipamento), filtros)
        total = self.db.scalar(select(func.count()).select_from(filtrado.subquery())) or 0

        stmt = (
            self._aplicar_filtros(self._base_query(), filtros)
            .order_by(*ordem)
            .offset((pagina - 1) * tamanho_pagina)
            .limit(tamanho_pagina)
        )
        return list(self.db.scalars(stmt).all()), total
