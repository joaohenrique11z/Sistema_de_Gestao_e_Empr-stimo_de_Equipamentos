"""Testes da Task 368: Autenticação, Hash de Senha, Rate Limiting e Middleware."""

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import (
    ACCESS_TOKEN,
    REFRESH_TOKEN,
    TokenError,
    create_access_token,
    decode_token,
    hash_password,
    verify_and_update_password,
    verify_password,
)
from app.models import Usuario
from tests.factories import SENHA_PADRAO


def test_hash_e_verificacao_de_senha_argon2id() -> None:
    hashed = hash_password(SENHA_PADRAO)
    assert hashed != SENHA_PADRAO
    assert hashed.startswith("$argon2id$")
    assert verify_password(SENHA_PADRAO, hashed) is True
    assert verify_password("SenhaErrada123", hashed) is False
    valida, novo_hash = verify_and_update_password(SENHA_PADRAO, hashed)
    assert valida is True
    assert novo_hash is None


def test_middleware_bloqueia_rota_privada_sem_token(client: TestClient) -> None:
    res = client.get("/responsaveis")
    assert res.status_code == 401
    assert res.headers.get("WWW-Authenticate") == "Bearer"
    assert res.json()["codigo"] == "nao_autenticado"


def test_middleware_rejeita_token_invalido_ou_expirado(client: TestClient, usuario: Usuario) -> None:
    res_invalido = client.get("/auth/me", headers={"Authorization": "Bearer token.invalido.aqui"})
    assert res_invalido.status_code == 401

    expirado = create_access_token(usuario.id, expires_delta=timedelta(seconds=-10))
    res_expirado = client.get("/auth/me", headers={"Authorization": f"Bearer {expirado.token}"})
    assert res_expirado.status_code == 401
    assert "expirado" in res_expirado.json()["detail"].lower()


def test_login_refresh_e_logout_fluxo_completo(client: TestClient, usuario: Usuario) -> None:
    # 1. Login
    res_login = client.post("/auth/login", json={"email": usuario.email, "senha": SENHA_PADRAO})
    assert res_login.status_code == 200
    dados_login = res_login.json()
    assert dados_login["token_type"] == "bearer"
    access_1 = dados_login["access_token"]
    refresh_1 = dados_login["refresh_token"]

    # Valida claims dos tokens emitidos
    payload_access = decode_token(access_1, ACCESS_TOKEN)
    payload_refresh = decode_token(refresh_1, REFRESH_TOKEN)
    assert payload_access["sub"] == str(usuario.id)
    assert payload_refresh["sub"] == str(usuario.id)

    # 2. Rota privada /auth/me com access token
    res_me = client.get("/auth/me", headers={"Authorization": f"Bearer {access_1}"})
    assert res_me.status_code == 200
    assert res_me.json()["email"] == usuario.email

    # 3. Refresh rotaciona o refresh token
    res_refresh = client.post("/auth/refresh", json={"refresh_token": refresh_1})
    assert res_refresh.status_code == 200
    dados_refresh = res_refresh.json()
    access_2 = dados_refresh["access_token"]
    refresh_2 = dados_refresh["refresh_token"]
    assert refresh_2 != refresh_1

    # 4. Reutilização do refresh_1 antigo é bloqueada e revoga todas as sessões por segurança
    res_reuso = client.post("/auth/refresh", json={"refresh_token": refresh_1})
    assert res_reuso.status_code == 401
    res_refresh_2 = client.post("/auth/refresh", json={"refresh_token": refresh_2})
    assert res_refresh_2.status_code == 401

    # 5. Logout revoga o access token imediatamente no middleware
    res_logout = client.post(
        "/auth/logout",
        json={"todas_sessoes": True},
        headers={"Authorization": f"Bearer {access_2}"},
    )
    assert res_logout.status_code == 200

    res_apos_logout = client.get("/auth/me", headers={"Authorization": f"Bearer {access_2}"})
    assert res_apos_logout.status_code == 401
    assert "revogado" in res_apos_logout.json()["detail"].lower()


def test_bloqueio_de_conta_apos_tentativas_falhas(
    client: TestClient, usuario: Usuario, db_session: Session
) -> None:
    from app.core.rate_limit import limiter

    limiter.enabled = False  # Isola o teste do bloqueio de conta do rate limit de IP
    for _ in range(5):
        r = client.post("/auth/login", json={"email": usuario.email, "senha": "SenhaIncorreta"})
        assert r.status_code == 401

    # 6ª tentativa mesmo com a senha correta deve retornar 423 (Locked)
    r_bloqueado = client.post("/auth/login", json={"email": usuario.email, "senha": SENHA_PADRAO})
    assert r_bloqueado.status_code == 423
    assert r_bloqueado.json()["codigo"] == "conta_bloqueada"


def test_rate_limiting_protege_endpoint_de_login(client: TestClient, usuario: Usuario) -> None:
    # Limite configurado: 5/minute em /auth/login
    for _ in range(5):
        res = client.post(
            "/auth/login", json={"email": "naoexiste@exemplo.com", "senha": "qualquer"}
        )
        assert res.status_code == 401

    res_bloqueado = client.post(
        "/auth/login", json={"email": "naoexiste@exemplo.com", "senha": "qualquer"}
    )
    assert res_bloqueado.status_code == 429
    assert res_bloqueado.json()["codigo"] == "limite_de_requisicoes"
    assert "Retry-After" in res_bloqueado.headers


def test_decode_token_rejeita_tipo_trocado(usuario: Usuario) -> None:
    access = create_access_token(usuario.id)
    try:
        decode_token(access.token, REFRESH_TOKEN)
        assert False, "Deveria falhar ao validar access token como refresh token"
    except TokenError as exc:
        assert "tipo" in str(exc).lower()

