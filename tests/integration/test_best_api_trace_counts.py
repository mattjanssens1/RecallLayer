from fastapi.testclient import TestClient

from turboquant_db.api.app_best import create_app


def test_best_api_trace_counts_include_mutable_and_sealed_hits() -> None:
    app = create_app()
    client = TestClient(app)

    client.put("/v1/vectors/sealed-1", json={"embedding": [1.0, 0.0], "metadata": {"region": "us"}})
    client.post("/v1/flush")
    client.put("/v1/vectors/mutable-1", json={"embedding": [0.95, 0.05], "metadata": {"region": "us"}})

    response = client.post(
        "/v1/query",
        json={"embedding": [1.0, 0.0], "top_k": 2, "approximate": True, "rerank": True, "filters": {"region": {"eq": "us"}}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["trace"]["mutable_hit_count"] >= 0
    assert payload["trace"]["sealed_hit_count"] >= 0
    assert payload["trace"]["sealed_segment_ids"]
