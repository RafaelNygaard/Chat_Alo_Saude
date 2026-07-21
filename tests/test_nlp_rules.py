"""Testes do pré-processamento e do motor A1 (regras + FAQ)."""
from app.nlp.engine import Contexto
from app.nlp.preprocess import normalizar
from app.nlp.rules_engine import RESPOSTA_FALLBACK, IntentDef, RulesEngine, similaridade

INTENTS = [
    IntentDef(
        intent="falar_com_atendente",
        padroes=["quero falar com atendente", "falar com humano",
                 "transferir para agente", "preciso de um atendente"],
        resposta="Certo, vou transferir você.",
    ),
    IntentDef(
        intent="notificacao_compulsoria",
        padroes=["notificacao compulsoria", "prazo para notificar dengue",
                 "como notificar no sinan"],
        resposta="O prazo padrão é de 24h para agravos imediatos.",
    ),
]


def engine() -> RulesEngine:
    return RulesEngine(INTENTS)


class TestNormalizacao:
    def test_remove_acentos_e_pontuacao(self):
        assert normalizar("Notificação compulsória!!") == "notificacao compulsoria"

    def test_colapsa_espacos_e_minusculas(self):
        assert normalizar("  QUERO   Falar ") == "quero falar"


class TestSimilaridade:
    def test_identicos(self):
        assert similaridade("falar com humano", "falar com humano") == 1.0

    def test_sem_relacao_baixa(self):
        assert similaridade("bom dia", "notificacao compulsoria") < 0.2

    def test_variacao_proxima_alta(self):
        assert similaridade("quero falar com um atendente",
                            "quero falar com atendente") > 0.6


class TestRulesEngine:
    def test_reconhece_pedido_atendente(self):
        e = engine().entender("Quero falar com um atendente, por favor")
        assert e.intent == "falar_com_atendente"
        assert e.confianca >= 0.6

    def test_reconhece_com_acentos(self):
        e = engine().entender("qual o prazo para notificar Dengue?")
        assert e.intent == "notificacao_compulsoria"
        assert e.confianca >= 0.6

    def test_confianca_baixa_para_texto_fora_do_dominio(self):
        e = engine().entender("qual a previsão do tempo amanhã em Poços?")
        assert e.confianca < 0.6

    def test_gera_resposta_do_intent(self):
        eng = engine()
        ent = eng.entender("como notificar no SINAN")
        assert "24h" in eng.gerar_resposta(Contexto(entendimento=ent, texto_usuario=""))

    def test_fallback_sem_intent(self):
        eng = engine()
        ent = eng.entender("xyzabc")
        ctx = Contexto(entendimento=ent, texto_usuario="xyzabc")
        if ent.confianca < 0.3:
            assert eng.gerar_resposta(ctx) in (RESPOSTA_FALLBACK,
                                               *[i.resposta for i in INTENTS])
