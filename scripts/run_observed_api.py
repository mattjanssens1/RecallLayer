"""Soft-deprecated compatibility runner for the legacy observed API name.

Prefer ``scripts/run_best_api.py`` for new usage. This runner stays in place so
older notes and commands continue to work during the deprecation window.
"""

import warnings

from turboquant_db.api.app_best import app


if __name__ == "__main__":
    warnings.warn(
        "run_observed_api.py is a soft-deprecated compatibility runner; prefer scripts/run_best_api.py.",
        DeprecationWarning,
        stacklevel=2,
    )
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8001)
