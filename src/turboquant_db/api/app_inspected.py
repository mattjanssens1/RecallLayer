from turboquant_db.api.showcase_server_inspected import app, create_inspected_showcase_app

create_app = create_inspected_showcase_app

__all__ = ["app", "create_app"]
