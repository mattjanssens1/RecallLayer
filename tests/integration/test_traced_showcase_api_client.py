from pathlib import Path

from fastapi.testclient import TestClient

from recalllayer.api.showcase_server_traced import create_traced_showcase_app


def test_traced_showcase_api_upsert_flush_and_query(tmp_path: Path) -> None:
    app = create_traced_showcase_app(root_dir=str(tmp_path))
    client = TestClient(app)

    response = client.put(
        "/v1/vectors/doc-1",
        json={"embedding": [1.0, 0.0], "metadata": {"region": "us"}},
    )
    assert response.status_code == 200

    response = client.post("/v1/flush")
    assert response.status_code == 200
    assert response.json()["active_segment_ids"]

    response = client.post(
        "/v1/query",
        json={
            "embedding": [1.0, 0.0],
            "top_k": 1,
            "approximate": True,
            "rerank": True,
            "filters": {"region": {"eq": "us"}},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "compressed-reranked-hybrid-scored"
    assert payload["trace"]["filters_applied"] is True
    assert payload["results"]
    assert payload["results"][0]["vector_id"] == "doc-1"
