"""Testes das Tasks 378, 384 e 390:
- Task 378: Endpoints POST, GET e PUT em /equipamentos com transação atómica e rollback
- Task 384: Listagem com paginação, múltiplos filtros combinados e ordenação dinâmica
- Task 390: Busca por código de património ou código interno
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError
from app.models import Acessorio, Equipamento, Movimentacao, Usuario
from app.repositories import MovimentacaoRepository
from app.schemas.equipamento import AcessorioIn, EquipamentoCreate
from app.services import EquipamentoService
from tests.factories import dados_equipamento, dados_responsavel


# --------------------------------------------------------------------------- #
# Task 378: POST, GET, PUT /equipamentos + Transação Atómica e Rollback
# --------------------------------------------------------------------------- #
def test_criar_obter_e_atualizar_equipamento_com_acessorios_e_movimentacoes(
    api: TestClient,
) -> None:
    resp = api.post("/responsaveis", json=dados_responsavel()).json()

    payload = dados_equipamento(
        codigo_patrimonio="pat-2026-01",
        codigo_interno="int-2026-01",
        nome="Osciloscópio Digital",
        responsavel_id=resp["id"],
        acessorios=[
            {"nome": "Ponta de Prova 100MHz", "quantidade": 2},
            {"nome": "Cabo de Alimentação", "quantidade": 1},
        ],
    )
    res_post = api.post("/equipamentos", json=payload)
    assert res_post.status_code == 201, res_post.text
    criado = res_post.json()
    eq_id = criado["id"]
    assert criado["codigo_patrimonio"] == "PAT-2026-01"
    assert criado["codigo_interno"] == "INT-2026-01"
    assert len(criado["acessorios"]) == 2
    assert criado["responsavel"]["id"] == resp["id"]

    # Consulta individual GET /equipamentos/{id}
    res_get = api.get(f"/equipamentos/{eq_id}")
    assert res_get.status_code == 200
    assert res_get.json()["nome"] == "Osciloscópio Digital"

    # Verifica histórico inicial: 1 CADASTRO + 2 VINCULO_ACESSORIO
    movs_iniciais = api.get(f"/equipamentos/{eq_id}/movimentacoes").json()
    assert [m["tipo"] for m in movs_iniciais] == [
        "CADASTRO",
        "VINCULO_ACESSORIO",
        "VINCULO_ACESSORIO",
    ]

    # Atualização PUT /equipamentos/{id}: altera status, mantém/edita 1º acessório,
    # remove o 2º e adiciona um 3º acessório na mesma transação
    primeiro_acessorio_id = criado["acessorios"][0]["id"]
    res_put = api.put(
        f"/equipamentos/{eq_id}",
        json={
            "status": "EMPRESTADO",
            "localizacao": "Laboratório 3",
            "acessorios": [
                {"id": primeiro_acessorio_id, "nome": "Ponta de Prova 100MHz", "quantidade": 4},
                {"nome": "Maleta de Transporte", "quantidade": 1},
            ],
        },
    )
    assert res_put.status_code == 200, res_put.text
    atualizado = res_put.json()
    assert atualizado["status"] == "EMPRESTADO"
    assert atualizado["localizacao"] == "Laboratório 3"
    nomes_acessorios = {a["nome"]: a["quantidade"] for a in atualizado["acessorios"]}
    assert nomes_acessorios == {"Ponta de Prova 100MHz": 4, "Maleta de Transporte": 1}

    # Verifica histórico completo após atualização
    movs_finais = api.get(f"/equipamentos/{eq_id}/movimentacoes").json()
    tipos = [m["tipo"] for m in movs_finais]
    assert tipos == [
        "CADASTRO",
        "VINCULO_ACESSORIO",
        "VINCULO_ACESSORIO",
        "ATUALIZACAO",
        "DESVINCULO_ACESSORIO",
        "VINCULO_ACESSORIO",
        "VINCULO_ACESSORIO",
    ]


def test_rollback_atomico_na_criacao_se_falhar_registro_de_movimentacao(
    db_session: Session, usuario: Usuario
) -> None:
    """Se falhar o vínculo/movimentação do 2º acessório, nada pode ser gravado no banco."""
    service = EquipamentoService(db_session)
    dados = EquipamentoCreate(
        **dados_equipamento(
            codigo_patrimonio="PAT-ROLLBACK-01",
            codigo_interno="INT-ROLLBACK-01",
            acessorios=[
                AcessorioIn(nome="Acessório 1", quantidade=1),
                AcessorioIn(nome="Acessório 2 que falha", quantidade=1),
            ],
        )
    )

    original = MovimentacaoRepository.registrar
    chamadas = 0

    def falhar_na_terceira_chamada(self, *args, **kwargs):
        nonlocal chamadas
        chamadas += 1
        if chamadas == 3:  # 1=CADASTRO, 2=1º acessório, 3=2º acessório -> erro!
            raise RuntimeError("Falha simulada ao registar movimentação do acessório")
        return original(self, *args, **kwargs)

    with patch.object(MovimentacaoRepository, "registrar", falhar_na_terceira_chamada):
        with pytest.raises(RuntimeError, match="Falha simulada"):
            service.criar(dados, usuario)

    assert db_session.scalar(select(func.count()).select_from(Equipamento)) == 0
    assert db_session.scalar(select(func.count()).select_from(Acessorio)) == 0
    assert db_session.scalar(select(func.count()).select_from(Movimentacao)) == 0


def test_rollback_atomico_na_atualizacao_quando_acessorio_invalido(
    api: TestClient, db_session: Session
) -> None:
    """Se um acessório enviado no PUT não pertence ao equipamento, a alteração do
    equipamento e a movimentação de atualização sofrem rollback completo."""
    criado = api.post(
        "/equipamentos",
        json=dados_equipamento(
            nome="Projetor Original",
            status="DISPONIVEL",
            acessorios=[{"nome": "Controle Remoto", "quantidade": 1}],
        ),
    ).json()
    eq_id = criado["id"]

    # Tenta atualizar o nome/status junto com um id de acessório inexistente (999999)
    res_put = api.put(
        f"/equipamentos/{eq_id}",
        json={
            "nome": "Projetor Alterado Indevidamente",
            "status": "MANUTENCAO",
            "acessorios": [{"id": 999999, "nome": "Acessório Fantasma", "quantidade": 1}],
        },
    )
    assert res_put.status_code == 422
    assert res_put.json()["codigo"] == "regra_de_negocio"

    # Confirma que o equipamento manteve o estado original e nenhuma movimentação extra foi salva
    atual = api.get(f"/equipamentos/{eq_id}").json()
    assert atual["nome"] == "Projetor Original"
    assert atual["status"] == "DISPONIVEL"
    assert len(atual["acessorios"]) == 1

    movs = api.get(f"/equipamentos/{eq_id}/movimentacoes").json()
    assert len(movs) == 2  # apenas CADASTRO + VINCULO_ACESSORIO iniciais


# --------------------------------------------------------------------------- #
# Task 384: Listagem com Paginação, Filtros Combinados e Ordenação Dinâmica
# --------------------------------------------------------------------------- #
def test_listagem_com_paginacao_filtros_combinados_e_ordenacao(api: TestClient) -> None:
    resp = api.post("/responsaveis", json=dados_responsavel()).json()

    itens = [
        dados_equipamento(
            codigo_patrimonio="PAT-101",
            codigo_interno="INT-101",
            nome="Notebook Dell XPS",
            categoria="Informática",
            marca="Dell",
            status="DISPONIVEL",
            localizacao="Sala 10",
            data_aquisicao="2024-01-10",
            valor_aquisicao="8000.00",
            responsavel_id=resp["id"],
            acessorios=[{"nome": "Carregador USB-C", "quantidade": 1}],
        ),
        dados_equipamento(
            codigo_patrimonio="PAT-102",
            codigo_interno="INT-102",
            nome="Notebook Lenovo ThinkPad",
            categoria="Informática",
            marca="Lenovo",
            status="EMPRESTADO",
            localizacao="Sala 10",
            data_aquisicao="2024-06-20",
            valor_aquisicao="6500.00",
            responsavel_id=resp["id"],
        ),
        dados_equipamento(
            codigo_patrimonio="PAT-103",
            codigo_interno="INT-103",
            nome="Furadeira de Impacto",
            categoria="Ferramentas",
            marca="Bosch",
            status="MANUTENCAO",
            localizacao="Oficina Central",
            data_aquisicao="2023-05-01",
            valor_aquisicao="950.00",
        ),
        dados_equipamento(
            codigo_patrimonio="PAT-104",
            codigo_interno="INT-104",
            nome="Monitor Dell UltraSharp",
            categoria="Informática",
            marca="Dell",
            status="DISPONIVEL",
            localizacao="Sala 20",
            data_aquisicao="2024-09-01",
            valor_aquisicao="3200.00",
        ),
    ]
    for item in itens:
        assert api.post("/equipamentos", json=item).status_code == 201

    # 1. Paginação + Ordenação decrescente por valor_aquisicao
    p1 = api.get(
        "/equipamentos",
        params={"pagina": 1, "tamanho_pagina": 2, "ordenar_por": "-valor_aquisicao"},
    ).json()
    assert p1["total"] == 4
    assert p1["total_paginas"] == 2
    assert [i["codigo_patrimonio"] for i in p1["items"]] == ["PAT-101", "PAT-102"]

    p2 = api.get(
        "/equipamentos",
        params={"pagina": 2, "tamanho_pagina": 2, "ordenar_por": "-valor_aquisicao"},
    ).json()
    assert [i["codigo_patrimonio"] for i in p2["items"]] == ["PAT-104", "PAT-103"]

    # 2. Múltiplos filtros combinados
    filtrado = api.get(
        "/equipamentos",
        params={
            "categoria": "informática",
            "marca": "dell",
            "status": ["DISPONIVEL"],
            "possui_acessorios": True,
            "valor_min": "5000",
        },
    ).json()
    assert filtrado["total"] == 1
    assert filtrado["items"][0]["codigo_patrimonio"] == "PAT-101"

    # 3. Filtro por sem_responsavel e intervalo de datas
    sem_resp = api.get(
        "/equipamentos",
        params={
            "sem_responsavel": True,
            "data_aquisicao_inicio": "2024-01-01",
            "data_aquisicao_fim": "2024-12-31",
        },
    ).json()
    assert sem_resp["total"] == 1
    assert sem_resp["items"][0]["codigo_patrimonio"] == "PAT-104"

    # 4. Campo de ordenação inválido retorna 422 com a whitelist
    res_invalido = api.get("/equipamentos", params={"ordenar_por": "coluna_inexistente"})
    assert res_invalido.status_code == 422
    assert "campos_permitidos" in res_invalido.json()


# --------------------------------------------------------------------------- #
# Task 390: Busca por Código de Património ou Código Interno
# --------------------------------------------------------------------------- #
def test_busca_equipamento_por_codigo_patrimonio_ou_interno(api: TestClient) -> None:
    criado = api.post(
        "/equipamentos",
        json=dados_equipamento(
            codigo_patrimonio="PAT-LAB/0099",
            codigo_interno="INT-LAB-0099",
            nome="Multímetro Digital True RMS",
        ),
    ).json()

    # Busca pelo código de património (case-insensitive, suportando '/')
    r_pat = api.get("/equipamentos/codigo/pat-lab/0099")
    assert r_pat.status_code == 200
    assert r_pat.json()["id"] == criado["id"]

    # Busca pelo código interno
    r_int = api.get("/equipamentos/codigo/int-lab-0099")
    assert r_int.status_code == 200
    assert r_int.json()["id"] == criado["id"]

    # Restringindo o tipo da busca: procurar código interno exigindo tipo=patrimonio deve dar 404
    r_tipo_errado = api.get(
        "/equipamentos/codigo/INT-LAB-0099", params={"tipo": "patrimonio"}
    )
    assert r_tipo_errado.status_code == 404

    r_tipo_certo = api.get(
        "/equipamentos/codigo/INT-LAB-0099", params={"tipo": "interno"}
    )
    assert r_tipo_certo.status_code == 200
    assert r_tipo_certo.json()["id"] == criado["id"]

    # Código inexistente retorna 404
    assert api.get("/equipamentos/codigo/NAO-EXISTE").status_code == 404

