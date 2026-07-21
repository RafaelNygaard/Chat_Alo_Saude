"""Implementação A1 da NLPEngine: regras + FAQ (ADR-001, Decisão A).

Matching por similaridade trigram (equivalente em Python ao pg_trgm) sobre os
padrões da tabela faq_intents. Em produção, os intents vêm do banco via
IntentRepository; nos testes, de uma lista em memória.
"""
from dataclasses import dataclass

from app.nlp.engine import Contexto, Entendimento, NLPEngine
from app.nlp.preprocess import normalizar

RESPOSTA_FALLBACK = (
    "Não tenho certeza se entendi sua dúvida. Pode reformular? "
    "Se preferir, posso transferir você para um atendente."
)


@dataclass
class IntentDef:
    intent: str
    padroes: list[str]   # exemplos de frases
    resposta: str


def _trigrams(texto: str) -> set[str]:
    """Trigramas no estilo pg_trgm (texto com padding de 2 espaços à esquerda, 1 à direita)."""
    t = f"  {texto} "
    return {t[i:i + 3] for i in range(len(t) - 2)}


def similaridade(a: str, b: str) -> float:
    """Similaridade de Jaccard sobre trigramas — mesmo princípio do pg_trgm."""
    ta, tb = _trigrams(normalizar(a)), _trigrams(normalizar(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


class RulesEngine(NLPEngine):
    def __init__(self, intents: list[IntentDef]):
        self._intents = intents
        self._respostas = {i.intent: i.resposta for i in intents}

    def entender(self, texto: str) -> Entendimento:
        melhor_intent, melhor_score = None, 0.0
        for intent_def in self._intents:
            for padrao in intent_def.padroes:
                score = similaridade(texto, padrao)
                if score > melhor_score:
                    melhor_intent, melhor_score = intent_def.intent, score
        return Entendimento(intent=melhor_intent, confianca=round(melhor_score, 3))

    def gerar_resposta(self, contexto: Contexto) -> str:
        intent = contexto.entendimento.intent
        if intent and intent in self._respostas:
            return self._respostas[intent]
        return RESPOSTA_FALLBACK
