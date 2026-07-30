"""Recuperação por senha temporária + troca no 1º acesso + config de e-mail.

SQLite in-memory (StaticPool) — sem PostgreSQL nem SMTP; o e-mail cai no log.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from werkzeug.security import check_password_hash, generate_password_hash

from app import create_app
from app import repositories as repo
from app.config import Config
from app.db import Session
from app.models import Base, ConfigEmail, Usuario


class ConfigTeste(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SECRET_KEY = "chave-teste"


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
    Session.add(Usuario(id=3, nome="Admin", email="adm@ex.com", papel="admin",
                        senha_hash=generate_password_hash("admin123")))
    Session.commit()
    yield app
    Session.remove()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(app):
    return app.test_client()


def _login_admin(client):
    client.post("/api/login", json={"identificador": "adm@ex.com", "senha": "admin123"})


# ------------------------------------------------------------ recuperação
def test_recuperar_gera_senha_temporaria(client):
    hash_antes = Session.get(Usuario, 1).senha_hash
    r = client.post("/api/recuperar-senha", json={"identificador": "M1"})
    assert r.status_code == 200
    u = Session.get(Usuario, 1)
    assert u.senha_temporaria is True
    assert u.senha_hash != hash_antes                 # senha trocada
    assert not check_password_hash(u.senha_hash, "antiga1")


def test_recuperar_resposta_generica_sem_enumeracao(client):
    r1 = client.post("/api/recuperar-senha", json={"identificador": "M1"})
    r2 = client.post("/api/recuperar-senha", json={"identificador": "NAO-EXISTE"})
    assert r1.get_json()["mensagem"] == r2.get_json()["mensagem"]


def test_recuperar_sem_email_nao_gera_temporaria(client):
    client.post("/api/recuperar-senha", json={"identificador": "M2"})
    assert Session.get(Usuario, 2).senha_temporaria is False


# ------------------------------------------------- login + troca obrigatória
def test_login_com_senha_temporaria_entra_normalmente(client):
    # A troca de senha acontece por "Esqueci minha senha", não no login:
    # a senha temporária autentica e abre sessão como qualquer outra.
    temp = repo.gerar_senha_temporaria(Session.get(Usuario, 3))
    r = client.post("/api/login", json={"identificador": "adm@ex.com", "senha": temp})
    assert r.status_code == 200 and r.get_json()["papel"] == "admin"
    assert client.get("/api/sessao").status_code == 200   # sessão aberta


def test_servidor_login_reporta_senha_temporaria(client):
    temp = repo.gerar_senha_temporaria(Session.get(Usuario, 1))
    r = client.post("/api/servidores/login", json={"identificador": "M1", "senha": temp})
    assert r.status_code == 200 and r.get_json()["senha_temporaria"] is True


def test_trocar_senha_limpa_flag_e_autentica(client):
    temp = repo.gerar_senha_temporaria(Session.get(Usuario, 1))
    r = client.post("/api/trocar-senha", json={
        "identificador": "M1", "senha_atual": temp, "nova_senha": "minhaNova9"})
    assert r.status_code == 200
    u = Session.get(Usuario, 1)
    assert u.senha_temporaria is False
    assert check_password_hash(u.senha_hash, "minhaNova9")


def test_trocar_senha_atual_incorreta(client):
    assert client.post("/api/trocar-senha", json={
        "identificador": "M1", "senha_atual": "errada", "nova_senha": "minhaNova9"}).status_code == 401


def test_trocar_senha_nova_curta(client):
    assert client.post("/api/trocar-senha", json={
        "identificador": "M1", "senha_atual": "antiga1", "nova_senha": "123"}).status_code == 400


def test_trocar_senha_igual_atual(client):
    assert client.post("/api/trocar-senha", json={
        "identificador": "M1", "senha_atual": "antiga1", "nova_senha": "antiga1"}).status_code == 400


# ------------------------------------------------------- config de e-mail
def test_config_email_exige_admin(client):
    assert client.get("/api/admin/email").status_code == 401
    assert client.put("/api/admin/email", json={"assunto": "x", "corpo": "y"}).status_code == 401


def test_salvar_config_cifra_senha_e_nao_devolve(client):
    _login_admin(client)
    r = client.put("/api/admin/email", json={
        "host": "mail.ex.gov.br", "porta": 587, "email": "no-reply@ex.gov.br",
        "senha": "segredoSMTP", "assunto": "Recuperação", "corpo": "Olá {{username}}"})
    assert r.status_code == 200
    assert "senha" not in r.get_json() and r.get_json()["tem_senha"] is True
    # guardada cifrada, mas decifrável para uso
    cfg = Session.get(ConfigEmail, 1)
    assert cfg.smtp_senha_cif and cfg.smtp_senha_cif != "segredoSMTP"
    with client.application.app_context():   # decifrar precisa do current_app
        assert repo.smtp_config()["senha"] == "segredoSMTP"


def test_config_email_assunto_corpo_obrigatorios(client):
    _login_admin(client)
    assert client.put("/api/admin/email", json={"assunto": "", "corpo": ""}).status_code == 400


def test_testar_conexao_exige_host(client):
    _login_admin(client)
    r = client.post("/api/admin/email/testar", json={"host": ""})
    assert r.status_code == 400 and r.get_json()["ok"] is False


# ------------------------------------------------------------- criptografia
def test_cifrar_decifrar_roundtrip(app):
    with app.app_context():
        from app.seguranca import cifrar, decifrar
        cif = cifrar("segredo-123")
        assert cif != "segredo-123"
        assert decifrar(cif) == "segredo-123"
        assert decifrar("lixo-invalido") == ""    # não estoura, retorna vazio
