"""Exceções de domínio e respetivos handlers HTTP."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded


class AppError(Exception):
    status_code: int = 400
    codigo: str = "erro"

    def __init__(self, mensagem: str, **extra: Any) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.extra = extra


class NotFoundError(AppError):
    status_code = 404
    codigo = "nao_encontrado"


class ConflictError(AppError):
    status_code = 409
    codigo = "conflito"


class BusinessRuleError(AppError):
    status_code = 422
    codigo = "regra_de_negocio"


class AuthenticationError(AppError):
    status_code = 401
    codigo = "nao_autenticado"


class AccountLockedError(AppError):
    status_code = 423
    codigo = "conta_bloqueada"


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.mensagem, "codigo": exc.codigo, **exc.extra},
        headers=headers,
    )


async def rate_limit_exceeded_handler(_request: Request, exc: RateLimitExceeded) -> JSONResponse:
    retry_after = 60
    limit = getattr(exc, "limit", None)
    if limit is not None and getattr(limit, "limit", None) is not None:
        retry_after = int(limit.limit.get_expiry())
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Muitas requisições. Tente novamente mais tarde.",
            "codigo": "limite_de_requisicoes",
            "limite": str(exc.detail),
        },
        headers={"Retry-After": str(retry_after)},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]

