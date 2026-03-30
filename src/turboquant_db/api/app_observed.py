from turboquant_db.api.showcase_server_observed import app, create_observed_showcase_app

create_app = create_observed_showcase_app

__all__ = ["app", "create_app"]
