from fastapi.testclient import TestClient

from recalllayer.api.app_best import create_app


def test_best_api_exact_and_reranked_modes() -> None:
    app = create_app()
    client = TestClient(app)

    client.put("/v1/vectors/a", json={"embedding": [1.0, 0.0], "metadata": {"region": "us"}})
    client.put("/v1/vectors/b", json={"embedding": [0.8, 0.2], "metadata": {"region": "us"}})
    client.post("/v1/flush")

    exact = client.post(
        "/v1/query",
        json={"embedding": [1.0, 0.0], "top_k": 1, "approximate": False, "rerank": False, "filters": {}},
    )
    reranked = client.post(
        "/v1/query",
        json={"embedding": [1.0, 0.0], "top_k": 2, "approximate": True, "rerank": True, "filters": {"region": {"eq": "us"}}},
    )

    assert exact.status_code == 200
    assert reranked.status_code == 200
    assert exact.json()["mode"] == "exact-hybrid-observed-plus"
    assert reranked.json()["mode"] == "compressed-reranked-hybrid-observed-plus"
