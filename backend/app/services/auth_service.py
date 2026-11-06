from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import security
from app.core.exceptions import AccountLockedError, AuthenticationError
from app.database import transaction
from app.models import Usuario
from app.models.types import utcnow
from app.repositories import TokenRepository, UsuarioRepository
from app.schemas.auth import TokenResponse

logger = structlog.get_logger()

CREDENCIAIS_INVALIDAS = "E-mail ou senha inválidos."


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.usuarios = UsuarioRepository(db)
        self.tokens = TokenRepository(db)
        self.settings = get_settings()

    # ------------------------------------------------------------------ #
    def _emitir_tokens(self, usuario: Usuario) -> tuple[TokenResponse, str]:
        access = security.create_access_token(usuario.id)
        refresh = security.create_refresh_token(usuario.id)
        self.tokens.add_refresh(refresh.jti, usuario.id, refresh.expira_em)
        resposta = TokenResponse(
            access_token=access.token,
            refresh_token=refresh.token,
            expires_in=self.settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_expires_in=self.settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        )
        return resposta, refresh.jti

    def _registrar_falha(self, usuario: Usuario, agora: datetime) -> None:
        with transaction(self.db):
            usuario.tentativas_falhas = (usuario.tentativas_falhas or 0) + 1
            if usuario.tentativas_falhas >= self.settings.LOGIN_MAX_TENTATIVAS:
                usuario.bloqueado_ate = agora + timedelta(minutes=self.settings.LOGIN_BLOQUEIO_MINUTOS)
                usuario.tentativas_falhas = 0
                logger.warning("auth_conta_bloqueada", usuario_id=usuario.id)

    # ------------------------------------------------------------------ #
    def login(self, email: str, senha: str) -> TokenResponse:
        agora = utcnow()
        usuario = self.usuarios.get_by_email(email)

        if usuario is None:
            security.simulate_password_check(senha)
            logger.info("auth_login_falhou", motivo="usuario_inexistente")
            raise AuthenticationError(CREDENCIAIS_INVALIDAS)

        if usuario.bloqueado_ate and usuario.bloqueado_ate > agora:
            raise AccountLockedError(
                "Conta temporariamente bloqueada por excesso de tentativas. Tente novamente mais tarde.",
                bloqueado_ate=usuario.bloqueado_ate.isoformat(),
            )

        valida, novo_hash = security.verify_and_update_password(senha, usuario.senha_hash)
        if not valida:
            self._registrar_falha(usuario, agora)
            logger.info("auth_login_falhou", motivo="senha_invalida", usuario_id=usuario.id)
            raise AuthenticationError(CREDENCIAIS_INVALIDAS)

        if not usuario.ativo:
            raise AuthenticationError("Utilizador inativo.")

        with transaction(self.db):
            usuario.tentativas_falhas = 0
            usuario.bloqueado_ate = None
            if novo_hash:
                usuario.senha_hash = novo_hash
            resposta, _ = self._emitir_tokens(usuario)

        logger.info("auth_login_sucesso", usuario_id=usuario.id)
        return resposta

    def refresh(self, refresh_token: str) -> TokenResponse:
        try:
            payload = security.decode_token(refresh_token, security.REFRESH_TOKEN)
        except security.TokenError as exc:
            raise AuthenticationError(str(exc)) from exc

        armazenado = self.tokens.get_refresh(payload["jti"])
        if armazenado is None or str(armazenado.usuario_id) != payload["sub"]:
            raise AuthenticationError("Refresh token inválido.")

        if armazenado.revogado_em is not None:
            # Reutilização de um token já rodado: possível roubo -> revoga todas as sessões.
            with transaction(self.db):
                self.tokens.revoke_all_refresh(armazenado.usuario_id)
            logger.warning("auth_refresh_reutilizado", usuario_id=armazenado.usuario_id)
            raise AuthenticationError("Refresh token revogado.")

        usuario = self.usuarios.get(armazenado.usuario_id)
        if usuario is None or not usuario.ativo:
            raise AuthenticationError("Utilizador inválido ou inativo.")

        with transaction(self.db):
            resposta, novo_jti = self._emitir_tokens(usuario)
            armazenado.revogado_em = utcnow()
            armazenado.substituido_por = novo_jti

        return resposta

    def logout(
        self,
        usuario: Usuario,
        access_payload: dict[str, Any],
        refresh_token: str | None = None,
        todas_sessoes: bool = False,
    ) -> None:
        expira_em = datetime.fromtimestamp(access_payload["exp"], tz=timezone.utc)

        with transaction(self.db):
            self.tokens.revoke_access(access_payload["jti"], expira_em)

            if todas_sessoes:
                self.tokens.revoke_all_refresh(usuario.id)
            elif refresh_token:
                try:
                    payload = security.decode_token(refresh_token, security.REFRESH_TOKEN)
                except security.TokenError:
                    payload = None
                if payload is not None:
                    armazenado = self.tokens.get_refresh(payload["jti"])
                    if (
                        armazenado is not None
                        and armazenado.usuario_id == usuario.id
                        and armazenado.revogado_em is None
                    ):
                        armazenado.revogado_em = utcnow()

        logger.info("auth_logout", usuario_id=usuario.id, todas_sessoes=todas_sessoes)

    # ------------------------------------------------------------------ #
    def criar_usuario(self, nome: str, email: str, senha: str) -> Usuario:
        with transaction(self.db):
            usuario = self.usuarios.add(
                Usuario(nome=nome, email=email.lower(), senha_hash=security.hash_password(senha))
            )
        return usuario

