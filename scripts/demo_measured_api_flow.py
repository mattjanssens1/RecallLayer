from fastapi.testclient import TestClient

from turboquant_db.api.app_measured import create_app


def main() -> None:
    client = TestClient(create_app())

    client.put("/v1/vectors/sealed-1", json={"embedding": [1.0, 0.0], "metadata": {"region": "us", "tier": "sealed"}})
    client.put("/v1/vectors/sealed-2", json={"embedding": [0.8, 0.2], "metadata": {"region": "us", "tier": "sealed"}})
    client.post("/v1/flush")
    client.put("/v1/vectors/mutable-1", json={"embedding": [0.95, 0.05], "metadata": {"region": "us", "tier": "mutable"}})

    response = client.post(
        "/v1/query",
        json={
            "embedding": [1.0, 0.0],
            "top_k": 2,
            "approximate": True,
            "rerank": True,
            "filters": {"region": {"eq": "us"}},
        },
    )
    print(response.json())


if __name__ == "__main__":
    main()
