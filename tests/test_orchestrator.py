"""Testes dos gatilhos de handoff (ADR-001, Decisão B) — sem banco, com fakes."""
from app.nlp.engine import Contexto, Entendimento, NLPEngine
from app.orchestrator.handoff import HandoffManager
from app.orchestrator.orchestrator import (
    MENSAGEM_AGUARDE, EstadoConversa, Orquestrador,
)


class FakeNLP(NLPEngine):
    """Devolve entendimentos pré-programados, em ordem."""
    def __init__(self, entendimentos):
        self._fila = list(entendimentos)

    def entender(self, texto):
        return self._fila.pop(0)

    def gerar_resposta(self, contexto: Contexto) -> str:
        return f"resposta para {contexto.entendimento.intent}"


class FakeRepo:
    def __init__(self, disponiveis=None, nomes=None):
        self.disponiveis = disponiveis or []
        self.nomes = nomes or {}
        self.fila = []
        self.atribuicoes = []
        self.notificacoes = []

    def atendentes_disponiveis(self):
        return self.disponiveis

    def nome_atendente(self, atendente_id):
        return self.nomes.get(atendente_id, "")

    def enfileirar(self, conversa_id, gatilho):
        self.fila.append((conversa_id, gatilho))

    def atribuir(self, conversa_id, atendente_id):
        self.atribuicoes.append((conversa_id, atendente_id))

    def notificar_atendente(self, atendente_id, conversa_id):
        self.notificacoes.append((atendente_id, conversa_id))


def montar(entendimentos, disponiveis=None, topicos=("urgente", "emergencia"),
           nomes=None):
    repo = FakeRepo(disponiveis, nomes)
    orq = Orquestrador(
        nlp=FakeNLP(entendimentos),
        handoff=HandoffManager(repo, prazo_sem_atendente_min=30),
        topicos_criticos=list(topicos),
        limiar_confianca=0.6,
        msgs_consecutivas=2,
    )
    return orq, repo


class TestGatilhos:
    def test_pedido_explicito_escala(self):
        orq, repo = montar([Entendimento("falar_com_atendente", 0.9)], disponiveis=[7])
        r = orq.processar(EstadoConversa(1), "quero falar com atendente")
        assert r.handoff and r.gatilho == "pedido_explicito"
        assert repo.atribuicoes == [(1, 7)]
        assert repo.notificacoes == [(7, 1)]

    def test_topico_critico_escala_mesmo_com_confianca_alta(self):
        orq, repo = montar([Entendimento("encaminhamento", 0.95)], disponiveis=[7])
        r = orq.processar(EstadoConversa(1), "Encaminhamento URGENTE de paciente")
        assert r.handoff and r.gatilho == "topico_critico"

    def test_topico_critico_normaliza_acentos(self):
        orq, _ = montar([Entendimento(None, 0.9)], disponiveis=[7])
        r = orq.processar(EstadoConversa(1), "é uma emergência!")
        assert r.handoff and r.gatilho == "topico_critico"

    def test_uma_msg_baixa_confianca_nao_escala(self):
        orq, _ = montar([Entendimento(None, 0.2)])
        estado = EstadoConversa(1)
        r = orq.processar(estado, "mensagem confusa")
        assert not r.handoff
        assert r.autor == "bot"
        assert estado.baixa_confianca_consecutivas == 1

    def test_duas_msgs_baixa_confianca_consecutivas_escalam(self):
        orq, repo = montar([Entendimento(None, 0.2), Entendimento(None, 0.3)],
                           disponiveis=[7])
        estado = EstadoConversa(1)
        orq.processar(estado, "mensagem confusa 1")
        r = orq.processar(estado, "mensagem confusa 2")
        assert r.handoff and r.gatilho == "baixa_confianca"
        assert estado.status == "humano"
        assert repo.fila == [(1, "baixa_confianca")]

    def test_confianca_alta_zera_contador(self):
        orq, _ = montar([Entendimento(None, 0.2), Entendimento("faq", 0.9),
                         Entendimento(None, 0.2)])
        estado = EstadoConversa(1)
        orq.processar(estado, "confusa")
        orq.processar(estado, "clara")
        assert estado.baixa_confianca_consecutivas == 0
        r = orq.processar(estado, "confusa de novo")
        assert not r.handoff  # contador recomeçou: 1 < 2


class TestMensagemDeEspera:
    """Ao escalar, o bot avisa primeiro; o desfecho da fila vem em seguida."""

    def test_bot_avisa_que_esta_transferindo(self):
        orq, _ = montar([Entendimento("falar_com_atendente", 0.9)], disponiveis=[5])
        r = orq.processar(EstadoConversa(1), "quero atendente")
        assert r.autor == "bot"
        assert r.texto == MENSAGEM_AGUARDE
        assert r.texto == ("Aguarde enquanto transfiro esse atendimento "
                           "para um atendente disponível.")

    def test_aviso_vale_para_todos_os_gatilhos(self):
        for entendimento, texto in [
            (Entendimento("falar_com_atendente", 0.9), "quero atendente"),
            (Entendimento("encaminhamento", 0.95), "caso URGENTE"),
        ]:
            orq, _ = montar([entendimento], disponiveis=[5])
            r = orq.processar(EstadoConversa(1), texto)
            assert r.handoff and r.texto == MENSAGEM_AGUARDE


class TestFilaSemAtendente:
    def test_sem_atendente_vai_para_fila_com_prazo(self):
        orq, repo = montar([Entendimento("falar_com_atendente", 0.9)], disponiveis=[])
        estado = EstadoConversa(1)
        r = orq.processar(estado, "quero atendente")
        assert r.handoff
        assert estado.status == "fila"
        assert r.texto == MENSAGEM_AGUARDE            # aviso vem primeiro
        assert "30 minutos" in r.mensagens_extra[0].texto  # desfecho depois
        assert repo.atribuicoes == []

    def test_divisor_nomeia_o_atendente(self):
        orq, _ = montar([Entendimento("falar_com_atendente", 0.9)],
                        disponiveis=[5], nomes={5: "Ana Paula"})
        r = orq.processar(EstadoConversa(1), "quero atendente")
        divisor = r.mensagens_extra[0]
        assert divisor.autor == "sistema"
        assert divisor.texto == "Transferindo para o (a) atendente Ana Paula."

    def test_divisor_sem_nome_usa_fallback(self):
        orq, _ = montar([Entendimento("falar_com_atendente", 0.9)], disponiveis=[5])
        r = orq.processar(EstadoConversa(1), "quero atendente")
        assert r.mensagens_extra[0].texto == "Transferindo para o (a) atendente disponível."


class TestConversaJaEscalada:
    def test_nao_chama_nlp_quando_humano(self):
        orq, _ = montar([])  # FakeNLP vazio: quebraria se fosse chamado
        r = orq.processar(EstadoConversa(1, status="humano"), "oi")
        assert not r.handoff and r.texto == ""
