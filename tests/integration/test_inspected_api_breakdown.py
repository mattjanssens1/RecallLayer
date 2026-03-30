from fastapi.testclient import TestClient

from turboquant_db.api.app_inspected import create_app


def test_inspected_api_returns_breakdown_fields() -> None:
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
    assert payload["trace"]["pre_filter_candidate_estimate"] >= 2
    assert payload["trace"]["post_filter_candidate_estimate"] >= 2
    assert payload["trace"]["search_latency_ms"] >= 0.0
    assert payload["trace"]["rerank_latency_ms"] >= 0.0
    assert payload["trace"]["total_latency_ms"] >= payload["trace"]["search_latency_ms"]
