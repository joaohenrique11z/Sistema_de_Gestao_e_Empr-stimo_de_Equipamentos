from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.database import transaction
from app.models import Equipamento, Movimentacao, Responsavel, StatusEquipamento, TipoMovimentacao, Usuario
from app.models.types import utcnow
from app.repositories import EquipamentoRepository, MovimentacaoRepository, ResponsavelRepository
from app.schemas.emprestimo import (
    DevolucaoRequest,
    DevolucaoResponse,
    EmprestimoAbertoOut,
    EmprestimoCreate,
    EmprestimoResponse,
    ItemEmprestadoOut,
)

logger = structlog.get_logger()


class EmprestimoService:
    """Regras de negócio de Empréstimos e Devoluções de Equipamentos."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.equipamentos = EquipamentoRepository(db)
        self.movimentacoes = MovimentacaoRepository(db)
        self.responsaveis = ResponsavelRepository(db)

    def realizar_emprestimo(
        self, dados: EmprestimoCreate, usuario: Usuario | None = None
    ) -> EmprestimoResponse:
        responsavel = self.responsaveis.get(dados.responsavel_id)
        if responsavel is None:
            raise BusinessRuleError("Responsável informado não existe.")
        if not responsavel.ativo:
            raise BusinessRuleError("Responsável informado está inativo e não pode retirar equipamentos.")

        usuario_id = usuario.id if usuario else None
        agora = utcnow()

        # Validação de concorrência e disponibilidade prévia
        itens_para_emprestar: list[Equipamento] = []
        for eq_id in dados.equipamento_ids:
            equipamento = self.equipamentos.get(eq_id)
            if equipamento is None:
                raise NotFoundError(f"Equipamento com ID {eq_id} não encontrado.")
            if equipamento.status != StatusEquipamento.DISPONIVEL:
                raise BusinessRuleError(
                    f"Equipamento '{equipamento.codigo_patrimonio}' não está disponível "
                    f"(status atual: {equipamento.status.value}).",
                    equipamento_id=equipamento.id,
                    status_atual=equipamento.status.value,
                )
            itens_para_emprestar.append(equipamento)

        itens_out: list[ItemEmprestadoOut] = []

        with transaction(self.db):
            for eq in itens_para_emprestar:
                # Regra dos acessórios vinculados (Task #402): acompanham o equipamento
                nomes_acessorios = [
                    f"{ac.nome} (qtd: {ac.quantidade})" for ac in eq.acessorios
                ]

                eq.status = StatusEquipamento.EMPRESTADO
                eq.responsavel_id = responsavel.id

                detalhes_mov = {
                    "responsavel_id": responsavel.id,
                    "responsavel_nome": responsavel.nome,
                    "responsavel_cpf": responsavel.cpf,
                    "previsao_devolucao": (
                        dados.previsao_devolucao.isoformat() if dados.previsao_devolucao else None
                    ),
                    "acessorios_vinculados": nomes_acessorios,
                    "observacoes": dados.observacoes,
                }

                self.movimentacoes.registrar(
                    eq,
                    TipoMovimentacao.EMPRESTIMO,
                    f"Equipamento emprestado para {responsavel.nome}.",
                    detalhes=detalhes_mov,
                    usuario_id=usuario_id,
                )

                itens_out.append(
                    ItemEmprestadoOut(
                        equipamento_id=eq.id,
                        codigo_patrimonio=eq.codigo_patrimonio,
                        codigo_interno=eq.codigo_interno,
                        nome=eq.nome,
                        acessorios=nomes_acessorios,
                    )
                )

        logger.info(
            "emprestimo_realizado",
            responsavel_id=responsavel.id,
            qtd_equipamentos=len(itens_out),
            usuario_id=usuario_id,
        )

        return EmprestimoResponse(
            responsavel_id=responsavel.id,
            responsavel_nome=responsavel.nome,
            data_emprestimo=agora,
            previsao_devolucao=dados.previsao_devolucao,
            observacoes=dados.observacoes,
            itens=itens_out,
        )

    def realizar_devolucao(
        self, dados: DevolucaoRequest, usuario: Usuario | None = None
    ) -> DevolucaoResponse:
        equipamento = self.equipamentos.get(dados.equipamento_id)
        if equipamento is None:
            raise NotFoundError(f"Equipamento com ID {dados.equipamento_id} não encontrado.")

        if equipamento.status != StatusEquipamento.EMPRESTADO:
            raise BusinessRuleError(
                f"Equipamento '{equipamento.codigo_patrimonio}' não está emprestado "
                f"(status atual: {equipamento.status.value}).",
                equipamento_id=equipamento.id,
                status_atual=equipamento.status.value,
            )

        usuario_id = usuario.id if usuario else None
        agora = utcnow()
        responsavel_anterior = equipamento.responsavel

        # Regra do status de destino (Task #406): se houver avaria/dano ou se for MANUTENCAO, vai para MANUTENCAO
        status_novo = (
            StatusEquipamento.MANUTENCAO
            if (dados.status_destino == "MANUTENCAO" or dados.avarias)
            else StatusEquipamento(dados.status_destino)
        )

        with transaction(self.db):
            equipamento.status = status_novo
            equipamento.responsavel_id = None

            detalhes_devolucao: dict[str, Any] = {
                "responsavel_anterior_id": responsavel_anterior.id if responsavel_anterior else None,
                "responsavel_anterior_nome": responsavel_anterior.nome if responsavel_anterior else None,
                "status_destino": status_novo.value,
                "avarias": dados.avarias,
                "observacoes": dados.observacoes,
            }

            self.movimentacoes.registrar(
                equipamento,
                TipoMovimentacao.DEVOLUCAO,
                f"Equipamento devolvido com destino {status_novo.value}.",
                detalhes=detalhes_devolucao,
                usuario_id=usuario_id,
            )

        logger.info(
            "devolucao_realizada",
            equipamento_id=equipamento.id,
            status_novo=status_novo.value,
            usuario_id=usuario_id,
        )

        return DevolucaoResponse(
            equipamento_id=equipamento.id,
            codigo_patrimonio=equipamento.codigo_patrimonio,
            status_novo=status_novo.value,
            data_devolucao=agora,
            avarias=dados.avarias,
            observacoes=dados.observacoes,
        )

    def listar_abertos(
        self,
        *,
        responsavel_id: int | None = None,
        equipamento_id: int | None = None,
    ) -> list[EmprestimoAbertoOut]:
        """Consulta empréstimos em aberto filtrando por responsável ou equipamento."""
        stmt = (
            select(Equipamento)
            .where(Equipamento.status == StatusEquipamento.EMPRESTADO)
            .options(
                selectinload(Equipamento.responsavel),
                selectinload(Equipamento.acessorios),
                selectinload(Equipamento.movimentacoes),
            )
        )

        if responsavel_id is not None:
            stmt = stmt.where(Equipamento.responsavel_id == responsavel_id)
        if equipamento_id is not None:
            stmt = stmt.where(Equipamento.id == equipamento_id)

        equipamentos = self.db.scalars(stmt).all()
        resultado: list[EmprestimoAbertoOut] = []

        for eq in equipamentos:
            if not eq.responsavel:
                continue

            # Obtém a data do empréstimo a partir da última movimentação do tipo EMPRESTIMO
            data_emp = eq.atualizado_em
            for m in reversed(eq.movimentacoes):
                if m.tipo == TipoMovimentacao.EMPRESTIMO:
                    data_emp = m.criado_em
                    break

            resultado.append(
                EmprestimoAbertoOut(
                    equipamento_id=eq.id,
                    codigo_patrimonio=eq.codigo_patrimonio,
                    codigo_interno=eq.codigo_interno,
                    nome=eq.nome,
                    categoria=eq.categoria,
                    localizacao=eq.localizacao,
                    responsavel_id=eq.responsavel.id,
                    responsavel_nome=eq.responsavel.nome,
                    responsavel_matricula=eq.responsavel.matricula,
                    responsavel_email=eq.responsavel.email,
                    data_emprestimo=data_emp,
                    acessorios=[f"{a.nome} (qtd: {a.quantidade})" for a in eq.acessorios],
                )
            )

        return resultado
