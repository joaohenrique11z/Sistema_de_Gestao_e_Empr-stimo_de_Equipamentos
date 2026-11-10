"""Middleware de autenticação: valida o access token JWT em todas as rotas privadas."""

from collections.abc import Callable, Iterable

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.security import ACCESS_TOKEN, TokenError, decode_token
from app.models import TokenRevogado

logger = structlog.get_logger()

DEFAULT_PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/docs",
        "/docs/oauth2-redirect",
        "/redoc",
        "/openapi.json",
        "/auth/login",
        "/auth/refresh",
    }
)


def _default_session_factory() -> Session:
    # Import tardio para respeitar a configuração do banco feita em tempo de execução.
    from app.database import SessionLocal

    return SessionLocal()


class AuthMiddleware(BaseHTTPMiddleware):
    """Rejeita com 401 qualquer pedido a rota privada sem um access token válido.

    Em caso de sucesso, disponibiliza ``request.state.token_payload`` e
    ``request.state.user_id`` para as dependências e rotas.
    """

    def __init__(
        self,
        app: ASGIApp,
        public_paths: Iterable[str] | None = None,
        session_factory: Callable[[], Session] | None = None,
    ) -> None:
        super().__init__(app)
        self.public_paths = frozenset(public_paths or DEFAULT_PUBLIC_PATHS)
        self.session_factory = session_factory or _default_session_factory

    def _is_public(self, request: Request) -> bool:
        path = request.url.path.rstrip("/") or "/"
        return request.method == "OPTIONS" or path in self.public_paths

    def _is_revoked(self, jti: str) -> bool:
        db = self.session_factory()
        try:
            return db.scalar(select(TokenRevogado.jti).where(TokenRevogado.jti == jti)) is not None
        finally:
            db.close()

    @staticmethod
    def _unauthorized(mensagem: str) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"detail": mensagem, "codigo": "nao_autenticado"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if self._is_public(request):
            return await call_next(request)

        scheme, _, token = request.headers.get("Authorization", "").partition(" ")
        token = token.strip()
        if scheme.lower() != "bearer" or not token:
            return self._unauthorized("Credenciais de autenticação não fornecidas.")

        try:
            payload = decode_token(token, ACCESS_TOKEN)
        except TokenError as exc:
            logger.info("auth_token_rejeitado", path=request.url.path, motivo=str(exc))
            return self._unauthorized(str(exc))

        if await run_in_threadpool(self._is_revoked, payload["jti"]):
            return self._unauthorized("Token revogado.")

        request.state.token_payload = payload
        try:
            request.state.user_id = int(payload["sub"])
        except (ValueError, TypeError, KeyError):
            return self._unauthorized("Token com identificador inválido.")
        structlog.contextvars.bind_contextvars(user_id=request.state.user_id)

        return await call_next(request)

