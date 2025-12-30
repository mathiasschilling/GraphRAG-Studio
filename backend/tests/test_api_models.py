import os

from fastapi.testclient import TestClient

os.environ.setdefault("GRAPHRAG_USE_LLM_STUB", "true")

from app.main import app  # noqa: E402

client = TestClient(app)


def test_list_models_stubbed():
    response = client.get("/models")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
