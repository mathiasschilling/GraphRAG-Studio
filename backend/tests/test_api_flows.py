import os
import time
from pathlib import Path

from fastapi.testclient import TestClient

# configure test database before app imports
TEST_DB_PATH = Path("./test_api.db")
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

os.environ["GRAPHRAG_DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

from app.main import app  # noqa: E402
from app.persistence.db import init_db  # noqa: E402

init_db()
client = TestClient(app)


def example_graph():
    return {
        "id": "demo",
        "nodes": {
            "user": {"id": "user", "type": "UserInputNode", "config": {"key": "input"}},
            "prompt": {
                "id": "prompt",
                "type": "PromptTemplateNode",
                "config": {"template": "Hello {input}"},
            },
            "llm": {"id": "llm", "type": "LLMNode", "config": {"model": "test-model"}},
            "final": {"id": "final", "type": "FinalAnswerNode", "config": {"key": "response"}},
        },
        "edges": [
            {"id": "e1", "from_node": "user", "from_output": "input", "to_node": "prompt"},
            {"id": "e2", "from_node": "prompt", "from_output": "prompt", "to_node": "llm"},
            {"id": "e3", "from_node": "llm", "from_output": "response", "to_node": "final"},
        ],
    }


def test_flow_crud_and_run():
    payload = {"name": "demo-flow", "graph": example_graph()}

    create_resp = client.post("/flows", json=payload)
    assert create_resp.status_code == 201
    flow = create_resp.json()
    assert flow["name"] == "demo-flow"

    update_graph = example_graph()
    update_graph["id"] = flow["id"]
    update_resp = client.put(f"/flows/{flow['id']}", json={"name": "updated-flow", "graph": update_graph})
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["name"] == "updated-flow"

    # Ensure the latest saved version is returned when the flow is reloaded.
    get_resp = client.get(f"/flows/{flow['id']}")
    assert get_resp.status_code == 200
    fetched = get_resp.json()
    assert fetched["name"] == "updated-flow"
    assert fetched["graph"]["id"] == update_graph["id"]

    list_resp = client.get("/flows")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    run_resp = client.post(f"/flows/{flow['id']}/run", json={"input": {"name": "GraphRAG"}})
    assert run_resp.status_code == 200
    run_data = run_resp.json()
    assert run_data["status"] in {"running", "pending"}

    # Poll for completion so we can assert on outputs and per-node logs
    for _ in range(20):
        time.sleep(0.05)
        current = client.get(f"/runs/{run_data['id']}")
        assert current.status_code == 200
        payload = current.json()
        if payload["status"] == "completed":
            run_data = payload
            break
    else:
        raise AssertionError("Run did not complete in time during test")

    assert run_data["output_payload"]["final"]["output"].startswith("[test-model] Hello")
    assert run_data["started_at"] is not None
    assert run_data["completed_at"] is not None
    node_outputs = run_data["node_outputs"]
    assert "llm" in node_outputs

    prompt_log = node_outputs["prompt"]
    assert prompt_log["inputs"] == {"input": {"name": "GraphRAG"}}
    assert prompt_log["outputs"]["prompt"].startswith("Hello")
    assert prompt_log["duration_ms"] >= 0
    assert prompt_log["skipped"] is False

    user_log = node_outputs["user"]
    assert user_log["inputs"] == {}
    assert user_log["outputs"] == {"input": {"name": "GraphRAG"}}

    delete_resp = client.delete(f"/flows/{flow['id']}")
    assert delete_resp.status_code == 204
