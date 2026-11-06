from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Equipamento, Movimentacao, TipoMovimentacao


class MovimentacaoRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def registrar(
        self,
        equipamento: Equipamento,
        tipo: TipoMovimentacao,
        descricao: str,
        *,
        detalhes: dict[str, Any] | None = None,
        usuario_id: int | None = None,
    ) -> Movimentacao:
        movimentacao = Movimentacao(
            equipamento_id=equipamento.id,
            tipo=tipo,
            descricao=descricao[:255],
            detalhes=detalhes,
            usuario_id=usuario_id,
        )
        self.db.add(movimentacao)
        self.db.flush()
        return movimentacao

    def list_by_equipamento(self, equipamento_id: int) -> list[Movimentacao]:
        stmt = (
            select(Movimentacao)
            .where(Movimentacao.equipamento_id == equipamento_id)
            .order_by(Movimentacao.id)
        )
        return list(self.db.scalars(stmt).all())

