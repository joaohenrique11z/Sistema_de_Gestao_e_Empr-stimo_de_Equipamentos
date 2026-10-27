from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "environment" in data
    assert "app_name" in data
    assert "X-Request-ID" in response.headers


def test_docs_endpoint() -> None:
    response = client.get("/docs")
    assert response.status_code == 200

