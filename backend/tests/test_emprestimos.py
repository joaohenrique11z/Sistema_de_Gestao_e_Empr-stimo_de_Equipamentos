"""Testes das Tasks 401, 402, 404, 406, 407 e 409:
- Empréstimo transacional com vínculo automático de acessórios (Task 401 e 402)
- Testes de concorrência e duplo empréstimo bloqueado (Task 404)
- Devolução normal e com dano/manutenção (Task 406 e 409)
- Busca de empréstimos em aberto por item e responsável (Task 407)
"""

from fastapi.testclient import TestClient

from tests.factories import dados_equipamento, dados_responsavel


def test_fluxo_completo_emprestimo_com_acessorios_vinculados_e_devolucao(api: TestClient) -> None:
    # 1. Cadastra responsável ativo
    resp = api.post("/responsaveis", json=dados_responsavel(nome="Professor Carlos Silva")).json()

    # 2. Cadastra notebook com 2 acessórios vinculados (carregador e mouse)
    eq = api.post(
        "/equipamentos",
        json=dados_equipamento(
            nome="Notebook Dell Vostro",
            codigo_patrimonio="PAT-NOTE-100",
            codigo_interno="INT-NOTE-100",
            acessorios=[
                {"nome": "Carregador 65W Original", "quantidade": 1},
                {"nome": "Mouse Óptico USB", "quantidade": 1},
            ],
        ),
    ).json()
    eq_id = eq["id"]

    # 3. Realiza empréstimo (Task 401 e 402)
    res_emp = api.post(
        "/emprestimos",
        json={
            "responsavel_id": resp["id"],
            "equipamento_ids": [eq_id],
            "observacoes": "Empréstimo para semana de tecnologia",
        },
    )
    assert res_emp.status_code == 201, res_emp.text
    dados_emp = res_emp.json()

    assert dados_emp["responsavel_id"] == resp["id"]
    assert dados_emp["responsavel_nome"] == "Professor Carlos Silva"
    assert len(dados_emp["itens"]) == 1
    # Verifica que os acessórios vinculados acompanharam o equipamento (Task 402)
    acessorios_saiu = dados_emp["itens"][0]["acessorios"]
    assert any("Carregador 65W" in a for a in acessorios_saiu)
    assert any("Mouse Óptico" in a for a in acessorios_saiu)

    # Verifica status do equipamento atualizado para EMPRESTADO
    eq_atual = api.get(f"/equipamentos/{eq_id}").json()
    assert eq_atual["status"] == "EMPRESTADO"
    assert eq_atual["responsavel"]["id"] == resp["id"]

    # 4. Consulta empréstimos em aberto (Task 407)
    res_abertos = api.get("/emprestimos/abertos", params={"responsavel_id": resp["id"]})
    assert res_abertos.status_code == 200
    abertos = res_abertos.json()
    assert len(abertos) == 1
    assert abertos[0]["equipamento_id"] == eq_id
    assert abertos[0]["responsavel_nome"] == "Professor Carlos Silva"

    # 5. Devolução normal (Task 406 e 409)
    res_dev = api.post(
        "/emprestimos/devolver",
        json={
            "equipamento_id": eq_id,
            "status_destino": "DISPONIVEL",
            "observacoes": "Devolvido em perfeito estado",
        },
    )
    assert res_dev.status_code == 200
    dados_dev = res_dev.json()
    assert dados_dev["status_novo"] == "DISPONIVEL"

    # Equipamento volta a ficar DISPONÍVEL e sem responsável
    eq_pos_dev = api.get(f"/equipamentos/{eq_id}").json()
    assert eq_pos_dev["status"] == "DISPONIVEL"
    assert eq_pos_dev["responsavel"] is None

    # Consulta de abertos agora não deve mais listar esse equipamento
    res_abertos_pos = api.get("/emprestimos/abertos", params={"responsavel_id": resp["id"]}).json()
    assert len(res_abertos_pos) == 0


def test_concorrencia_duplo_emprestimo_bloqueado_task_404(api: TestClient) -> None:
    resp1 = api.post("/responsaveis", json=dados_responsavel()).json()
    resp2 = api.post("/responsaveis", json=dados_responsavel()).json()

    eq = api.post(
        "/equipamentos",
        json=dados_equipamento(codigo_patrimonio="PAT-CONC-01", codigo_interno="INT-CONC-01"),
    ).json()

    # 1º Empréstimo tem sucesso
    res1 = api.post(
        "/emprestimos",
        json={"responsavel_id": resp1["id"], "equipamento_ids": [eq["id"]]},
    )
    assert res1.status_code == 201

    # 2ª tentativa de emprestar o mesmo item antes de ser devolvido deve falhar com 422 (Task 404)
    res2 = api.post(
        "/emprestimos",
        json={"responsavel_id": resp2["id"], "equipamento_ids": [eq["id"]]},
    )
    assert res2.status_code == 422
    assert "não está disponível" in res2.json()["detail"].lower()


def test_devolucao_com_dano_vai_para_manutencao_task_409(api: TestClient) -> None:
    resp = api.post("/responsaveis", json=dados_responsavel()).json()
    eq = api.post(
        "/equipamentos",
        json=dados_equipamento(codigo_patrimonio="PAT-DANO-01", codigo_interno="INT-DANO-01"),
    ).json()

    # Empresta
    api.post("/emprestimos", json={"responsavel_id": resp["id"], "equipamento_ids": [eq["id"]]})

    # Devolve com relato de avaria/dano
    res_dev = api.post(
        "/emprestimos/devolver",
        json={
            "equipamento_id": eq["id"],
            "status_destino": "MANUTENCAO",
            "avarias": "Tela quebrada após queda durante transporte",
            "observacoes": "Encaminhado para a assistência técnica",
        },
    )
    assert res_dev.status_code == 200
    assert res_dev.json()["status_novo"] == "MANUTENCAO"
    assert res_dev.json()["avarias"] == "Tela quebrada após queda durante transporte"

    # Equipamento agora deve estar em MANUTENCAO
    eq_atual = api.get(f"/equipamentos/{eq['id']}").json()
    assert eq_atual["status"] == "MANUTENCAO"


def test_devolucao_de_equipamento_nao_emprestado_retorna_422(api: TestClient) -> None:
    eq = api.post(
        "/equipamentos",
        json=dados_equipamento(codigo_patrimonio="PAT-LIVRE-01", codigo_interno="INT-LIVRE-01"),
    ).json()

    # Tenta devolver equipamento que já está DISPONIVEL
    res = api.post(
        "/emprestimos/devolver",
        json={"equipamento_id": eq["id"], "status_destino": "DISPONIVEL"},
    )
    assert res.status_code == 422
    assert "não está emprestado" in res.json()["detail"].lower()


def test_emprestimo_bloqueia_responsavel_inativo_ou_inexistente(api: TestClient) -> None:
    eq = api.post(
        "/equipamentos",
        json=dados_equipamento(codigo_patrimonio="PAT-INAT-01", codigo_interno="INT-INAT-01"),
    ).json()

    # Responsável inativo
    resp_inativo = api.post("/responsaveis", json=dados_responsavel(ativo=False)).json()
    res1 = api.post(
        "/emprestimos",
        json={"responsavel_id": resp_inativo["id"], "equipamento_ids": [eq["id"]]},
    )
    assert res1.status_code == 422
    assert "inativo" in res1.json()["detail"].lower()

    # Responsável inexistente
    res2 = api.post(
        "/emprestimos",
        json={"responsavel_id": 999999, "equipamento_ids": [eq["id"]]},
    )
    assert res2.status_code == 422
    assert "não existe" in res2.json()["detail"].lower()
