from fastapi.testclient import TestClient

from turboquant_db.api.app_observed import create_app


def test_observed_showcase_api_returns_diagnostics() -> None:
    app = create_app()
    client = TestClient(app)

    client.put("/v1/vectors/a", json={"embedding": [1.0, 0.0], "metadata": {"region": "us"}})
    client.post("/v1/flush")

    response = client.post(
        "/v1/query",
        json={"embedding": [1.0, 0.0], "top_k": 1, "approximate": True, "rerank": True, "filters": {"region": {"eq": "us"}}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "compressed-reranked-hybrid-observed"
    assert payload["trace"]["latency_ms"] >= 0.0
    assert payload["trace"]["sealed_segment_count"] >= 1
    assert payload["trace"]["filters_applied"] is True
    assert payload["results"][0]["metadata"]["region"] == "us"
