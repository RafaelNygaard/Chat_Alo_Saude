"""Orquestrador de conversa (ADR-001): coração do sistema, independente do motor NLP.

Fluxo por mensagem:
  1. Se a conversa já está com humano, apenas repassa (não chama NLP).
  2. Chama NLPEngine.entender().
  3. Avalia gatilhos de handoff (Decisão B):
     a. pedido explícito (intent 'falar_com_atendente')
     b. tópico crítico (palavras-chave vindas de tabela, não de código)
     c. confiança < limiar em N mensagens consecutivas
  4. Sem gatilho: bot responde via NLPEngine.gerar_resposta().
  5. Com gatilho: escala via HandoffManager e grava divisor de sistema.
"""
from dataclasses import dataclass, field

from app.nlp.engine import Contexto, NLPEngine
from app.nlp.preprocess import normalizar
from app.orchestrator.handoff import HandoffManager

INTENT_PEDIDO_EXPLICITO = "falar_com_atendente"


@dataclass
class EstadoConversa:
    """Estado mínimo que o orquestrador precisa (carregado do banco em produção)."""
    conversa_id: int
    status: str = "bot"                       # bot | fila | humano | encerrada
    baixa_confianca_consecutivas: int = 0


@dataclass
class Resposta:
    autor: str                                # 'bot' | 'sistema'
    texto: str
    confianca: float | None = None
    handoff: bool = False
    gatilho: str | None = None
    mensagens_extra: list["Resposta"] = field(default_factory=list)


class Orquestrador:
    def __init__(
        self,
        nlp: NLPEngine,
        handoff: HandoffManager,
        topicos_criticos: list[str],
        limiar_confianca: float = 0.6,
        msgs_consecutivas: int = 2,
    ):
        self._nlp = nlp
        self._handoff = handoff
        self._topicos = [normalizar(t) for t in topicos_criticos]
        self._limiar = limiar_confianca
        self._n_consecutivas = msgs_consecutivas

    def processar(self, estado: EstadoConversa, texto: str) -> Resposta:
        if estado.status in ("humano", "fila"):
            # Conversa já escalada: orquestrador não interfere.
            return Resposta(autor="sistema", texto="", handoff=False)

        entendimento = self._nlp.entender(texto)

        gatilho = self._avaliar_gatilhos(estado, texto, entendimento.intent,
                                         entendimento.confianca)
        if gatilho:
            return self._escalar(estado, gatilho, entendimento.confianca)

        resposta = self._nlp.gerar_resposta(
            Contexto(entendimento=entendimento, texto_usuario=texto)
        )
        return Resposta(autor="bot", texto=resposta, confianca=entendimento.confianca)

    # ------------------------------------------------------------------

    def _avaliar_gatilhos(self, estado: EstadoConversa, texto: str,
                          intent: str | None, confianca: float) -> str | None:
        if intent == INTENT_PEDIDO_EXPLICITO and confianca >= self._limiar:
            return "pedido_explicito"

        texto_norm = normalizar(texto)
        if any(topico in texto_norm for topico in self._topicos):
            return "topico_critico"

        if confianca < self._limiar:
            estado.baixa_confianca_consecutivas += 1
            if estado.baixa_confianca_consecutivas >= self._n_consecutivas:
                return "baixa_confianca"
        else:
            estado.baixa_confianca_consecutivas = 0

        return None

    def _escalar(self, estado: EstadoConversa, gatilho: str,
                 confianca: float) -> Resposta:
        resultado = self._handoff.escalar(estado.conversa_id, gatilho)
        estado.status = "humano" if resultado.atribuido else "fila"
        estado.baixa_confianca_consecutivas = 0
        # Divisor de sistema: gravado como mensagens.autor = 'sistema' (auditável)
        return Resposta(
            autor="sistema",
            texto=resultado.mensagem_sistema,
            confianca=confianca,
            handoff=True,
            gatilho=gatilho,
        )
