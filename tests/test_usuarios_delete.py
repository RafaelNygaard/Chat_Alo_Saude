"""Exclusão de usuários em Cadastros → Servidores (DELETE /api/admin/usuarios)."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import Config
from app.db import Session
from app.models import AtendenteStatus, Base, Conversa, Usuario


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
    Session.add(Usuario(id=9, nome="Admin", email="adm@ex.com", papel="admin",
                        senha_hash=generate_password_hash("admin123")))
    Session.add(Usuario(id=1, nome="Servidor Comum", matricula="M1", papel="servidor"))
    Session.commit()
    yield app
    Session.remove()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(app):
    client = app.test_client()
    client.post("/api/login", json={"identificador": "adm@ex.com", "senha": "admin123"})
    return client


def test_exclui_usuario_sem_vinculos(client):
    assert client.delete("/api/admin/usuarios/1").status_code == 200
    assert Session.get(Usuario, 1) is None


def test_exclui_atendente_remove_status(client):
    Session.add(Usuario(id=2, nome="Atd", papel="atendente"))
    Session.add(AtendenteStatus(atendente_id=2, status="ausente"))
    Session.commit()
    assert client.delete("/api/admin/usuarios/2").status_code == 200
    assert Session.get(AtendenteStatus, 2) is None


def test_nao_exclui_com_atendimentos_como_servidor(client):
    Session.add(Conversa(id=1, protocolo="AS-2026-00001", usuario_id=1, status="bot"))
    Session.commit()
    assert client.delete("/api/admin/usuarios/1").status_code == 409
    assert Session.get(Usuario, 1) is not None


def test_nao_exclui_com_atendimentos_como_atendente(client):
    Session.add(Usuario(id=2, nome="Atd", papel="atendente"))
    Session.add(Usuario(id=3, nome="Serv", papel="servidor"))
    Session.add(Conversa(id=1, protocolo="AS-2026-00002", usuario_id=3,
                         status="humano", atendente_id=2))
    Session.commit()
    assert client.delete("/api/admin/usuarios/2").status_code == 409


def test_nao_exclui_a_si_mesmo(client):
    assert client.delete("/api/admin/usuarios/9").status_code == 409
    assert Session.get(Usuario, 9) is not None


def test_excluir_inexistente(client):
    assert client.delete("/api/admin/usuarios/999").status_code == 404


def test_excluir_exige_admin(app):
    assert app.test_client().delete("/api/admin/usuarios/1").status_code == 401
