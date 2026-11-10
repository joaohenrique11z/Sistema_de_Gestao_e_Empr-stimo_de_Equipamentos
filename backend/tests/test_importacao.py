"""Testes das Tasks 394 e 397: Importação de Planilha de Equipamentos com Upsert e Validação."""

import io
from fastapi.testclient import TestClient

from tests.factories import dados_equipamento


def test_importacao_csv_sucesso_lote(api: TestClient) -> None:
    csv_content = (
        "codigo_patrimonio,codigo_interno,nome,categoria,marca,modelo,valor_aquisicao,localizacao\n"
        "PAT-IMP-001,INT-IMP-001,Notebook Dell Latitude,Informatica,Dell,Latitude 3420,4500.00,Lab 01\n"
        "PAT-IMP-002,INT-IMP-002,Projetor Epson PowerLite,Audiovisual,Epson,PowerLite E20,2800.00,Auditorio\n"
        "PAT-IMP-003,INT-IMP-003,Multimetro Digital Minipa,Eletronica,Minipa,ET-2082C,350.50,Lab 04\n"
    )

    arquivo = ("equipamentos.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")
    res = api.post("/equipamentos/importar", files={"arquivo": arquivo})
    assert res.status_code == 200, res.text
    dados = res.json()

    assert dados["total_linhas"] == 3
    assert dados["sucessos"] == 3
    assert dados["inseridos"] == 3
    assert dados["atualizados"] == 0
    assert dados["falhas"] == 0
    assert len(dados["erros"]) == 0

    # Verifica se os equipamentos foram cadastrados na busca
    eq1 = api.get("/equipamentos/codigo/PAT-IMP-001")
    assert eq1.status_code == 200
    assert eq1.json()["nome"] == "Notebook Dell Latitude"
    assert eq1.json()["localizacao"] == "Lab 01"


def test_importacao_csv_com_linhas_invalidas_gera_relatorio_de_erros(api: TestClient) -> None:
    csv_content = (
        "codigo_patrimonio;codigo_interno;nome;categoria\n"
        "PAT-VALIDO-10;INT-VALIDO-10;Servidor Rack;TI\n"
        ";INT-SEM-PAT;Item sem patrimonio;TI\n"  # Linha 3: falta patrimonio
        "PAT-COD-IGUAL;PAT-COD-IGUAL;Item codigos iguais;TI\n"  # Linha 4: codigos iguais
        "PAT-VALIDO-20;INT-VALIDO-20;Switch Gigabit;Redes\n"
    )

    arquivo = ("amostra.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")
    res = api.post("/equipamentos/importar", files={"arquivo": arquivo})
    assert res.status_code == 200
    dados = res.json()

    assert dados["total_linhas"] == 4
    assert dados["sucessos"] == 2
    assert dados["inseridos"] == 2
    assert dados["falhas"] == 2
    assert len(dados["erros"]) == 2

    linhas_erro = [e["linha"] for e in dados["erros"]]
    assert 3 in linhas_erro
    assert 4 in linhas_erro


def test_reimportacao_executa_upsert_sem_duplicar(api: TestClient) -> None:
    # 1. Primeira importação
    csv_1 = (
        "codigo_patrimonio,codigo_interno,nome,localizacao\n"
        "PAT-UPSERT-01,INT-UPSERT-01,Câmera Sony Alpha,Estudio A\n"
    )
    api.post(
        "/equipamentos/importar",
        files={"arquivo": ("lote1.csv", io.BytesIO(csv_1.encode("utf-8")), "text/csv")},
    )

    # 2. Reimportação com alteração de localização e nome
    csv_2 = (
        "codigo_patrimonio,codigo_interno,nome,localizacao\n"
        "PAT-UPSERT-01,INT-UPSERT-01,Câmera Sony Alpha 4K,Estudio B (Transferido)\n"
    )
    res2 = api.post(
        "/equipamentos/importar",
        files={"arquivo": ("lote2.csv", io.BytesIO(csv_2.encode("utf-8")), "text/csv")},
    )
    assert res2.status_code == 200
    dados2 = res2.json()

    assert dados2["total_linhas"] == 1
    assert dados2["sucessos"] == 1
    assert dados2["inseridos"] == 0
    assert dados2["atualizados"] == 1

    # Verifica atualização no banco
    eq = api.get("/equipamentos/codigo/PAT-UPSERT-01").json()
    assert eq["nome"] == "Câmera Sony Alpha 4K"
    assert eq["localizacao"] == "Estudio B (Transferido)"


def test_importacao_arquivo_vazio(api: TestClient) -> None:
    arquivo = ("vazio.csv", io.BytesIO(b""), "text/csv")
    res = api.post("/equipamentos/importar", files={"arquivo": arquivo})
    assert res.status_code == 200
    assert res.json()["total_linhas"] == 0
    assert res.json()["falhas"] == 0
