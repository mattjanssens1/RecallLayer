"""Experimental measured inspection surface.

Prefer ``app_best.py`` for default public usage. This module remains available
for engine-focused measured inspection work and may change faster than the
canonical surface.
"""

from recalllayer.api.showcase_server_measured import app, create_measured_showcase_app

create_app = create_measured_showcase_app

__all__ = ["app", "create_app"]
