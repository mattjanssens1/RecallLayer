"""Soft-deprecated compatibility alias for the current best API surface.

Prefer ``app_best.py`` for all new entrypoints. This module remains only so
older scripts and links keep working during the deprecation window.
"""

from turboquant_db.api.app_best import app, create_app

__all__ = ["app", "create_app"]
