from fastapi.testclient import TestClient

from recalllayer.api.app_observed import create_app


def test_observed_api_basic_modes() -> None:
    app = create_app()
    client = TestClient(app)

    client.put("/v1/vectors/a", json={"embedding": [1.0, 0.0], "metadata": {"region": "us"}})
    client.put("/v1/vectors/b", json={"embedding": [0.0, 1.0], "metadata": {"region": "ca"}})
    client.post("/v1/flush")

    exact = client.post("/v1/query", json={"embedding": [1.0, 0.0], "top_k": 1, "approximate": False, "rerank": False, "filters": {}})
    compressed = client.post("/v1/query", json={"embedding": [1.0, 0.0], "top_k": 1, "approximate": True, "rerank": False, "filters": {}})

    assert exact.status_code == 200
    assert compressed.status_code == 200
    assert exact.json()["mode"] == "exact-hybrid-observed-plus"
    assert compressed.json()["mode"] == "compressed-hybrid-observed-plus"
