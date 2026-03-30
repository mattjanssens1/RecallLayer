from fastapi.testclient import TestClient

from turboquant_db.api.app_best import create_app


def main() -> None:
    client = TestClient(create_app())

    client.put("/v1/vectors/a", json={"embedding": [1.0, 0.0], "metadata": {"region": "us"}})
    client.put("/v1/vectors/b", json={"embedding": [0.8, 0.2], "metadata": {"region": "us"}})
    client.post("/v1/flush")

    response = client.post(
        "/v1/query",
        json={"embedding": [1.0, 0.0], "top_k": 2, "approximate": True, "rerank": True, "filters": {"region": {"eq": "us"}}},
    )
    print(response.json())


if __name__ == "__main__":
    main()
