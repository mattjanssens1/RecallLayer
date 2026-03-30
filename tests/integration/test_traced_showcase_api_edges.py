from fastapi.testclient import TestClient

from turboquant_db.api.app import create_app


def test_traced_showcase_api_empty_query_and_bad_payload() -> None:
    app = create_app()
    client = TestClient(app)

    empty = client.post(
        "/v1/query",
        json={"embedding": [1.0, 0.0], "top_k": 3, "approximate": True, "rerank": False, "filters": {}},
    )
    assert empty.status_code == 200
    assert empty.json()["results"] == []
    assert empty.json()["trace"]["result_count"] == 0

    bad = client.post(
        "/v1/query",
        json={"embedding": [], "top_k": 0, "approximate": True, "rerank": False, "filters": {}},
    )
    assert bad.status_code == 422
