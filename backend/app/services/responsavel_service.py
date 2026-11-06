from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.database import transaction
from app.models import Responsavel
from app.repositories import ResponsavelRepository
from app.schemas.common import Pagina
from app.schemas.responsavel import (
    ConflitoDuplicidade,
    ResponsavelCreate,
    ResponsavelOut,
    ResponsavelUpdate,
    VerificacaoDuplicidade,
)


class ResponsavelService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ResponsavelRepository(db)

    def _obter_ou_404(self, responsavel_id: int) -> Responsavel:
        responsavel = self.repo.get(responsavel_id)
        if responsavel is None:
            raise NotFoundError("Responsável não encontrado.")
        return responsavel

    def verificar_duplicidade(
        self,
        *,
        cpf: str | None = None,
        email: str | None = None,
        matricula: str | None = None,
        excluir_id: int | None = None,
    ) -> VerificacaoDuplicidade:
        conflitos = [
            ConflitoDuplicidade(campo=campo, valor=valor, responsavel_id=rid)
            for campo, valor, rid in self.repo.find_duplicates(
                cpf=cpf, email=email, matricula=matricula, excluir_id=excluir_id
            )
        ]
        return VerificacaoDuplicidade(duplicado=bool(conflitos), conflitos=conflitos)

    def _garantir_sem_duplicidade(self, excluir_id: int | None = None, **campos: str | None) -> None:
        verificacao = self.verificar_duplicidade(excluir_id=excluir_id, **campos)
        if verificacao.duplicado:
            nomes = ", ".join(c.campo for c in verificacao.conflitos)
            raise ConflictError(
                f"Já existe um responsável com o(s) mesmo(s) dado(s): {nomes}.",
                conflitos=[c.model_dump() for c in verificacao.conflitos],
            )

    def _commit(self, operacao) -> None:
        try:
            with transaction(self.db):
                operacao()
        except IntegrityError as exc:  # corrida entre a verificação e o INSERT/UPDATE
            raise ConflictError("Registo duplicado de responsável.") from exc

    # ------------------------------------------------------------------ #
    def criar(self, dados: ResponsavelCreate) -> Responsavel:
        self._garantir_sem_duplicidade(cpf=dados.cpf, email=dados.email, matricula=dados.matricula)
        responsavel = Responsavel(**dados.model_dump())
        self._commit(lambda: self.repo.add(responsavel))
        return responsavel

    def obter(self, responsavel_id: int) -> Responsavel:
        return self._obter_ou_404(responsavel_id)

    def listar(
        self,
        *,
        termo: str | None,
        ativo: bool | None,
        departamento: str | None,
        pagina: int,
        tamanho_pagina: int,
    ) -> Pagina[ResponsavelOut]:
        items, total = self.repo.search(
            termo=termo,
            ativo=ativo,
            departamento=departamento,
            pagina=pagina,
            tamanho_pagina=tamanho_pagina,
        )
        return Pagina[ResponsavelOut].criar(
            [ResponsavelOut.model_validate(r) for r in items], total, pagina, tamanho_pagina
        )

    def atualizar(self, responsavel_id: int, dados: ResponsavelUpdate) -> Responsavel:
        responsavel = self._obter_ou_404(responsavel_id)
        alteracoes = dados.model_dump(exclude_unset=True)
        self._garantir_sem_duplicidade(
            excluir_id=responsavel_id,
            cpf=alteracoes.get("cpf"),
            email=alteracoes.get("email"),
            matricula=alteracoes.get("matricula"),
        )

        def aplicar() -> None:
            for campo, valor in alteracoes.items():
                setattr(responsavel, campo, valor)

        self._commit(aplicar)
        return responsavel

    def remover(self, responsavel_id: int) -> None:
        responsavel = self._obter_ou_404(responsavel_id)
        if self.repo.has_equipamentos(responsavel_id):
            raise ConflictError(
                "Não é possível remover: existem equipamentos vinculados a este responsável."
            )
        self._commit(lambda: self.repo.delete(responsavel))

