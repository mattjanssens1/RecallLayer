from fastapi.testclient import TestClient

from recalllayer.api.showcase_server_observed import create_observed_showcase_app
from recalllayer.api.showcase_server_observed_plus import create_observed_plus_showcase_app


def test_observed_api_exposes_candidate_estimate_aliases() -> None:
    client = TestClient(create_observed_showcase_app())
    client.put('/v1/vectors/a', json={'embedding': [1.0, 0.0], 'metadata': {'region': 'us'}})

    response = client.post('/v1/query', json={'embedding': [1.0, 0.0], 'top_k': 1, 'approximate': False, 'rerank': False})
    payload = response.json()

    assert payload['trace']['candidate_count_estimate'] >= 1
    assert payload['trace']['pre_filter_candidate_estimate'] == payload['trace']['candidate_count_estimate']
    assert payload['trace']['post_filter_candidate_estimate'] == len(payload['results'])


def test_observed_plus_api_exposes_candidate_estimate_aliases() -> None:
    client = TestClient(create_observed_plus_showcase_app())
    client.put('/v1/vectors/a', json={'embedding': [1.0, 0.0], 'metadata': {'region': 'us'}})

    response = client.post('/v1/query', json={'embedding': [1.0, 0.0], 'top_k': 1, 'approximate': False, 'rerank': False})
    payload = response.json()

    assert payload['trace']['candidate_count_estimate'] >= 1
    assert payload['trace']['pre_filter_candidate_estimate'] == payload['trace']['candidate_count_estimate']
    assert payload['trace']['post_filter_candidate_estimate'] == len(payload['results'])
