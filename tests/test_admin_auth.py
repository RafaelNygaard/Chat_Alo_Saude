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
def _dados_servidor(**over):
    d = {"nome": "Fulano", "email": "fulano@ex.com", "matricula": "M1",
         "senha": "segredo1", "funcao_id": 1, "ubs_id": 1}
    d.update(over)
    return d


def test_identificar_cadastra_servidor(client):
    r = client.post("/api/servidores/identificar", json=_dados_servidor())
    assert r.status_code == 200
    u = Session.get(Usuario, r.get_json()["usuario_id"])
    assert u.papel == "servidor" and u.funcao_id == 1 and u.senha_hash  # senha gravada como hash


def test_identificar_autentica_e_atualiza(client):
    id1 = client.post("/api/servidores/identificar", json=_dados_servidor()).get_json()["usuario_id"]
    # mesma matrícula + senha correta -> mesmo id, dados atualizados
    r2 = client.post("/api/servidores/identificar", json=_dados_servidor(nome="Fulano Silva"))
    assert r2.status_code == 200 and r2.get_json()["usuario_id"] == id1
    assert Session.get(Usuario, id1).nome == "Fulano Silva"


def test_identificar_senha_incorreta(client):
    client.post("/api/servidores/identificar", json=_dados_servidor())
    r = client.post("/api/servidores/identificar", json=_dados_servidor(senha="outra1"))
    assert r.status_code == 401


def test_identificar_senha_curta(client):
    r = client.post("/api/servidores/identificar", json=_dados_servidor(senha="123"))
    assert r.status_code == 400


def test_identificar_valida_obrigatorios(client):
    r = client.post("/api/servidores/identificar", json={"nome": "Só nome"})
    assert r.status_code == 400


def test_identificar_valida_email(client):
    r = client.post("/api/servidores/identificar", json=_dados_servidor(email="invalido"))
    assert r.status_code == 400


# ------------------------------------------------- login do profissional
def test_login_servidor_por_matricula(client):
    uid = client.post("/api/servidores/identificar",
                      json=_dados_servidor()).get_json()["usuario_id"]
    r = client.post("/api/servidores/login",
                    json={"identificador": "M1", "senha": "segredo1"})
    assert r.status_code == 200
    j = r.get_json()
    assert j["usuario_id"] == uid and j["funcao_id"] == 1  # devolve dados p/ a UI


def test_login_servidor_por_email(client):
    client.post("/api/servidores/identificar", json=_dados_servidor())
    r = client.post("/api/servidores/login",
                    json={"identificador": "fulano@ex.com", "senha": "segredo1"})
    assert r.status_code == 200


def test_login_servidor_senha_errada(client):
    client.post("/api/servidores/identificar", json=_dados_servidor())
    r = client.post("/api/servidores/login",
                    json={"identificador": "M1", "senha": "errada9"})
    assert r.status_code == 401


def test_login_servidor_nao_cadastrado(client):
    r = client.post("/api/servidores/login",
                    json={"identificador": "M-INEXISTENTE", "senha": "qualquer"})
    assert r.status_code == 401
    assert "Cadastrar usuário" in r.get_json()["erro"]  # orienta o cadastro


def test_login_servidor_nao_cria_usuario(client):
    antes = Session.query(Usuario).count()
    client.post("/api/servidores/login", json={"identificador": "novo@ex.com", "senha": "x"})
    assert Session.query(Usuario).count() == antes  # login nunca cadastra


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
