"""Testes da Task 413: Painel de Métricas Operacionais e Lista de Pendências."""

from fastapi.testclient import TestClient

from app.models.equipamento import StatusEquipamento
from tests.factories import dados_equipamento, dados_responsavel


def test_dashboard_contadores_e_pendencias(api: TestClient) -> None:
    # 1. Cria um responsável
    resp = api.post("/responsaveis", json=dados_responsavel(nome="Dr. Lucas Oliveira")).json()

    # 2. Cria equipamentos com múltiplos status
    eq_disp = api.post(
        "/equipamentos",
        json=dados_equipamento(codigo_patrimonio="PAT-DASH-01", codigo_interno="INT-DASH-01"),
    ).json()

    eq_emp = api.post(
        "/equipamentos",
        json=dados_equipamento(codigo_patrimonio="PAT-DASH-02", codigo_interno="INT-DASH-02"),
    ).json()

    # Empresta o segundo equipamento
    api.post(
        "/emprestimos",
        json={"responsavel_id": resp["id"], "equipamento_ids": [eq_emp["id"]]},
    )

    # Cria equipamento em manutenção
    eq_manut = api.post(
        "/equipamentos",
        json=dados_equipamento(codigo_patrimonio="PAT-DASH-03", codigo_interno="INT-DASH-03"),
    ).json()
    api.put(f"/equipamentos/{eq_manut['id']}", json={"status": "MANUTENCAO"})

    # 3. Consulta o Dashboard
    res = api.get("/dashboard")
    assert res.status_code == 200, res.text
    dash = res.json()

    # Validação dos contadores
    contadores = dash["contadores"]
    assert contadores["total_equipamentos"] >= 3
    assert contadores["disponiveis"] >= 1
    assert contadores["emprestados"] >= 1
    assert contadores["em_manutencao"] >= 1
    assert contadores["total_responsaveis_ativos"] >= 1

    # Validação das pendências (deve conter o equipamento emprestado)
    pendencias = dash["pendencias"]
    assert any(p["equipamento_id"] == eq_emp["id"] for p in pendencias)
    pendencia_emp = next(p for p in pendencias if p["equipamento_id"] == eq_emp["id"])
    assert pendencia_emp["responsavel_nome"] == "Dr. Lucas Oliveira"
    assert pendencia_emp["codigo_patrimonio"] == "PAT-DASH-02"

    # Validação das últimas movimentações
    movs = dash["ultimas_movimentacoes"]
    assert len(movs) > 0
    assert any(m["tipo"] == "EMPRESTIMO" for m in movs)
