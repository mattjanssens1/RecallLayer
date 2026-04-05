"""Experimental inspection surface.

Prefer ``app_best.py`` for default public usage. This module remains available
for engine-focused inspection work and may change faster than the canonical
surface.
"""

from recalllayer.api.showcase_server_inspected import app, create_inspected_showcase_app

create_app = create_inspected_showcase_app

__all__ = ["app", "create_app"]
