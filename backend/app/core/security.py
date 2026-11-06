"""Hash de senhas (Argon2id via pwdlib) e emissão/validação de tokens JWT (PyJWT)."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.config import get_settings

ACCESS_TOKEN = "access"
REFRESH_TOKEN = "refresh"

_password_hash = PasswordHash.recommended()
# Hash fictício usado para igualar o tempo de resposta quando o utilizador não existe.
_DUMMY_HASH = _password_hash.hash("senha-ficticia-para-tempo-constante")


class TokenError(Exception):
    """Token ausente, inválido, expirado ou de tipo incorreto."""


@dataclass(frozen=True)
class TokenEmitido:
    token: str
    jti: str
    expira_em: datetime


# --------------------------------------------------------------------------- #
# Senhas
# --------------------------------------------------------------------------- #
def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _password_hash.verify(password, hashed)
    except Exception:  # hash corrompido / algoritmo desconhecido
        return False


def verify_and_update_password(password: str, hashed: str) -> tuple[bool, str | None]:
    """Verifica a senha e devolve um novo hash se os parâmetros estiverem desatualizados."""
    try:
        return _password_hash.verify_and_update(password, hashed)
    except Exception:
        return False, None


def simulate_password_check(password: str) -> None:
    """Executa uma verificação fictícia para mitigar enumeração de utilizadores por tempo."""
    verify_password(password, _DUMMY_HASH)


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #
def _create_token(subject: str | int, token_type: str, expires_delta: timedelta) -> TokenEmitido:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expira_em = now + expires_delta
    jti = uuid.uuid4().hex
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "jti": jti,
        "iat": now,
        "nbf": now,
        "exp": expira_em,
        "iss": settings.JWT_ISSUER,
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return TokenEmitido(token=token, jti=jti, expira_em=expira_em)


def create_access_token(subject: str | int, expires_delta: timedelta | None = None) -> TokenEmitido:
    settings = get_settings()
    delta = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return _create_token(subject, ACCESS_TOKEN, delta)


def create_refresh_token(subject: str | int, expires_delta: timedelta | None = None) -> TokenEmitido:
    settings = get_settings()
    delta = expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return _create_token(subject, REFRESH_TOKEN, delta)


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.JWT_ISSUER,
            options={"require": ["exp", "iat", "sub", "jti", "type"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token expirado.") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Token inválido.") from exc

    if payload.get("type") != expected_type:
        raise TokenError("Tipo de token inválido.")
    return payload

