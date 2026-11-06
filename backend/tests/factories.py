"""Geradores de dados de teste."""

import itertools
from typing import Any

SENHA_PADRAO = "Senha@Forte123"

_sequencia = itertools.count(1)


def gerar_cpf(base: int | None = None) -> str:
    """Gera um CPF válido (apenas dígitos) a partir de um número base."""
    numero = base if base is not None else next(_sequencia) * 12_345_679
    digitos = [int(d) for d in f"{numero % 1_000_000_000:09d}"]
    if len(set(digitos)) == 1:
        digitos[-1] = (digitos[-1] + 1) % 10
    for tamanho in (9, 10):
        soma = sum(d * p for d, p in zip(digitos, range(tamanho + 1, 1, -1)))
        resto = (soma * 10) % 11
        digitos.append(0 if resto == 10 else resto)
    return "".join(map(str, digitos))


def formatar_cpf(cpf: str) -> str:
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def dados_responsavel(**extra: Any) -> dict[str, Any]:
    n = next(_sequencia)
    dados = {
        "nome": f"Responsável {n}",
        "cpf": gerar_cpf(),
        "email": f"responsavel{n}@exemplo.com",
        "matricula": f"MAT{n:05d}",
        "telefone": "(11) 99999-0000",
        "departamento": "TI",
    }
    dados.update(extra)
    return dados


def dados_equipamento(**extra: Any) -> dict[str, Any]:
    n = next(_sequencia)
    dados = {
        "codigo_patrimonio": f"PAT-{n:05d}",
        "codigo_interno": f"INT-{n:05d}",
        "nome": f"Notebook {n}",
        "categoria": "Informática",
        "marca": "Dell",
        "modelo": "Latitude 5440",
        "status": "DISPONIVEL",
        "localizacao": "Bloco A - Sala 101",
        "data_aquisicao": "2024-03-15",
        "valor_aquisicao": "4500.00",
    }
    dados.update(extra)
    return dados

