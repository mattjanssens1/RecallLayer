from turboquant_db.api.showcase_server_scored import create_scored_showcase_app


def test_scored_showcase_api_app_factory_exists() -> None:
    app = create_scored_showcase_app()
    assert app.title == "TurboQuant Native Vector Database Showcase Scored"
