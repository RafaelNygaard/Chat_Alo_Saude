"""Fila de atendentes com distribuição balanceada (round-robin).

Regra: quem encerra um atendimento vai para o FIM da fila; quem nunca atendeu
vem primeiro. Exercita o SqlHandoffRepository de verdade sobre SQLite.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app import create_app
from app import repositories as repo
from app.config import Config
from app.db import Session
from app.models import AtendenteStatus, Base, Conversa, Usuario
from app.orchestrator.handoff import HandoffManager


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
    for i, nome in [(10, "Ana"), (11, "Bruno"), (12, "Carla")]:
        Session.add(Usuario(id=i, nome=nome, papel="atendente"))
        Session.add(AtendenteStatus(atendente_id=i, status="disponivel"))
    Session.commit()
    yield app
    Session.remove()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(app):
    return app.test_client()


def _conversa(cid: int, atendente_id=None, status="humano") -> Conversa:
    c = Conversa(id=cid, protocolo=f"AS-2026-{cid:05d}", usuario_id=1,
                 status=status, atendente_id=atendente_id)
    Session.add(c)
    Session.commit()
    return c


@pytest.fixture()
def fila(app):
    return repo.SqlHandoffRepository()


# ----------------------------------------------------------------- ordenação
def test_quem_nunca_atendeu_vem_primeiro(app, fila):
    assert fila.atendentes_disponiveis() == [10, 11, 12]


def test_quem_encerra_vai_para_o_fim(app, fila):
    repo.liberar_atendente(10)                      # Ana encerrou
    assert fila.atendentes_disponiveis() == [11, 12, 10]


def test_ordem_segue_sequencia_de_encerramentos(app, fila):
    for aid in (10, 11, 12):
        repo.liberar_atendente(aid)
    # todos já atenderam: a ordem é a dos encerramentos (o mais antigo à frente)
    assert fila.atendentes_disponiveis() == [10, 11, 12]
    repo.liberar_atendente(10)                      # Ana encerra de novo
    assert fila.atendentes_disponiveis() == [11, 12, 10]


def test_ocupado_e_ausente_ficam_fora_da_fila(app, fila):
    Session.get(AtendenteStatus, 10).status = "ocupado"
    Session.get(AtendenteStatus, 11).status = "ausente"
    Session.commit()
    assert fila.atendentes_disponiveis() == [12]


# -------------------------------------------------------- liberação ao encerrar
def test_encerrar_libera_o_atendente(client, app):
    _conversa(1, atendente_id=10)
    Session.get(AtendenteStatus, 10).status = "ocupado"
    Session.commit()

    client.post("/api/conversas/1/encerrar")

    st = Session.get(AtendenteStatus, 10)
    assert st.status == "disponivel"                # volta ao pool
    assert st.ultimo_encerramento_em is not None     # e vai para o fim da fila


def test_encerrar_por_pesquisa_tambem_libera(client, app):
    _conversa(2, atendente_id=11)
    Session.get(AtendenteStatus, 11).status = "ocupado"
    Session.commit()

    client.post("/api/conversas/2/pesquisa", json={"nota": 5})

    assert Session.get(AtendenteStatus, 11).status == "disponivel"


def test_encerrar_respeita_quem_se_marcou_ausente(client, app):
    _conversa(3, atendente_id=12)
    Session.get(AtendenteStatus, 12).status = "ausente"   # saiu do expediente
    Session.commit()

    client.post("/api/conversas/3/encerrar")

    assert Session.get(AtendenteStatus, 12).status == "ausente"  # não é reativado


# ------------------------------------------------------- distribuição balanceada
def test_rodizio_distribui_igualmente(client, app):
    """Seis atendimentos entre três atendentes -> dois para cada, em rodízio."""
    gestor = HandoffManager(repo.SqlHandoffRepository())
    atribuidos = []
    for i in range(1, 7):
        _conversa(i, status="bot")
        resultado = gestor.escalar(i, "pedido_explicito")
        atribuidos.append(resultado.atendente_id)
        client.post(f"/api/conversas/{i}/encerrar")   # encerra -> volta ao fim

    assert atribuidos == [10, 11, 12, 10, 11, 12]     # rodízio perfeito
    assert {a: atribuidos.count(a) for a in (10, 11, 12)} == {10: 2, 11: 2, 12: 2}
