from fastapi.testclient import TestClient

from recalllayer.api.app_best import create_app


def test_observed_plus_api_validation_and_diagnostics() -> None:
    app = create_app()
    client = TestClient(app)

    bad = client.post(
        "/v1/query",
        json={"embedding": [], "top_k": 0, "approximate": True, "rerank": False, "filters": {}},
    )
    assert bad.status_code == 422

    client.put("/v1/vectors/a", json={"embedding": [1.0, 0.0], "metadata": {"region": "us"}})
    client.post("/v1/flush")

    good = client.post(
        "/v1/query",
        json={"embedding": [1.0, 0.0], "top_k": 1, "approximate": True, "rerank": True, "filters": {"region": {"eq": "us"}}},
    )
    assert good.status_code == 200
    payload = good.json()
    assert payload["trace"]["latency_ms"] >= 0.0
    assert payload["trace"]["mutable_hit_count"] >= 0
    assert payload["trace"]["sealed_hit_count"] >= 0
