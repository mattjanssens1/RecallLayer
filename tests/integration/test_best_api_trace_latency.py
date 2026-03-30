from fastapi.testclient import TestClient

from turboquant_db.api.app_best import create_app


def test_best_api_trace_latency_and_candidate_estimate() -> None:
    app = create_app()
    client = TestClient(app)

    client.put("/v1/vectors/a", json={"embedding": [1.0, 0.0], "metadata": {"region": "us"}})
    client.put("/v1/vectors/b", json={"embedding": [0.8, 0.2], "metadata": {"region": "us"}})
    client.post("/v1/flush")

    response = client.post(
        "/v1/query",
        json={"embedding": [1.0, 0.0], "top_k": 2, "approximate": True, "rerank": True, "filters": {"region": {"eq": "us"}}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["trace"]["latency_ms"] >= 0.0
    assert payload["trace"]["candidate_count_estimate"] >= 2
