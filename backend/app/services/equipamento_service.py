from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.database import transaction
from app.models import Acessorio, Equipamento, Movimentacao, TipoMovimentacao, Usuario
from app.repositories import (
    EquipamentoRepository,
    FiltrosEquipamento,
    MovimentacaoRepository,
    ResponsavelRepository,
)
from app.schemas.common import Pagina
from app.schemas.equipamento import (
    AcessorioIn,
    EquipamentoCreate,
    EquipamentoOut,
    EquipamentoUpdate,
    TipoBuscaCodigo,
)

logger = structlog.get_logger()

CAMPOS_ACESSORIO = ("nome", "descricao", "numero_serie", "quantidade")


def _json(valor: Any) -> Any:
    """Converte valores para tipos serializáveis em JSON (para o histórico)."""
    if isinstance(valor, Enum):
        return valor.value
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    return valor


def _snapshot_acessorio(acessorio: Acessorio) -> dict[str, Any]:
    return {"acessorio_id": acessorio.id, **{c: getattr(acessorio, c) for c in CAMPOS_ACESSORIO}}


class EquipamentoService:
    """Regras de negócio de equipamentos.

    Todas as operações de escrita executam, numa única transação, a alteração do
    equipamento, os vínculos de acessórios e o registo das movimentações. Qualquer
    falha provoca rollback integral.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = EquipamentoRepository(db)
        self.movimentacoes = MovimentacaoRepository(db)
        self.responsaveis = ResponsavelRepository(db)

    # ------------------------------------------------------------------ #
    # Validações
    # ------------------------------------------------------------------ #
    def _obter_ou_404(self, equipamento_id: int) -> Equipamento:
        equipamento = self.repo.get(equipamento_id)
        if equipamento is None:
            raise NotFoundError("Equipamento não encontrado.")
        return equipamento

    def _garantir_codigos_disponiveis(self, codigos: dict[str, str], excluir_id: int | None = None) -> None:
        if not codigos:
            return
        conflitos = self.repo.find_code_conflicts(codigos, excluir_id=excluir_id)
        if conflitos:
            raise ConflictError(
                "Código já utilizado por outro equipamento.",
                conflitos=[
                    {"campo": campo, "valor": valor, "equipamento_id": eid}
                    for campo, valor, eid in conflitos
                ],
            )

    def _garantir_responsavel(self, responsavel_id: int | None) -> None:
        if responsavel_id is None:
            return
        responsavel = self.responsaveis.get(responsavel_id)
        if responsavel is None:
            raise BusinessRuleError("Responsável informado não existe.")
        if not responsavel.ativo:
            raise BusinessRuleError("Responsável informado está inativo.")

    # ------------------------------------------------------------------ #
    # Acessórios (executados dentro da transação do chamador)
    # ------------------------------------------------------------------ #
    def _vincular_acessorio(self, equipamento: Equipamento, dados: AcessorioIn, usuario_id: int | None) -> None:
        acessorio = Acessorio(**dados.model_dump(exclude={"id"}))
        equipamento.acessorios.append(acessorio)
        self.db.flush()
        self.movimentacoes.registrar(
            equipamento,
            TipoMovimentacao.VINCULO_ACESSORIO,
            f"Acessório '{acessorio.nome}' vinculado ao equipamento.",
            detalhes=_snapshot_acessorio(acessorio),
            usuario_id=usuario_id,
        )

    def _sincronizar_acessorios(
        self, equipamento: Equipamento, novos: list[AcessorioIn], usuario_id: int | None
    ) -> bool:
        ids_enviados_com_repeticao = [a.id for a in novos if a.id is not None]
        if len(ids_enviados_com_repeticao) != len(set(ids_enviados_com_repeticao)):
            raise BusinessRuleError("Identificadores de acessórios duplicados na requisição.")

        atuais = {a.id: a for a in equipamento.acessorios}
        ids_enviados = set(ids_enviados_com_repeticao)

        desconhecidos = ids_enviados - atuais.keys()
        if desconhecidos:
            raise BusinessRuleError(
                "Acessório(s) não vinculado(s) a este equipamento.",
                acessorios=sorted(desconhecidos),
            )

        houve_alteracao = False

        # Desvínculos
        for acessorio_id, acessorio in list(atuais.items()):
            if acessorio_id not in ids_enviados:
                snapshot = _snapshot_acessorio(acessorio)
                equipamento.acessorios.remove(acessorio)
                self.movimentacoes.registrar(
                    equipamento,
                    TipoMovimentacao.DESVINCULO_ACESSORIO,
                    f"Acessório '{acessorio.nome}' desvinculado do equipamento.",
                    detalhes=snapshot,
                    usuario_id=usuario_id,
                )
                houve_alteracao = True

        # Atualizações e novos vínculos
        for dados in novos:
            if dados.id is None:
                self._vincular_acessorio(equipamento, dados, usuario_id)
                houve_alteracao = True
                continue
            acessorio = atuais[dados.id]
            mudancas = {
                campo: {"de": getattr(acessorio, campo), "para": getattr(dados, campo)}
                for campo in CAMPOS_ACESSORIO
                if getattr(acessorio, campo) != getattr(dados, campo)
            }
            if mudancas:
                for campo, valores in mudancas.items():
                    setattr(acessorio, campo, valores["para"])
                self.movimentacoes.registrar(
                    equipamento,
                    TipoMovimentacao.VINCULO_ACESSORIO,
                    f"Dados do acessório '{acessorio.nome}' atualizados.",
                    detalhes={"acessorio_id": acessorio.id, "alteracoes": mudancas},
                    usuario_id=usuario_id,
                )
                houve_alteracao = True

        self.db.flush()
        return houve_alteracao

    # ------------------------------------------------------------------ #
    # Escrita
    # ------------------------------------------------------------------ #
    def criar(self, dados: EquipamentoCreate, usuario: Usuario | None = None) -> Equipamento:
        if dados.codigo_patrimonio.strip().upper() == dados.codigo_interno.strip().upper():
            raise BusinessRuleError("O código de patrimônio e o código interno não podem ser iguais.")

        self._garantir_codigos_disponiveis(
            {"codigo_patrimonio": dados.codigo_patrimonio, "codigo_interno": dados.codigo_interno}
        )
        self._garantir_responsavel(dados.responsavel_id)
        usuario_id = usuario.id if usuario else None

        campos = dados.model_dump(exclude={"acessorios"})
        try:
            with transaction(self.db):
                equipamento = self.repo.add(Equipamento(**campos))
                self.movimentacoes.registrar(
                    equipamento,
                    TipoMovimentacao.CADASTRO,
                    "Equipamento cadastrado.",
                    detalhes={k: _json(v) for k, v in campos.items()},
                    usuario_id=usuario_id,
                )
                for acessorio in dados.acessorios:
                    self._vincular_acessorio(equipamento, acessorio, usuario_id)
        except IntegrityError as exc:
            raise ConflictError("Não foi possível cadastrar: dados conflitantes.") from exc

        logger.info("equipamento_cadastrado", equipamento_id=equipamento.id)
        return self._obter_ou_404(equipamento.id)

    def atualizar(
        self, equipamento_id: int, dados: EquipamentoUpdate, usuario: Usuario | None = None
    ) -> Equipamento:
        equipamento = self._obter_ou_404(equipamento_id)
        usuario_id = usuario.id if usuario else None
        enviados = dados.model_dump(exclude_unset=True, exclude={"acessorios"})

        alteracoes = {
            campo: {"de": _json(getattr(equipamento, campo)), "para": _json(valor)}
            for campo, valor in enviados.items()
            if getattr(equipamento, campo) != valor
        }

        patrimonio_final = enviados.get("codigo_patrimonio", equipamento.codigo_patrimonio)
        interno_final = enviados.get("codigo_interno", equipamento.codigo_interno)
        if patrimonio_final.strip().upper() == interno_final.strip().upper():
            raise BusinessRuleError("O código de patrimônio e o código interno não podem ser iguais.")

        codigos = {
            campo: enviados[campo]
            for campo in ("codigo_patrimonio", "codigo_interno")
            if campo in alteracoes
        }
        self._garantir_codigos_disponiveis(codigos, excluir_id=equipamento_id)
        if "responsavel_id" in alteracoes:
            self._garantir_responsavel(enviados["responsavel_id"])

        try:
            with transaction(self.db):
                for campo in alteracoes:
                    setattr(equipamento, campo, enviados[campo])
                if alteracoes:
                    self.db.flush()
                    self.movimentacoes.registrar(
                        equipamento,
                        TipoMovimentacao.ATUALIZACAO,
                        "Equipamento atualizado: " + ", ".join(alteracoes) + ".",
                        detalhes={"alteracoes": alteracoes},
                        usuario_id=usuario_id,
                    )
                if dados.acessorios is not None:
                    self._sincronizar_acessorios(equipamento, dados.acessorios, usuario_id)
        except IntegrityError as exc:
            raise ConflictError("Não foi possível atualizar: dados conflitantes.") from exc
        except Exception:
            # A transação já sofreu rollback; descarta o estado em memória do objeto.
            self.db.expire_all()
            raise

        logger.info("equipamento_atualizado", equipamento_id=equipamento_id, campos=list(alteracoes))
        self.db.expire_all()
        return self._obter_ou_404(equipamento_id)

    # ------------------------------------------------------------------ #
    # Leitura
    # ------------------------------------------------------------------ #
    def obter(self, equipamento_id: int) -> Equipamento:
        return self._obter_ou_404(equipamento_id)

    def obter_por_codigo(self, codigo: str, tipo: TipoBuscaCodigo = TipoBuscaCodigo.QUALQUER) -> Equipamento:
        codigo = codigo.strip().upper()
        equipamento = None
        if tipo in (TipoBuscaCodigo.QUALQUER, TipoBuscaCodigo.PATRIMONIO):
            equipamento = self.repo.get_by_codigo_patrimonio(codigo)
        if equipamento is None and tipo in (TipoBuscaCodigo.QUALQUER, TipoBuscaCodigo.INTERNO):
            equipamento = self.repo.get_by_codigo_interno(codigo)
        if equipamento is None:
            raise NotFoundError(f"Nenhum equipamento encontrado com o código '{codigo}'.")
        return equipamento

    def listar(
        self,
        filtros: FiltrosEquipamento,
        *,
        ordenar_por: str | None,
        pagina: int,
        tamanho_pagina: int,
    ) -> Pagina[EquipamentoOut]:
        if (
            filtros.data_aquisicao_inicio
            and filtros.data_aquisicao_fim
            and filtros.data_aquisicao_inicio > filtros.data_aquisicao_fim
        ):
            raise BusinessRuleError("data_aquisicao_inicio não pode ser posterior a data_aquisicao_fim.")
        if filtros.valor_min is not None and filtros.valor_max is not None and filtros.valor_min > filtros.valor_max:
            raise BusinessRuleError("valor_min não pode ser maior que valor_max.")

        items, total = self.repo.listar(
            filtros, ordenar_por=ordenar_por, pagina=pagina, tamanho_pagina=tamanho_pagina
        )
        return Pagina[EquipamentoOut].criar(
            [EquipamentoOut.model_validate(e) for e in items], total, pagina, tamanho_pagina
        )

    def listar_movimentacoes(self, equipamento_id: int) -> list[Movimentacao]:
        self._obter_ou_404(equipamento_id)
        return self.movimentacoes.list_by_equipamento(equipamento_id)

