import importlib
import warnings


def test_app_observed_emits_deprecation_warning() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        import recalllayer.api.app_observed as module
        importlib.reload(module)

    messages = [str(item.message) for item in caught]
    assert any("app_observed.py is a soft-deprecated compatibility alias" in message for message in messages)
