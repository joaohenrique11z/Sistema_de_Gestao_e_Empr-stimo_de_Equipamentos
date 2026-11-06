from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str | None = None
    todas_sessoes: bool = Field(
        default=False, description="Revoga todos os refresh tokens ativos do utilizador."
    )


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Validade do access token em segundos.")
    refresh_expires_in: int = Field(description="Validade do refresh token em segundos.")


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: str
    ativo: bool
    criado_em: datetime

