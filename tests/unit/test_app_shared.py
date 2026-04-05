import warnings

from recalllayer.api.app_shared import build_alias_warning, emit_alias_warning


def test_build_alias_warning_formats_message() -> None:
    message = build_alias_warning(
        module_name='app_observed.py',
        preferred_module='app_best.py',
        purpose='the current best API surface',
    )

    assert message == 'app_observed.py is a soft-deprecated compatibility alias for the current best API surface; prefer app_best.py for new entrypoints.'


def test_emit_alias_warning_emits_deprecation_warning() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        emit_alias_warning(
            module_name='app_observed.py',
            preferred_module='app_best.py',
            purpose='the current best API surface',
        )

    assert any('app_observed.py is a soft-deprecated compatibility alias' in str(item.message) for item in caught)
