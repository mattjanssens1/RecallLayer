from pathlib import Path

from fastapi.testclient import TestClient

from turboquant_db.api.showcase_server_observed_plus import create_observed_plus_showcase_app
from turboquant_db.api.showcase_server_traced import create_traced_showcase_app


def test_traced_api_empty_flush_is_noop(tmp_path: Path) -> None:
    app = create_traced_showcase_app(root_dir=str(tmp_path))
    client = TestClient(app)

    response = client.post('/v1/flush')
    assert response.status_code == 200
    assert response.json() == {'active_segment_ids': []}


def test_observed_plus_api_empty_flush_is_noop(tmp_path: Path) -> None:
    app = create_observed_plus_showcase_app(root_dir=str(tmp_path))
    client = TestClient(app)

    response = client.post('/v1/flush')
    assert response.status_code == 200
    assert response.json() == {'active_segment_ids': []}
