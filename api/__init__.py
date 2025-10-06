import logging
from sanic import Sanic
from .routes.risk import bp as risk_blueprint
from .routes.health import bp as health_blueprint
from .routes.web import web_bp as web_blueprint
from .routes.data import data_bp as data_blueprint


def create_app():
    """
    Application factory to create and configure the Sanic app.
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    app = Sanic("SatelliteTrackerAPI")

    # Configure OpenAPI/Swagger documentation
    app.config.OAS_URL_PREFIX = "/swagger"
    app.config.OAS_UI_DEFAULT = "swagger"
    app.config.OAS_TITLE = "Satellite Tracker API"
    app.config.CORS_ORIGINS = "*"

    # Register blueprints
    app.blueprint(risk_blueprint)
    app.blueprint(health_blueprint)
    app.blueprint(web_blueprint)
    app.blueprint(data_blueprint)

    return app
