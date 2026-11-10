from datetime import datetime, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Equipamento, Movimentacao, Responsavel, StatusEquipamento, TipoMovimentacao
from app.models.types import utcnow
from app.schemas.dashboard import (
    DashboardContadores,
    DashboardOut,
    PendenciaEmprestimoOut,
    UltimaMovimentacaoOut,
)

logger = structlog.get_logger()


class DashboardService:
    """Painel de Métricas e Pendências do Sistema."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def obter_dados(self) -> DashboardOut:
        agora = utcnow()

        # 1. Contadores gerais
        total_equipamentos = self.db.scalar(select(func.count(Equipamento.id))) or 0
        disponiveis = (
            self.db.scalar(
                select(func.count(Equipamento.id)).where(
                    Equipamento.status == StatusEquipamento.DISPONIVEL
                )
            )
            or 0
        )
        emprestados = (
            self.db.scalar(
                select(func.count(Equipamento.id)).where(
                    Equipamento.status == StatusEquipamento.EMPRESTADO
                )
            )
            or 0
        )
        em_manutencao = (
            self.db.scalar(
                select(func.count(Equipamento.id)).where(
                    Equipamento.status == StatusEquipamento.MANUTENCAO
                )
            )
            or 0
        )
        baixados = (
            self.db.scalar(
                select(func.count(Equipamento.id)).where(
                    Equipamento.status == StatusEquipamento.BAIXADO
                )
            )
            or 0
        )
        responsaveis_ativos = (
            self.db.scalar(select(func.count(Responsavel.id)).where(Responsavel.ativo.is_(True))) or 0
        )

        contadores = DashboardContadores(
            total_equipamentos=total_equipamentos,
            disponiveis=disponiveis,
            emprestados=emprestados,
            em_manutencao=em_manutencao,
            baixados=baixados,
            total_responsaveis_ativos=responsaveis_ativos,
        )

        # 2. Pendências (Equipamentos atualmente emprestados)
        pendencias_stmt = (
            select(Equipamento)
            .where(Equipamento.status == StatusEquipamento.EMPRESTADO)
            .options(
                selectinload(Equipamento.responsavel),
                selectinload(Equipamento.movimentacoes),
            )
            .order_by(Equipamento.atualizado_em.asc())
        )
        equipamentos_pendentes = self.db.scalars(pendencias_stmt).all()

        pendencias: list[PendenciaEmprestimoOut] = []
        for eq in equipamentos_pendentes:
            data_emp = eq.atualizado_em
            for m in reversed(eq.movimentacoes):
                if m.tipo == TipoMovimentacao.EMPRESTIMO:
                    data_emp = m.criado_em
                    break

            # Garante que data_emp seja timezone-aware para subtração precisa
            if data_emp.tzinfo is None:
                data_emp = data_emp.replace(tzinfo=timezone.utc)

            dias = max(0, (agora - data_emp).days)

            pendencias.append(
                PendenciaEmprestimoOut(
                    equipamento_id=eq.id,
                    codigo_patrimonio=eq.codigo_patrimonio,
                    codigo_interno=eq.codigo_interno,
                    nome=eq.nome,
                    responsavel_id=eq.responsavel.id if eq.responsavel else 0,
                    responsavel_nome=eq.responsavel.nome if eq.responsavel else "Sem responsável",
                    data_emprestimo=data_emp,
                    dias_emprestado=dias,
                )
            )

        # 3. Últimas 10 movimentações registradas
        movs_stmt = (
            select(Movimentacao)
            .options(selectinload(Movimentacao.equipamento))
            .order_by(Movimentacao.criado_em.desc(), Movimentacao.id.desc())
            .limit(10)
        )
        movs = self.db.scalars(movs_stmt).all()

        ultimas_movimentacoes: list[UltimaMovimentacaoOut] = [
            UltimaMovimentacaoOut(
                id=m.id,
                equipamento_id=m.equipamento_id,
                equipamento_nome=m.equipamento.nome if m.equipamento else f"ID {m.equipamento_id}",
                tipo=m.tipo.value if hasattr(m.tipo, "value") else str(m.tipo),
                descricao=m.descricao,
                criado_em=m.criado_em,
                usuario_id=m.usuario_id,
            )
            for m in movs
        ]

        return DashboardOut(
            contadores=contadores,
            pendencias=pendencias,
            ultimas_movimentacoes=ultimas_movimentacoes,
        )
