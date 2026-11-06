"""Validadores e normalizadores reutilizáveis."""

import re

_NAO_DIGITOS = re.compile(r"\D")


def somente_digitos(valor: str) -> str:
    return _NAO_DIGITOS.sub("", valor or "")


def cpf_valido(cpf: str) -> bool:
    digitos = somente_digitos(cpf)
    if len(digitos) != 11 or digitos == digitos[0] * 11:
        return False

    for tamanho in (9, 10):
        soma = sum(int(d) * peso for d, peso in zip(digitos[:tamanho], range(tamanho + 1, 1, -1)))
        resto = (soma * 10) % 11
        if resto == 10:
            resto = 0
        if resto != int(digitos[tamanho]):
            return False
    return True


def normalizar_cpf(cpf: str) -> str:
    """Remove a máscara e valida os dígitos verificadores. Lança ValueError se inválido."""
    digitos = somente_digitos(cpf)
    if not cpf_valido(digitos):
        raise ValueError("CPF inválido.")
    return digitos

