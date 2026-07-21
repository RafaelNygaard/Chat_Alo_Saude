"""Smoke test: app cria, rotas registradas, páginas renderizam."""
import pytest

from app import create_app
from app.config import Config


class ConfigTeste(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


@pytest.fixture()
def app():
    return create_app(ConfigTeste)


def test_app_cria_e_registra_rotas(app):
    rotas = {r.rule for r in app.url_map.iter_rules()}
    esperadas = {
        "/", "/atendente",
        "/api/chat", "/api/chips", "/api/conversas",
        "/api/conversas/<int:conversa_id>/mensagens",
        "/api/conversas/<int:conversa_id>/stream",
        "/api/conversas/<int:conversa_id>/encerrar",
        "/api/conversas/<int:conversa_id>/assumir",
        "/api/conversas/<int:conversa_id>/responder",
        "/api/atendente/fila",
        "/api/atendente/<int:atendente_id>/status",
        "/api/atendente/<int:atendente_id>/conversas",
    }
    faltando = esperadas - rotas
    assert not faltando, f"rotas ausentes: {faltando}"


def test_pagina_chat_renderiza(app):
    resp = app.test_client().get("/")
    assert resp.status_code == 200
    corpo = resp.get_data(as_text=True)
    assert "Alô Saúde" in corpo
    assert "chips" in corpo          # chips de ação rápida
    assert "vlibras" in corpo.lower()  # acessibilidade


def test_pagina_atendente_renderiza(app):
    resp = app.test_client().get("/atendente")
    assert resp.status_code == 200
    corpo = resp.get_data(as_text=True)
    assert "Painel do Atendente" in corpo
    assert "FILA DE ESPERA" in corpo


def test_status_atendente_valida_entrada(app):
    resp = app.test_client().post("/api/atendente/1/status", json={"status": "almocando"})
    assert resp.status_code == 400
