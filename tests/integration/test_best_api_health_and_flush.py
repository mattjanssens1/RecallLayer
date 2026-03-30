from fastapi.testclient import TestClient

from turboquant_db.api.app_best import create_app


def test_best_api_health_and_flush() -> None:
    app = create_app()
    client = TestClient(app)

    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    client.put("/v1/vectors/a", json={"embedding": [1.0, 0.0], "metadata": {"region": "us"}})
    flush = client.post("/v1/flush")
    assert flush.status_code == 200
    assert flush.json()["active_segment_ids"]
