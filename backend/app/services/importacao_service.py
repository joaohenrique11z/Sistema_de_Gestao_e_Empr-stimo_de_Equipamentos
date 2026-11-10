import csv
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.database import transaction
from app.models import Equipamento, Movimentacao, StatusEquipamento, TipoMovimentacao, Usuario
from app.repositories import EquipamentoRepository, MovimentacaoRepository
from app.schemas.importacao import ErroImportacao, ResultadoImportacao

logger = structlog.get_logger()


class ImportacaoService:
    """Serviço de importação de planilhas de equipamentos com suporte a CSV e Upsert."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = EquipamentoRepository(db)
        self.movimentacoes = MovimentacaoRepository(db)

    def importar_csv(
        self, conteudo_bytes: bytes, usuario: Usuario | None = None
    ) -> ResultadoImportacao:
        """Processa um arquivo CSV codificado em UTF-8 ou Latin-1."""
        usuario_id = usuario.id if usuario else None

        # Detecta codificação
        try:
            texto = conteudo_bytes.decode("utf-8")
        except UnicodeDecodeError:
            texto = conteudo_bytes.decode("latin-1")

        # Detecta delimitador (, ou ; ou \t)
        linhas_texto = [linha for linha in texto.splitlines() if linha.strip()]
        if not linhas_texto:
            return ResultadoImportacao(
                total_linhas=0,
                sucessos=0,
                inseridos=0,
                atualizados=0,
                falhas=0,
                erros=[ErroImportacao(linha=0, erro="O arquivo CSV está vazio.")],
            )

        primeira_linha = linhas_texto[0]
        delimitador = ";" if ";" in primeira_linha else ("," if "," in primeira_linha else "\t")

        leitor = csv.DictReader(linhas_texto, delimiter=delimitador)
        # Normaliza nomes de colunas do cabeçalho
        if leitor.fieldnames is None:
            return ResultadoImportacao(
                total_linhas=0,
                sucessos=0,
                inseridos=0,
                atualizados=0,
                falhas=0,
                erros=[ErroImportacao(linha=1, erro="Não foi possível identificar o cabeçalho do arquivo.")],
            )

        total_linhas = 0
        inseridos = 0
        atualizados = 0
        falhas = 0
        erros: list[ErroImportacao] = []

        for numero_linha, row in enumerate(leitor, start=2):
            total_linhas += 1
            # Normaliza chaves
            row_clean = {
                k.strip().lower().replace(" ", "_").replace("ç", "c").replace("ã", "a"): (v.strip() if v else "")
                for k, v in row.items()
                if k
            }

            codigo_patrimonio = (
                row_clean.get("codigo_patrimonio")
                or row_clean.get("patrimonio")
                or row_clean.get("tombo")
                or ""
            ).strip().upper()

            codigo_interno = (
                row_clean.get("codigo_interno")
                or row_clean.get("interno")
                or row_clean.get("codigo")
                or ""
            ).strip().upper()

            nome = (row_clean.get("nome") or row_clean.get("descricao_item") or "").strip()

            if not codigo_patrimonio or not codigo_interno or not nome:
                falhas += 1
                faltantes = []
                if not codigo_patrimonio:
                    faltantes.append("codigo_patrimonio")
                if not codigo_interno:
                    faltantes.append("codigo_interno")
                if not nome:
                    faltantes.append("nome")
                erros.append(
                    ErroImportacao(
                        linha=numero_linha,
                        campo=", ".join(faltantes),
                        erro=f"Campos obrigatórios não informados: {', '.join(faltantes)}.",
                    )
                )
                continue

            if codigo_patrimonio == codigo_interno:
                falhas += 1
                erros.append(
                    ErroImportacao(
                        linha=numero_linha,
                        campo="codigo_patrimonio/codigo_interno",
                        erro="O código de patrimônio e o código interno não podem ser iguais.",
                    )
                )
                continue

            # Campos opcionais
            categoria = row_clean.get("categoria") or None
            marca = row_clean.get("marca") or None
            modelo = row_clean.get("modelo") or None
            numero_serie = row_clean.get("numero_serie") or row_clean.get("serie") or None
            descricao = row_clean.get("descricao") or None
            localizacao = row_clean.get("localizacao") or None

            valor_aquisicao: Decimal | None = None
            valor_bruto = row_clean.get("valor_aquisicao") or row_clean.get("valor")
            if valor_bruto:
                try:
                    valor_limpo = valor_bruto.replace("R$", "").replace(".", "").replace(",", ".").strip()
                    valor_aquisicao = Decimal(valor_limpo)
                except (InvalidOperation, ValueError):
                    pass

            data_aquisicao: date | None = None
            data_bruta = row_clean.get("data_aquisicao") or row_clean.get("data")
            if data_bruta:
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                    try:
                        data_aquisicao = datetime.strptime(data_bruta, fmt).date()
                        break
                    except ValueError:
                        pass

            try:
                with transaction(self.db):
                    # Procura se já existe por código de patrimônio ou código interno
                    equipamento = self.repo.get_by_codigo_patrimonio(
                        codigo_patrimonio
                    ) or self.repo.get_by_codigo_interno(codigo_interno)

                    if equipamento:
                        # Atualiza dados existentes
                        equipamento.codigo_patrimonio = codigo_patrimonio
                        equipamento.codigo_interno = codigo_interno
                        equipamento.nome = nome
                        if categoria is not None:
                            equipamento.categoria = categoria
                        if marca is not None:
                            equipamento.marca = marca
                        if modelo is not None:
                            equipamento.modelo = modelo
                        if numero_serie is not None:
                            equipamento.numero_serie = numero_serie
                        if descricao is not None:
                            equipamento.descricao = descricao
                        if localizacao is not None:
                            equipamento.localizacao = localizacao
                        if valor_aquisicao is not None:
                            equipamento.valor_aquisicao = valor_aquisicao
                        if data_aquisicao is not None:
                            equipamento.data_aquisicao = data_aquisicao

                        self.movimentacoes.registrar(
                            equipamento,
                            TipoMovimentacao.ATUALIZACAO,
                            "Equipamento atualizado via importação de planilha.",
                            detalhes={"origem": "IMPORTACAO_CSV", "linha": numero_linha},
                            usuario_id=usuario_id,
                        )
                        atualizados += 1
                    else:
                        # Cria novo equipamento
                        novo = Equipamento(
                            codigo_patrimonio=codigo_patrimonio,
                            codigo_interno=codigo_interno,
                            nome=nome,
                            descricao=descricao,
                            categoria=categoria,
                            marca=marca,
                            modelo=modelo,
                            numero_serie=numero_serie,
                            status=StatusEquipamento.DISPONIVEL,
                            localizacao=localizacao,
                            data_aquisicao=data_aquisicao,
                            valor_aquisicao=valor_aquisicao,
                        )
                        self.repo.add(novo)
                        self.movimentacoes.registrar(
                            novo,
                            TipoMovimentacao.CADASTRO,
                            "Equipamento cadastrado via importação de planilha.",
                            detalhes={"origem": "IMPORTACAO_CSV", "linha": numero_linha},
                            usuario_id=usuario_id,
                        )
                        inseridos += 1
            except Exception as exc:
                falhas += 1
                erros.append(
                    ErroImportacao(
                        linha=numero_linha,
                        erro=f"Falha ao persistir registro: {str(exc)}",
                    )
                )

        logger.info(
            "importacao_concluida",
            total=total_linhas,
            inseridos=inseridos,
            atualizados=atualizados,
            falhas=falhas,
        )

        return ResultadoImportacao(
            total_linhas=total_linhas,
            sucessos=inseridos + atualizados,
            inseridos=inseridos,
            atualizados=atualizados,
            falhas=falhas,
            erros=erros,
        )
