from fastapi.testclient import TestClient

from recalllayer.api.showcase_server_traced import create_traced_showcase_app


def test_traced_showcase_api_exact_and_compressed_modes() -> None:
    app = create_traced_showcase_app()
    client = TestClient(app)

    client.put("/v1/vectors/a", json={"embedding": [1.0, 0.0], "metadata": {"region": "us"}})
    client.put("/v1/vectors/b", json={"embedding": [0.0, 1.0], "metadata": {"region": "ca"}})
    client.post("/v1/flush")

    exact = client.post(
        "/v1/query",
        json={"embedding": [1.0, 0.0], "top_k": 1, "approximate": False, "rerank": False, "filters": {}},
    )
    assert exact.status_code == 200
    assert exact.json()["mode"] == "exact-hybrid-scored"

    compressed = client.post(
        "/v1/query",
        json={"embedding": [1.0, 0.0], "top_k": 1, "approximate": True, "rerank": False, "filters": {}},
    )
    assert compressed.status_code == 200
    assert compressed.json()["mode"] == "compressed-hybrid-scored"
