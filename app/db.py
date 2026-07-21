"""Sessão SQLAlchemy. Mantido fora dos models para facilitar testes sem banco."""
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

engine = None
Session = scoped_session(sessionmaker())


def init_db(app):
    global engine
    try:
        engine = create_engine(app.config["SQLALCHEMY_DATABASE_URI"], pool_pre_ping=True)
        Session.configure(bind=engine)
    except Exception as exc:  # driver ausente ou URL inválida: app sobe, DB falha só na requisição
        app.logger.warning("Banco indisponível na inicialização (%s). "
                            "Páginas carregam; rotas de API que usam o banco falharão.", exc)

    @app.teardown_appcontext
    def cleanup(_exc):
        Session.remove()
