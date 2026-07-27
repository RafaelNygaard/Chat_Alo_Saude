"""Recuperação de senha: token com hash, prazo e uso único (ADR-003).

SQLite in-memory (StaticPool) — sem PostgreSQL nem SMTP; o e-mail cai no log.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from werkzeug.security import check_password_hash, generate_password_hash

from app import create_app
from app import repositories as repo
from app.config import Config
from app.db import Session
from app.models import Base, TokenRecuperacao, Usuario


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
    Session.add(Usuario(id=1, nome="Carla", email="carla@ex.com", matricula="M1",
                        papel="servidor", senha_hash=generate_password_hash("antiga1")))
    Session.add(Usuario(id=2, nome="Sem Email", matricula="M2", papel="servidor"))
    Session.commit()
    yield app
    Session.remove()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(app):
    return app.test_client()


# ---------------------------------------------------------- repositório
def test_token_guardado_como_hash(app):
    token = repo.criar_token_recuperacao(1, ttl_min=60)
    row = Session.query(TokenRecuperacao).filter_by(usuario_id=1).one()
    assert row.token_hash != token                 # nunca guarda o token em claro
    assert row.token_hash == repo._hash_token(token)
    assert repo.token_recuperacao_valido(token).usuario_id == 1


def test_novo_token_invalida_o_anterior(app):
    t1 = repo.criar_token_recuperacao(1)
    t2 = repo.criar_token_recuperacao(1)
    assert repo.token_recuperacao_valido(t1) is None   # o anterior deixa de valer
    assert repo.token_recuperacao_valido(t2) is not None


def test_token_expirado_invalido(app):
    token = repo.criar_token_recuperacao(1)
    row = Session.query(TokenRecuperacao).filter_by(usuario_id=1, usado_em=None).one()
    row.expira_em = datetime.now(timezone.utc) - timedelta(minutes=1)
    Session.commit()
    assert repo.token_recuperacao_valido(token) is None


def test_redefinir_troca_a_senha_e_consome_token(app):
    token = repo.criar_token_recuperacao(1)
    assert repo.redefinir_senha_por_token(token, "novaSenha9") is True
    assert check_password_hash(Session.get(Usuario, 1).senha_hash, "novaSenha9")
    assert repo.token_recuperacao_valido(token) is None          # uso único
    assert repo.redefinir_senha_por_token(token, "outra12") is False


# ------------------------------------------------------------- endpoints
def test_recuperar_resposta_generica_sem_enumeracao(client):
    r1 = client.post("/api/recuperar-senha", json={"identificador": "M1"})
    r2 = client.post("/api/recuperar-senha", json={"identificador": "NAO-EXISTE"})
    assert r1.status_code == r2.status_code == 200
    assert r1.get_json()["mensagem"] == r2.get_json()["mensagem"]   # idêntica
    assert Session.query(TokenRecuperacao).count() == 1            # só p/ quem existe


def test_recuperar_sem_email_nao_gera_token(client):
    client.post("/api/recuperar-senha", json={"identificador": "M2"})  # usuário sem e-mail
    assert Session.query(TokenRecuperacao).filter_by(usuario_id=2).count() == 0


def test_validar_token_endpoint(client):
    token = repo.criar_token_recuperacao(1)
    assert client.get(f"/api/recuperar-senha/validar?token={token}").get_json()["valido"]
    assert not client.get("/api/recuperar-senha/validar?token=lixo").get_json()["valido"]


def test_redefinir_endpoint_sucesso(client):
    token = repo.criar_token_recuperacao(1)
    r = client.post("/api/redefinir-senha", json={"token": token, "senha": "novaSenha9"})
    assert r.status_code == 200
    assert check_password_hash(Session.get(Usuario, 1).senha_hash, "novaSenha9")


def test_redefinir_senha_curta(client):
    token = repo.criar_token_recuperacao(1)
    assert client.post("/api/redefinir-senha", json={"token": token, "senha": "123"}).status_code == 400


def test_redefinir_token_invalido(client):
    assert client.post("/api/redefinir-senha",
                       json={"token": "invalido", "senha": "novaSenha9"}).status_code == 400
