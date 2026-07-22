"""Pesquisa de satisfação + mensagem de encerramento configurável.

SQLite in-memory (StaticPool) — sem PostgreSQL, mantém o CI verde.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import Config
from app.db import Session
from app.models import Base, Conversa, PesquisaSatisfacao, Usuario


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
    Session.commit()
    yield app
    Session.remove()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(app):
    return app.test_client()


def _login_admin(client):
    Session.add(Usuario(nome="Adm", email="adm@ex.com", papel="admin",
                        senha_hash=generate_password_hash("segredo")))
    Session.commit()
    client.post("/api/login", json={"identificador": "adm@ex.com", "senha": "segredo"})


# ------------------------------------------------------------ pesquisa
def test_pesquisa_grava_e_encerra(client):
    r = client.post("/api/conversas/1/pesquisa", json={"nota": 5, "comentario": "Ótimo!"})
    assert r.status_code == 200
    assert r.get_json()["status"] == "Encerrado"
    assert Session.get(Conversa, 1).status == "encerrada"
    p = Session.query(PesquisaSatisfacao).filter_by(conversa_id=1).one()
    assert p.nota == 5 and p.comentario == "Ótimo!"


def test_pesquisa_devolve_mensagem_final(client):
    enc = client.post("/api/conversas/1/pesquisa", json={"nota": 4}).get_json()["encerramento"]
    assert enc["texto"] == (
        "A equipe do Alô Saúde agradece seu contato e deseja uma ótima semana!")


@pytest.mark.parametrize("nota", [0, 6, "abc", None])
def test_pesquisa_valida_nota(client, nota):
    r = client.post("/api/conversas/1/pesquisa", json={"nota": nota})
    assert r.status_code == 400
    assert Session.get(Conversa, 1).status != "encerrada"  # não encerra com nota inválida


def test_pesquisa_conversa_inexistente(client):
    assert client.post("/api/conversas/999/pesquisa", json={"nota": 3}).status_code == 404


def test_pesquisa_uma_por_conversa(client):
    client.post("/api/conversas/1/pesquisa", json={"nota": 2})
    client.post("/api/conversas/1/pesquisa", json={"nota": 5})
    assert Session.query(PesquisaSatisfacao).filter_by(conversa_id=1).count() == 1
    assert Session.query(PesquisaSatisfacao).filter_by(conversa_id=1).one().nota == 5


def test_encerrar_sem_pesquisa_pula(client):
    r = client.post("/api/conversas/1/encerrar")
    assert r.status_code == 200 and "encerramento" in r.get_json()
    assert Session.query(PesquisaSatisfacao).count() == 0


# ------------------------------------------------- configuração (admin)
def test_encerramento_publico_para_o_chat(client):
    j = client.get("/api/encerramento").get_json()
    assert "texto" in j and j["cor_fundo"] and "imagem" in j


def test_admin_salva_mensagem(client):
    _login_admin(client)
    r = client.put("/api/admin/encerramento", json={
        "texto": "Obrigado! 💙", "cor_fundo": "#000000", "cor_texto": "#ffffff",
        "imagem_como_fundo": True})
    assert r.status_code == 200
    assert client.get("/api/encerramento").get_json()["texto"] == "Obrigado! 💙"


def test_admin_texto_obrigatorio(client):
    _login_admin(client)
    assert client.put("/api/admin/encerramento", json={"texto": "  "}).status_code == 400


def test_config_encerramento_exige_admin(client):
    assert client.get("/api/admin/encerramento").status_code == 401
    assert client.put("/api/admin/encerramento", json={"texto": "x"}).status_code == 401


def test_upload_rejeita_extensao(client):
    _login_admin(client)
    import io
    r = client.post("/api/admin/encerramento/imagem",
                    data={"imagem": (io.BytesIO(b"MZ"), "virus.exe")},
                    content_type="multipart/form-data")
    assert r.status_code == 400
