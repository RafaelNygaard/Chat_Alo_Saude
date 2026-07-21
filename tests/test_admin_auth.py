"""Testes de identificação do servidor e autenticação/admin (ADR-003).

Rodam sobre SQLite in-memory (StaticPool para as tabelas sobreviverem entre
conexões) — sem PostgreSQL, mantêm o CI verde.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import Config
from app.db import Session
from app.models import Base, Funcao, UBS, Usuario


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
    # dados mínimos para os combos/identificação
    Session.add_all([Funcao(id=1, nome="Enfermeiro(a)"),
                     UBS(id=1, nome="UBS Centro", municipio="Poços de Caldas")])
    Session.commit()
    yield app
    Session.remove()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(app):
    return app.test_client()


# ---------------------------------------------------------- identificação
def test_identificar_cria_servidor(client):
    r = client.post("/api/servidores/identificar", json={
        "nome": "Fulano", "email": "fulano@ex.com", "matricula": "M1",
        "funcao_id": 1, "ubs_id": 1})
    assert r.status_code == 200
    uid = r.get_json()["usuario_id"]
    u = Session.get(Usuario, uid)
    assert u.papel == "servidor" and u.funcao_id == 1 and u.ubs_id == 1


def test_identificar_atualiza_mesmo_por_matricula(client):
    p = {"nome": "Fulano", "email": "f@ex.com", "matricula": "M1", "funcao_id": 1, "ubs_id": 1}
    id1 = client.post("/api/servidores/identificar", json=p).get_json()["usuario_id"]
    p2 = {**p, "nome": "Fulano Silva"}
    id2 = client.post("/api/servidores/identificar", json=p2).get_json()["usuario_id"]
    assert id1 == id2  # find-or-create pela matrícula
    assert Session.get(Usuario, id1).nome == "Fulano Silva"


def test_identificar_valida_obrigatorios(client):
    r = client.post("/api/servidores/identificar", json={"nome": "Só nome"})
    assert r.status_code == 400


def test_identificar_valida_email(client):
    r = client.post("/api/servidores/identificar", json={
        "nome": "X", "email": "invalido", "matricula": "M9", "funcao_id": 1, "ubs_id": 1})
    assert r.status_code == 400


# ---------------------------------------------------------- autenticação
def _cria_admin(senha="segredo"):
    Session.add(Usuario(nome="Adm", email="adm@ex.com", papel="admin",
                        senha_hash=generate_password_hash(senha)))
    Session.commit()


def test_login_sucesso(client):
    _cria_admin()
    r = client.post("/api/login", json={"identificador": "adm@ex.com", "senha": "segredo"})
    assert r.status_code == 200 and r.get_json()["papel"] == "admin"


def test_login_senha_errada(client):
    _cria_admin()
    r = client.post("/api/login", json={"identificador": "adm@ex.com", "senha": "errada"})
    assert r.status_code == 401


def test_servidor_nao_loga_no_painel(client):
    Session.add(Usuario(nome="Serv", email="s@ex.com", papel="servidor",
                        senha_hash=generate_password_hash("x")))
    Session.commit()
    r = client.post("/api/login", json={"identificador": "s@ex.com", "senha": "x"})
    assert r.status_code == 403  # papel sem acesso ao painel


# ---------------------------------------------------------- proteção admin
def test_admin_api_bloqueia_sem_sessao(client):
    assert client.get("/api/admin/funcoes").status_code == 401


def test_admin_pagina_redireciona_sem_sessao(client):
    r = client.get("/admin")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_admin_acessa_com_sessao_admin(client):
    _cria_admin()
    client.post("/api/login", json={"identificador": "adm@ex.com", "senha": "segredo"})
    r = client.get("/api/admin/funcoes")
    assert r.status_code == 200
    assert any(f["nome"] == "Enfermeiro(a)" for f in r.get_json())
