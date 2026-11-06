"""Rate limiting com slowapi (backend em memória por padrão, Redis em produção)."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    storage_uri=settings.RATE_LIMIT_STORAGE_URI,
    enabled=settings.RATE_LIMIT_ENABLED,
)

