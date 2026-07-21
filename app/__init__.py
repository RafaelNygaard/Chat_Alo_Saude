"""App factory Flask — Chatbot UBS <-> Alô Saúde (ADR-001)."""
from flask import Flask

from app.config import Config


def create_app(config_object=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    from app.db import init_db
    init_db(app)

    from app.api.chat import bp as chat_bp
    app.register_blueprint(chat_bp, url_prefix="/api")

    from app.api.atendente import bp as atendente_bp
    app.register_blueprint(atendente_bp, url_prefix="/api")

    from app.api.servidores import bp as servidores_bp
    app.register_blueprint(servidores_bp, url_prefix="/api")

    from app.api.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix="/api")

    from app.api.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix="/api")

    from app.pages import bp as pages_bp
    app.register_blueprint(pages_bp)

    return app
