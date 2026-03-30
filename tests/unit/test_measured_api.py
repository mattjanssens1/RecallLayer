from fastapi.testclient import TestClient

from turboquant_db.api.app_measured import create_app


def test_measured_api_reports_real_candidate_counts() -> None:
    client = TestClient(create_app())

    client.put("/v1/vectors/sealed-1", json={"embedding": [1.0, 0.0], "metadata": {"region": "us"}})
    client.put("/v1/vectors/sealed-2", json={"embedding": [0.7, 0.3], "metadata": {"region": "ca"}})
    client.post("/v1/flush")
    client.put("/v1/vectors/mutable-1", json={"embedding": [0.95, 0.05], "metadata": {"region": "us"}})

    response = client.post(
        "/v1/query",
        json={
            "embedding": [1.0, 0.0],
            "top_k": 2,
            "approximate": True,
            "rerank": True,
            "filters": {"region": {"eq": "us"}},
        },
    )

    payload = response.json()
    assert payload["mode"] == "compressed-reranked-hybrid-engine"
    assert payload["trace"]["pre_filter_candidate_count"] >= 3
    assert payload["trace"]["post_filter_candidate_count"] >= 2
    assert payload["trace"]["mutable_hit_count"] >= 1
    assert payload["trace"]["sealed_hit_count"] >= 1
    assert payload["trace"]["total_latency_ms"] >= payload["trace"]["search_latency_ms"]


def test_measured_api_exact_mode_has_no_rerank_latency() -> None:
    client = TestClient(create_app())
    client.put("/v1/vectors/a", json={"embedding": [1.0, 0.0], "metadata": {"region": "us"}})

    response = client.post(
        "/v1/query",
        json={"embedding": [1.0, 0.0], "top_k": 1, "approximate": False, "rerank": False, "filters": {"region": {"eq": "us"}}},
    )

    payload = response.json()
    assert payload["mode"] == "exact-hybrid-engine"
    assert payload["trace"]["rerank_candidate_k"] is None
    assert payload["trace"]["rerank_latency_ms"] == 0.0
