from turboquant_db.api.showcase_server_inspected import create_inspected_showcase_app
from turboquant_db.api.showcase_server_measured import create_measured_showcase_app
from turboquant_db.api.showcase_server_observed import create_observed_showcase_app
from turboquant_db.api.showcase_server_observed_plus import create_observed_plus_showcase_app
from turboquant_db.api.showcase_server_traced import create_traced_showcase_app


def test_all_surface_app_factories_have_stable_titles() -> None:
    assert create_observed_showcase_app().title == 'TurboQuant Native Vector Database Showcase Observed'
    assert create_observed_plus_showcase_app().title == 'TurboQuant Native Vector Database Showcase Observed Plus'
    assert create_traced_showcase_app().title == 'TurboQuant Native Vector Database Showcase Traced'
    assert create_inspected_showcase_app().title == 'TurboQuant Native Vector Database Showcase Inspected'
    assert create_measured_showcase_app().title == 'TurboQuant Native Vector Database Showcase Measured'
