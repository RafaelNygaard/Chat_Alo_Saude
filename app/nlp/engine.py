"""Interface NLPEngine (ADR-001, Decisão A — 'a decisão mais importante deste ADR').

O orquestrador, o handoff, o frontend e o banco dependem apenas desta interface.
Implementações: RulesEngine (A1, ativa), futura LLMEngine (A3) ou RasaEngine (A2).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Entendimento:
    intent: str | None      # None = não reconhecido
    confianca: float        # 0.0 a 1.0


@dataclass
class Contexto:
    """Contexto passado para geração de resposta."""
    entendimento: Entendimento
    texto_usuario: str
    historico: list[str] = field(default_factory=list)


class NLPEngine(ABC):
    @abstractmethod
    def entender(self, texto: str) -> Entendimento:
        """Classifica a intenção da mensagem com grau de confiança."""

    @abstractmethod
    def gerar_resposta(self, contexto: Contexto) -> str:
        """Gera a resposta do bot para o contexto dado."""
