from fastapi.testclient import TestClient

from turboquant_db.api.app_best import create_app


def test_best_api_empty_index_query() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/v1/query",
        json={"embedding": [1.0, 0.0], "top_k": 3, "approximate": True, "rerank": False, "filters": {}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["results"] == []
    assert payload["trace"]["result_count"] == 0
