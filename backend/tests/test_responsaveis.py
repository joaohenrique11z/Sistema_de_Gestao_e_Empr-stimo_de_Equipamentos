"""Testes da Task 372: CRUD de Responsáveis com Busca e Verificação de Duplicidade."""

from fastapi.testclient import TestClient

from tests.factories import dados_equipamento, dados_responsavel, formatar_cpf, gerar_cpf


def test_crud_completo_de_responsavel(api: TestClient) -> None:
    cpf = gerar_cpf()
    payload = dados_responsavel(
        nome="Maria Clara Souza",
        cpf=formatar_cpf(cpf),  # envia com máscara para validar normalização
        email="Maria.Souza@Exemplo.com",
        matricula="mat-900",
        departamento="Engenharia",
    )

    # Create
    res_create = api.post("/responsaveis", json=payload)
    assert res_create.status_code == 201, res_create.text
    criado = res_create.json()
    assert criado["cpf"] == cpf
    assert criado["email"] == "maria.souza@exemplo.com"
    assert criado["matricula"] == "MAT-900"
    resp_id = criado["id"]

    # Read
    res_get = api.get(f"/responsaveis/{resp_id}")
    assert res_get.status_code == 200
    assert res_get.json()["nome"] == "Maria Clara Souza"

    # Update
    res_put = api.put(
        f"/responsaveis/{resp_id}",
        json={"nome": "Maria Clara S. Lima", "departamento": "Pesquisa"},
    )
    assert res_put.status_code == 200
    atualizado = res_put.json()
    assert atualizado["nome"] == "Maria Clara S. Lima"
    assert atualizado["departamento"] == "Pesquisa"

    # Delete
    res_del = api.delete(f"/responsaveis/{resp_id}")
    assert res_del.status_code == 204
    assert api.get(f"/responsaveis/{resp_id}").status_code == 404


def test_verificacao_previa_e_bloqueio_de_duplicidade(api: TestClient) -> None:
    cpf_1 = gerar_cpf()
    r1 = api.post(
        "/responsaveis",
        json=dados_responsavel(cpf=cpf_1, email="joao@exemplo.com", matricula="MAT01"),
    ).json()

    # Endpoint de verificação prévia de duplicidade
    res_dup = api.get(
        "/responsaveis/verificar-duplicidade",
        params={"cpf": formatar_cpf(cpf_1), "email": "JOAO@exemplo.com", "matricula": "mat01"},
    )
    assert res_dup.status_code == 200
    verificacao = res_dup.json()
    assert verificacao["duplicado"] is True
    campos_conflito = {c["campo"] for c in verificacao["conflitos"]}
    assert campos_conflito == {"cpf", "email", "matricula"}

    # Excluindo o próprio registo (cenário de edição), não há conflito
    res_proprio = api.get(
        "/responsaveis/verificar-duplicidade",
        params={"cpf": cpf_1, "excluir_id": r1["id"]},
    )
    assert res_proprio.status_code == 200
    assert res_proprio.json()["duplicado"] is False

    # Tentativa de criação duplicada retorna 409 Conflict com detalhe dos campos
    res_conflito = api.post(
        "/responsaveis",
        json=dados_responsavel(cpf=cpf_1, email="outro@exemplo.com", matricula="MAT02"),
    )
    assert res_conflito.status_code == 409
    assert res_conflito.json()["codigo"] == "conflito"
    assert res_conflito.json()["conflitos"][0]["campo"] == "cpf"


def test_busca_de_responsaveis_por_termo_departamento_e_ativo(api: TestClient) -> None:
    cpf_ana = gerar_cpf()
    api.post(
        "/responsaveis",
        json=dados_responsavel(
            nome="Ana Beatriz",
            cpf=cpf_ana,
            email="ana@empresa.com",
            matricula="ENG123",
            departamento="Engenharia",
            ativo=True,
        ),
    )
    api.post(
        "/responsaveis",
        json=dados_responsavel(
            nome="Carlos Eduardo",
            email="carlos@empresa.com",
            matricula="FIN456",
            departamento="Financeiro",
            ativo=False,
        ),
    )

    # Busca por nome
    r_nome = api.get("/responsaveis", params={"q": "beatriz"}).json()
    assert r_nome["total"] == 1
    assert r_nome["items"][0]["nome"] == "Ana Beatriz"

    # Busca por CPF com máscara
    r_cpf = api.get("/responsaveis", params={"q": formatar_cpf(cpf_ana)}).json()
    assert r_cpf["total"] == 1
    assert r_cpf["items"][0]["cpf"] == cpf_ana

    # Busca por matrícula
    r_mat = api.get("/responsaveis", params={"q": "fin456"}).json()
    assert r_mat["total"] == 1
    assert r_mat["items"][0]["nome"] == "Carlos Eduardo"

    # Filtro combinado por departamento e status ativo
    r_filtro = api.get("/responsaveis", params={"departamento": "engenharia", "ativo": True}).json()
    assert r_filtro["total"] == 1
    assert r_filtro["items"][0]["email"] == "ana@empresa.com"


def test_impede_remocao_de_responsavel_com_equipamento_vinculado(api: TestClient) -> None:
    resp = api.post("/responsaveis", json=dados_responsavel()).json()
    api.post("/equipamentos", json=dados_equipamento(responsavel_id=resp["id"]))

    res_del = api.delete(f"/responsaveis/{resp['id']}")
    assert res_del.status_code == 409
    assert "equipamentos vinculados" in res_del.json()["detail"].lower()
