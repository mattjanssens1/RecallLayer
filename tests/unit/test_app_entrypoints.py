from turboquant_db.api import app as default_app_module
from turboquant_db.api import app_best as best_app_module
from turboquant_db.api import app_inspected as inspected_app_module
from turboquant_db.api import app_measured as measured_app_module


def test_default_and_best_app_share_observed_plus_entrypoint() -> None:
    assert default_app_module.create_app is best_app_module.create_app
    assert default_app_module.app.title == best_app_module.app.title == 'TurboQuant Native Vector Database Showcase Observed Plus'


def test_inspected_and_measured_entrypoints_expose_experimental_surfaces() -> None:
    assert inspected_app_module.app.title == 'TurboQuant Native Vector Database Showcase Inspected'
    assert measured_app_module.app.title == 'TurboQuant Native Vector Database Showcase Measured'
