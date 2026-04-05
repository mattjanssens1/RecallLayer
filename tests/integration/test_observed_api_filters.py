from fastapi.testclient import TestClient

from recalllayer.api.app_observed import create_app


def test_observed_api_filtering_behaves_as_expected() -> None:
    app = create_app()
    client = TestClient(app)

    client.put("/v1/vectors/us-1", json={"embedding": [1.0, 0.0], "metadata": {"region": "us", "tier": "gold"}})
    client.put("/v1/vectors/ca-1", json={"embedding": [0.0, 1.0], "metadata": {"region": "ca", "tier": "silver"}})
    client.post("/v1/flush")

    response = client.post(
        "/v1/query",
        json={
            "embedding": [1.0, 0.0],
            "top_k": 5,
            "approximate": True,
            "rerank": True,
            "filters": {"region": {"eq": "us"}, "tier": {"in": ["gold", "platinum"]}},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["results"]
    assert payload["results"][0]["metadata"]["region"] == "us"
    assert payload["trace"]["filters_applied"] is True
