"""Feedback Útil/Não útil por resposta do bot (gov.br DS)."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app import create_app
from app.config import Config
from app.db import Session
from app.models import Base, Conversa, FeedbackMensagem, Mensagem, Usuario


class ConfigTeste(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SECRET_KEY = "teste"


@pytest.fixture()
def app():
    app = create_app(ConfigTeste)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Session.configure(bind=engine)
    Base.metadata.create_all(engine)
    Session.add(Usuario(id=1, nome="Serv", papel="servidor"))
    Session.add(Conversa(id=1, protocolo="AS-2026-00001", usuario_id=1, status="bot"))
    Session.add(Mensagem(id=10, conversa_id=1, autor="bot", texto="Resposta do bot"))
    Session.commit()
    yield app
    Session.remove()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(app):
    return app.test_client()


def test_registra_feedback_util(client):
    r = client.post("/api/mensagens/10/feedback", json={"util": True})
    assert r.status_code == 200 and r.get_json()["util"] is True
    assert Session.query(FeedbackMensagem).filter_by(mensagem_id=10).one().util is True


def test_um_feedback_por_mensagem(client):
    client.post("/api/mensagens/10/feedback", json={"util": True})
    client.post("/api/mensagens/10/feedback", json={"util": False})   # atualiza
    fbs = Session.query(FeedbackMensagem).filter_by(mensagem_id=10).all()
    assert len(fbs) == 1 and fbs[0].util is False


def test_feedback_mensagem_inexistente(client):
    assert client.post("/api/mensagens/999/feedback", json={"util": True}).status_code == 404
