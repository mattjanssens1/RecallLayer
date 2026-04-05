from fastapi.testclient import TestClient

from recalllayer.api.app import create_app


def test_traced_showcase_api_repeated_flush_cycles() -> None:
    app = create_app()
    client = TestClient(app)

    client.put("/v1/vectors/a", json={"embedding": [1.0, 0.0], "metadata": {"region": "us"}})
    first_flush = client.post("/v1/flush")
    assert first_flush.status_code == 200

    client.put("/v1/vectors/b", json={"embedding": [0.0, 1.0], "metadata": {"region": "ca"}})
    second_flush = client.post("/v1/flush")
    assert second_flush.status_code == 200

    response = client.post(
        "/v1/query",
        json={"embedding": [1.0, 0.0], "top_k": 2, "approximate": False, "rerank": False, "filters": {}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["trace"]["sealed_segment_count"] >= 1
    assert payload["results"]
