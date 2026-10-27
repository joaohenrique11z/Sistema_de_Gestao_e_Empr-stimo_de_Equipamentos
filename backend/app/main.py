from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.logging_config import RequestLoggingMiddleware, configure_logging

configure_logging()

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description="API do Sistema de Gestão e Empréstimo de Equipamentos",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestLoggingMiddleware)


@app.get("/health", tags=["Health"])
async def health_check(config: Settings = Depends(get_settings)) -> dict:
    """Retorna o status de saúde da aplicação e o ambiente atual."""
    return {
        "status": "ok",
        "environment": config.APP_ENV,
        "app_name": config.APP_NAME,
    }

