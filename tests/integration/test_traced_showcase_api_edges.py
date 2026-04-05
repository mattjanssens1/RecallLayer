from fastapi.testclient import TestClient

from recalllayer.api.showcase_server_traced import create_traced_showcase_app


def test_traced_showcase_api_empty_query_and_bad_payload(tmp_path) -> None:
    app = create_traced_showcase_app(root_dir=str(tmp_path / ".showcase_traced_api_db"))
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
