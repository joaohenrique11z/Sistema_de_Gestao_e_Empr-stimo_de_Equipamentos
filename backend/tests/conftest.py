"""Fixtures partilhadas.

As variáveis de ambiente são definidas *antes* de importar a aplicação, para que
os testes usem um SQLite em memória isolado e um segredo JWT próprio.
"""

import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "chave-secreta-exclusiva-para-testes-automatizados"
os.environ["APP_ENV"] = "test"
os.environ["RATE_LIMIT_ENABLED"] = "true"
os.environ["RATE_LIMIT_STORAGE_URI"] = "memory://"
os.environ.pop("FIRST_ADMIN_EMAIL", None)
os.environ.pop("FIRST_ADMIN_PASSWORD", None)

from collections.abc import Callable, Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.rate_limit import limiter  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Usuario  # noqa: E402
from tests.factories import SENHA_PADRAO  # noqa: E402


@pytest.fixture(autouse=True)
def _banco_limpo() -> Iterator[None]:
    """Cria um esquema novo e reinicia os contadores de rate limit a cada teste."""
    Base.metadata.create_all(engine)
    limiter.reset()
    limiter.enabled = True
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def criar_usuario(db_session: Session) -> Callable[..., Usuario]:
    def _criar(
        email: str = "admin@exemplo.com",
        senha: str = SENHA_PADRAO,
        nome: str = "Administrador",
        ativo: bool = True,
    ) -> Usuario:
        usuario = Usuario(nome=nome, email=email, senha_hash=hash_password(senha), ativo=ativo)
        db_session.add(usuario)
        db_session.commit()
        return usuario

    return _criar


@pytest.fixture
def usuario(criar_usuario: Callable[..., Usuario]) -> Usuario:
    return criar_usuario()


@pytest.fixture
def tokens(client: TestClient, usuario: Usuario) -> dict:
    resposta = client.post("/auth/login", json={"email": usuario.email, "senha": SENHA_PADRAO})
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


@pytest.fixture
def auth_headers(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
def api(client: TestClient, auth_headers: dict[str, str]) -> TestClient:
    """Cliente já autenticado."""
    client.headers.update(auth_headers)
    return client

