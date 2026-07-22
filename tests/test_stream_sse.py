"""Stream SSE: cada mensagem é entregue uma única vez (Decisão C do ADR-001).

O bug original: a URL do EventSource é fixa, então a reconexão automática do
navegador reenviava tudo a partir do `after` inicial — mensagens repetindo em
ciclo. O servidor passou a emitir `id:` e a honrar `Last-Event-ID`.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app import create_app
from app.config import Config
from app.db import Session
from app.models import Base, Conversa, Mensagem, Usuario


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
    Session.add(Usuario(id=1, nome="Servidor", papel="servidor"))
    Session.add(Conversa(id=1, protocolo="AS-2026-00001", usuario_id=1, status="bot"))
    Session.add_all([
        Mensagem(id=1, conversa_id=1, autor="usuario", texto="encaminhamento urgente"),
        Mensagem(id=2, conversa_id=1, autor="bot", texto="Aguarde enquanto transfiro..."),
    ])
    Session.commit()
    yield app
    Session.remove()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(app):
    return app.test_client()


def _ler(resp, n=4) -> str:
    """Lê só o início do stream (o ciclo completo dura ~25 s)."""
    it = iter(resp.response)
    saida = ""
    for _ in range(n):
        try:
            pedaco = next(it)
        except StopIteration:
            break
        saida += pedaco.decode() if isinstance(pedaco, bytes) else pedaco
        if "event: status" in saida:   # fim da 1ª volta do laço
            break
    resp.close()
    return saida


def test_stream_envia_mensagens_pendentes(client):
    saida = _ler(client.get("/api/conversas/1/stream?after=0"))
    assert "encaminhamento urgente" in saida
    assert "id: 1" in saida and "id: 2" in saida   # id para o cliente retomar


def test_stream_nao_reenvia_o_que_ja_foi_entregue(client):
    saida = _ler(client.get("/api/conversas/1/stream?after=2"))
    assert "encaminhamento urgente" not in saida
    assert "Aguarde" not in saida


def test_last_event_id_evita_reenvio_na_reconexao(client):
    """Reconexão com URL antiga (after=0) não pode repetir as mensagens."""
    saida = _ler(client.get("/api/conversas/1/stream?after=0",
                            headers={"Last-Event-ID": "2"}))
    assert "encaminhamento urgente" not in saida
    assert "Aguarde" not in saida


def test_encerrar_duas_vezes_grava_uma_unica_mensagem(client):
    client.post("/api/conversas/1/encerrar")
    client.post("/api/conversas/1/encerrar")
    encerramentos = (
        Session.query(Mensagem)
        .filter_by(conversa_id=1, texto="Atendimento encerrado").count()
    )
    assert encerramentos == 1


def test_pesquisa_apos_encerrar_nao_duplica_mensagem(client):
    client.post("/api/conversas/1/encerrar")
    client.post("/api/conversas/1/pesquisa", json={"nota": 5})
    encerramentos = (
        Session.query(Mensagem)
        .filter_by(conversa_id=1, texto="Atendimento encerrado").count()
    )
    assert encerramentos == 1
