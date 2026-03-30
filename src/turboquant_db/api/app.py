from turboquant_db.api.showcase_server_traced import app, create_traced_showcase_app

create_app = create_traced_showcase_app

__all__ = ["app", "create_app"]
