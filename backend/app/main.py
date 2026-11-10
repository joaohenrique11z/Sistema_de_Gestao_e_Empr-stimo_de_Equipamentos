from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware

from app.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.rate_limit import limiter
from app.logging_config import RequestLoggingMiddleware, configure_logging
from app.middlewares import AuthMiddleware
from app.routers import auth, dashboard, emprestimos, equipamentos, importacao, responsaveis
from app.seed import bootstrap_admin

configure_logging()

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    bootstrap_admin()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="API do Sistema de Gestão e Empréstimo de Equipamentos",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter
register_exception_handlers(app)

# Ordem: o último middleware adicionado é o mais externo.
# Logging -> CORS -> Rate limiting -> Autenticação -> Rotas
app.add_middleware(AuthMiddleware)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestLoggingMiddleware)

app.include_router(auth.router)
app.include_router(responsaveis.router)
app.include_router(equipamentos.router)
app.include_router(importacao.router)
app.include_router(emprestimos.router)
app.include_router(dashboard.router)


@app.get("/health", tags=["Health"])
@limiter.exempt
async def health_check(config: Settings = Depends(get_settings)) -> dict:
    """Retorna o status de saúde da aplicação e o ambiente atual."""
    return {
        "status": "ok",
        "environment": config.APP_ENV,
        "app_name": config.APP_NAME,
    }
