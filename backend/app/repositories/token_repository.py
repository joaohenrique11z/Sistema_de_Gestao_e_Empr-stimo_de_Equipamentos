from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import RefreshToken, TokenRevogado
from app.models.types import utcnow


class TokenRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # Refresh tokens -------------------------------------------------------- #
    def add_refresh(self, jti: str, usuario_id: int, expira_em: datetime) -> RefreshToken:
        token = RefreshToken(jti=jti, usuario_id=usuario_id, expira_em=expira_em)
        self.db.add(token)
        return token

    def get_refresh(self, jti: str) -> RefreshToken | None:
        return self.db.scalar(select(RefreshToken).where(RefreshToken.jti == jti))

    def revoke_all_refresh(self, usuario_id: int) -> None:
        self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.usuario_id == usuario_id, RefreshToken.revogado_em.is_(None))
            .values(revogado_em=utcnow())
        )

    # Access tokens --------------------------------------------------------- #
    def revoke_access(self, jti: str, expira_em: datetime) -> None:
        if self.db.get(TokenRevogado, jti) is None:
            self.db.add(TokenRevogado(jti=jti, expira_em=expira_em))

    def is_access_revoked(self, jti: str) -> bool:
        return self.db.get(TokenRevogado, jti) is not None

