"""Cabeçalho configurável (logo e identidade) — renderizado no servidor."""
import io

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import Config
from app.db import Session
from app.models import Base, Usuario


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


# ------------------------------------------------------------ renderização
def test_logo_aparece_nas_paginas(client):
    corpo = client.get("/").get_data(as_text=True)
    assert '<img class="logo-icone"' in corpo
    assert "logo-alo-saude.png" in corpo
    assert 'class="logo-icone sem-imagem"' not in corpo  # não usa mais o "+"


def test_login_tambem_usa_o_logo(client):
    assert "logo-alo-saude.png" in client.get("/login").get_data(as_text=True)


def test_identidade_configurada_e_renderizada(client):
    _login_admin(client)
    client.put("/api/admin/cabecalho", json={
        "titulo": "Alô Saúde Verão", "subtitulo": "Campanha 2026",
        "orgao": "SMS Poços", "cor_fundo": "#008000"})
    corpo = client.get("/").get_data(as_text=True)
    assert "Alô Saúde Verão" in corpo and "Campanha 2026" in corpo
    assert "SMS Poços" in corpo and "#008000" in corpo


def test_sem_logo_volta_para_o_mais(client):
    _login_admin(client)
    client.put("/api/admin/cabecalho", json={"logo": None})
    corpo = client.get("/").get_data(as_text=True)
    assert 'class="logo-icone sem-imagem"' in corpo
    assert '<img class="logo-icone"' not in corpo


def test_painel_mantem_rotulo_proprio(client):
    """Subtítulo configurável vale para o chat; painéis mantêm sua identificação."""
    _login_admin(client)
    client.put("/api/admin/cabecalho", json={"subtitulo": "Campanha 2026"})
    assert "Painel do Atendente" in client.get("/atendente").get_data(as_text=True)


# ------------------------------------------------------------------ admin
def test_cabecalho_exige_admin(client):
    assert client.get("/api/admin/cabecalho").status_code == 401
    assert client.put("/api/admin/cabecalho", json={"titulo": "x"}).status_code == 401


def test_upload_de_logo_atualiza_config(client):
    _login_admin(client)
    r = client.post("/api/admin/cabecalho/logo",
                    data={"logo": (io.BytesIO(b"\x89PNG\r\n\x1a\n"), "marca.png")},
                    content_type="multipart/form-data")
    assert r.status_code == 200
    caminho = r.get_json()["logo"]
    assert caminho.startswith("/static/uploads/logo_")
    assert client.get("/api/admin/cabecalho").get_json()["logo"] == caminho


def test_upload_rejeita_extensao_invalida(client):
    _login_admin(client)
    r = client.post("/api/admin/cabecalho/logo",
                    data={"logo": (io.BytesIO(b"MZ"), "malware.exe")},
                    content_type="multipart/form-data")
    assert r.status_code == 400
