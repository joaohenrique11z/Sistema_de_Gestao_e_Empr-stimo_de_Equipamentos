from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "altere-esta-chave-secreta-em-producao"


class Settings(BaseSettings):
    APP_NAME: str = "Sistema de Gestão e Empréstimo de Equipamentos"
    APP_ENV: str = "development"

    # Banco de dados (SQLAlchemy). Ex.: postgresql+psycopg://user:pass@host:5432/db
    DATABASE_URL: str = "sqlite:///./equipamentos.db"
    DATABASE_ECHO: bool = False

    # Autenticação (JWT)
    JWT_SECRET_KEY: str = DEFAULT_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "equipamentos-api"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Proteção contra força bruta (bloqueio temporário da conta)
    LOGIN_MAX_TENTATIVAS: int = 5
    LOGIN_BLOQUEIO_MINUTOS: int = 15

    # Rate limiting (slowapi). Para múltiplas instâncias use redis://host:6379
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_STORAGE_URI: str = "memory://"
    RATE_LIMIT_DEFAULT: str = "120/minute"
    RATE_LIMIT_LOGIN: str = "5/minute"
    RATE_LIMIT_REFRESH: str = "10/minute"

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # Usuário administrador criado automaticamente na inicialização (opcional)
    FIRST_ADMIN_NOME: str = "Administrador"
    FIRST_ADMIN_EMAIL: str | None = None
    FIRST_ADMIN_PASSWORD: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def _validar_segredo_em_producao(self) -> "Settings":
        if self.APP_ENV.lower() in {"production", "producao", "staging"} and (
            self.JWT_SECRET_KEY == DEFAULT_JWT_SECRET or len(self.JWT_SECRET_KEY) < 32
        ):
            raise ValueError(
                "JWT_SECRET_KEY deve ser definida com pelo menos 32 caracteres "
                "em ambientes de staging/produção."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
