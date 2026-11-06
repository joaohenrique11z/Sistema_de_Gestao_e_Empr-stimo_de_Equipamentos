"""Dependências partilhadas pelas rotas."""

from typing import Any

from fastapi import Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError
from app.database import get_db
from app.models import Usuario

# Apenas para documentar o esquema Bearer no OpenAPI (botão "Authorize" do Swagger).
# A validação efetiva do token é feita pelo AuthMiddleware.
bearer_scheme = HTTPBearer(auto_error=False, description="Access token JWT")


def get_token_payload(request: Request) -> dict[str, Any]:
    payload = getattr(request.state, "token_payload", None)
    if payload is None:
        raise AuthenticationError("Não autenticado.")
    return payload


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    _credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> Usuario:
    payload = get_token_payload(request)
    usuario = db.get(Usuario, int(payload["sub"]))
    if usuario is None or not usuario.ativo:
        raise AuthenticationError("Utilizador inválido ou inativo.")
    return usuario

