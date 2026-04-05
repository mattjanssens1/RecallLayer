from fastapi.testclient import TestClient

from recalllayer.api.app_best import create_app


def test_best_api_validation_rejects_bad_query_payload() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/v1/query",
        json={"embedding": [], "top_k": 0, "approximate": True, "rerank": False, "filters": {}},
    )

    assert response.status_code == 422
