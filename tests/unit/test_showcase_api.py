from recalllayer.api.showcase_server import create_showcase_app


def test_showcase_api_app_factory_exists() -> None:
    app = create_showcase_app()
    assert app.title == "TurboQuant Native Vector Database Showcase"
