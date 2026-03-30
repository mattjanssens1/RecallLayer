"""Compatibility runner for the legacy observed API name.

Prefer ``scripts/run_best_api.py`` for new usage. This runner stays in place so
older notes and commands continue to work.
"""

from turboquant_db.api.app_best import app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8001)
