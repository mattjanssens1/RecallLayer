from recalllayer.api.showcase_server_observed_plus import app, create_observed_plus_showcase_app


def create_app(root_dir: str = ".showcase_observed_plus_api_db"):
    return create_observed_plus_showcase_app(root_dir=root_dir)


__all__ = ["app", "create_app"]
