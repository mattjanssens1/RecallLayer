"""Compatibility alias for the current best API surface.

Use ``app_best.py`` for new entrypoints. This module remains so older scripts and
links can keep working while both names still resolve to the same surface.
"""

from turboquant_db.api.app_best import app, create_app

__all__ = ["app", "create_app"]
