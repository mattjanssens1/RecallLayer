"""Soft-deprecated compatibility alias for the current best API surface.

Prefer ``app_best.py`` for all new entrypoints. This module remains only so
older scripts and links keep working during the deprecation window.
"""

from recalllayer.api.app_best import app, create_app
from recalllayer.api.app_shared import emit_alias_warning

emit_alias_warning(
    module_name="app_observed.py",
    preferred_module="app_best.py",
    purpose="the current best API surface",
)

__all__ = ["app", "create_app"]
