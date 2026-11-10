from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Equipamento, Responsavel


class ResponsavelRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, responsavel_id: int) -> Responsavel | None:
        return self.db.get(Responsavel, responsavel_id)

    def add(self, responsavel: Responsavel) -> Responsavel:
        self.db.add(responsavel)
        self.db.flush()
        return responsavel

    def delete(self, responsavel: Responsavel) -> None:
        self.db.delete(responsavel)

    def search(
        self,
        *,
        termo: str | None = None,
        ativo: bool | None = None,
        departamento: str | None = None,
        pagina: int = 1,
        tamanho_pagina: int = 20,
    ) -> tuple[list[Responsavel], int]:
        stmt = select(Responsavel)

        if termo:
            termo_clean = termo.strip().lower()
            termo_escaped = termo_clean.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            like = f"%{termo_escaped}%"
            condicoes = [
                func.lower(Responsavel.nome).like(like, escape="\\"),
                func.lower(Responsavel.email).like(like, escape="\\"),
                func.lower(Responsavel.matricula).like(like, escape="\\"),
            ]
            digitos = "".join(ch for ch in termo if ch.isdigit())
            # Só busca no CPF se o termo não contiver letras (evita que buscas como 'MAT01' batam em CPFs com '01')
            if digitos and not any(ch.isalpha() for ch in termo):
                condicoes.append(Responsavel.cpf.like(f"%{digitos}%"))
            stmt = stmt.where(or_(*condicoes))
        if ativo is not None:
            stmt = stmt.where(Responsavel.ativo.is_(ativo))
        if departamento:
            stmt = stmt.where(func.lower(Responsavel.departamento) == departamento.strip().lower())

        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = self.db.scalars(
            stmt.order_by(Responsavel.nome, Responsavel.id)
            .offset((pagina - 1) * tamanho_pagina)
            .limit(tamanho_pagina)
        ).all()
        return list(items), total

    def find_duplicates(
        self,
        *,
        cpf: str | None = None,
        email: str | None = None,
        matricula: str | None = None,
        excluir_id: int | None = None,
    ) -> list[tuple[str, str, int]]:
        """Devolve uma lista de (campo, valor, id_do_responsavel_existente)."""
        candidatos = {
            "cpf": (Responsavel.cpf, cpf),
            "email": (Responsavel.email, email.lower() if email else None),
            "matricula": (Responsavel.matricula, matricula.upper() if matricula else None),
        }
        conflitos: list[tuple[str, str, int]] = []
        for campo, (coluna, valor) in candidatos.items():
            if not valor:
                continue
            stmt = select(Responsavel.id).where(func.lower(coluna) == valor.lower())
            if excluir_id is not None:
                stmt = stmt.where(Responsavel.id != excluir_id)
            existente = self.db.scalar(stmt.limit(1))
            if existente is not None:
                conflitos.append((campo, valor, existente))
        return conflitos

    def has_equipamentos(self, responsavel_id: int) -> bool:
        stmt = select(Equipamento.id).where(Equipamento.responsavel_id == responsavel_id).limit(1)
        return self.db.scalar(stmt) is not None

