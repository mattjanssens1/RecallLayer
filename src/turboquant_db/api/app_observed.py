"""Soft-deprecated compatibility alias for the current best API surface.

Prefer ``app_best.py`` for all new entrypoints. This module remains only so
older scripts and links keep working during the deprecation window.
"""

import warnings

warnings.warn(
    "app_observed.py is a soft-deprecated compatibility alias; prefer app_best.py for new entrypoints.",
    DeprecationWarning,
    stacklevel=2,
)

from turboquant_db.api.app_best import app, create_app

__all__ = ["app", "create_app"]
