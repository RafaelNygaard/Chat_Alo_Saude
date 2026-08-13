"""CRUD de atendentes na área administrativa (Operação → Atendentes)."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from werkzeug.security import check_password_hash, generate_password_hash

from app import create_app
from app.config import Config
from app.db import Session
from app.models import AtendenteStatus, Base, Conversa, UBS, Usuario


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
    Session.add(UBS(id=1, nome="UBS Centro", municipio="Poços de Caldas"))
    Session.add(Usuario(id=9, nome="Admin", email="adm@ex.com", papel="admin",
                        senha_hash=generate_password_hash("admin123")))
    Session.commit()
    yield app
    Session.remove()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(app):
    client = app.test_client()
    client.post("/api/login", json={"identificador": "adm@ex.com", "senha": "admin123"})
    return client


def _criar(client, **over):
    dados = {"nome": "Ana", "email": "ana@ex.com", "matricula": "ATD-1",
             "ubs_id": 1, "senha": "segredo1"}
    dados.update(over)
    return client.post("/api/admin/atendentes", json=dados)


# ------------------------------------------------------------------ create
def test_criar_atendente_cria_usuario_e_status(client):
    r = _criar(client)
    assert r.status_code == 201
    aid = r.get_json()["id"]
    u = Session.get(Usuario, aid)
    assert u.papel == "atendente" and u.ubs_id == 1
    assert check_password_hash(u.senha_hash, "segredo1")
    assert Session.get(AtendenteStatus, aid).status == "ausente"   # entra na fila


def test_criar_sem_nome(client):
    assert _criar(client, nome="  ").status_code == 400


def test_criar_matricula_duplicada(client):
    _criar(client)
    assert _criar(client, email="b@ex.com").status_code == 409


# -------------------------------------------------------------------- read
def test_listar_atendentes(client):
    _criar(client)
    lista = client.get("/api/admin/atendentes").get_json()
    assert len(lista) == 1                      # o admin (papel admin) não aparece
    assert lista[0]["nome"] == "Ana" and lista[0]["ubs_nome"] == "UBS Centro"
    assert lista[0]["status"] == "ausente" and lista[0]["tem_senha"] is True


# ------------------------------------------------------------------ update
def test_editar_atendente(client):
    aid = _criar(client).get_json()["id"]
    r = client.put(f"/api/admin/atendentes/{aid}",
                   json={"nome": "Ana Paula", "senha": "novaSenha9"})
    assert r.status_code == 200 and r.get_json()["nome"] == "Ana Paula"
    assert check_password_hash(Session.get(Usuario, aid).senha_hash, "novaSenha9")


def test_editar_nao_atendente_404(client):
    # id 9 é admin, não atendente
    assert client.put("/api/admin/atendentes/9", json={"nome": "X"}).status_code == 404


# ------------------------------------------------------------------ delete
def test_excluir_atendente(client):
    aid = _criar(client).get_json()["id"]
    assert client.delete(f"/api/admin/atendentes/{aid}").status_code == 200
    assert Session.get(Usuario, aid) is None
    assert Session.get(AtendenteStatus, aid) is None


def test_nao_exclui_com_atendimentos_vinculados(client):
    aid = _criar(client).get_json()["id"]
    Session.add(Usuario(id=1, nome="Serv", papel="servidor"))
    Session.add(Conversa(id=1, protocolo="AS-2026-00001", usuario_id=1,
                         status="humano", atendente_id=aid))
    Session.commit()
    r = client.delete(f"/api/admin/atendentes/{aid}")
    assert r.status_code == 409
    assert Session.get(Usuario, aid) is not None   # preservado


# ------------------------------------------------------------- permissão
def test_crud_exige_admin(app):
    anon = app.test_client()   # sem login
    assert anon.get("/api/admin/atendentes").status_code == 401
    assert anon.post("/api/admin/atendentes", json={"nome": "X"}).status_code == 401
    assert anon.delete("/api/admin/atendentes/1").status_code == 401
