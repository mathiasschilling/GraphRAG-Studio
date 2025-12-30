import os
import time
from pathlib import Path

from fastapi.testclient import TestClient

# configure test database before app imports
TEST_DB_PATH = Path("./test_events.db")
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


def test_run_event_history_and_ordering():
    payload = {"name": "demo-flow", "graph": example_graph()}
    create_resp = client.post("/flows", json=payload)
    assert create_resp.status_code == 201
    flow = create_resp.json()

    run_resp = client.post(f"/flows/{flow['id']}/run", json={"input": {"name": "GraphRAG"}})
    assert run_resp.status_code == 200
    run_id = run_resp.json()["id"]

    events = []
    for _ in range(30):
        time.sleep(0.05)
        events_resp = client.get(f"/runs/{run_id}/events")
        assert events_resp.status_code == 200
        events = events_resp.json()
        statuses = [event["status"] for event in events]
        if "run_completed" in statuses or "run_failed" in statuses:
            break
    else:
        raise AssertionError("Timed out waiting for run events")

    sequences = [event["sequence"] for event in events]
    assert sequences == sorted(sequences)
    assert events[0]["status"] == "run_started"
    assert events[-1]["status"] in {"run_completed", "run_failed"}

    node_started = [event for event in events if event["status"] == "started"]
    node_completed = [event for event in events if event["status"] in {"completed", "skipped"}]
    assert node_started
    assert len(node_started) == len(node_completed)

    # Polling with a cursor should return only newer events
    after_resp = client.get(f"/runs/{run_id}/events", params={"after": sequences[0]})
    assert after_resp.status_code == 200
    filtered = after_resp.json()
    assert all(event["sequence"] > sequences[0] for event in filtered)
