from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.dependencies import get_current_user, get_token_payload
from app.core.rate_limit import limiter
from app.database import get_db
from app.models import Usuario
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, TokenResponse, UsuarioOut
from app.schemas.common import Mensagem
from app.services import AuthService

settings = get_settings()

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post("/login", response_model=TokenResponse, summary="Autentica e emite access/refresh tokens")
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    return AuthService(db).login(payload.email, payload.senha)


@router.post("/refresh", response_model=TokenResponse, summary="Renova os tokens (rotação do refresh token)")
@limiter.limit(settings.RATE_LIMIT_REFRESH)
def refresh(request: Request, payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    return AuthService(db).refresh(payload.refresh_token)


@router.post("/logout", response_model=Mensagem, summary="Revoga o access token e o refresh token")
def logout(
    payload: LogoutRequest | None = None,
    usuario: Usuario = Depends(get_current_user),
    token_payload: dict[str, Any] = Depends(get_token_payload),
    db: Session = Depends(get_db),
) -> Mensagem:
    payload = payload or LogoutRequest()
    AuthService(db).logout(
        usuario,
        token_payload,
        refresh_token=payload.refresh_token,
        todas_sessoes=payload.todas_sessoes,
    )
    return Mensagem(detail="Logout realizado com sucesso.")


@router.get("/me", response_model=UsuarioOut, summary="Dados do utilizador autenticado")
def me(usuario: Usuario = Depends(get_current_user)) -> Usuario:
    return usuario

