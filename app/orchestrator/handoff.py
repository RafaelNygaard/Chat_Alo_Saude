"""Gestor de handoff (ADR-001, Decisão B): fila de conversas + disponibilidade.

Depende de um repositório abstrato para ser testável sem banco.
"""
from dataclasses import dataclass
from typing import Protocol


class HandoffRepository(Protocol):
    def atendentes_disponiveis(self) -> list[int]: ...
    def enfileirar(self, conversa_id: int, gatilho: str) -> None: ...
    def atribuir(self, conversa_id: int, atendente_id: int) -> None: ...
    def notificar_atendente(self, atendente_id: int, conversa_id: int) -> None: ...
    def nome_atendente(self, atendente_id: int) -> str: ...


@dataclass
class ResultadoHandoff:
    atribuido: bool
    atendente_id: int | None
    mensagem_sistema: str


class HandoffManager:
    def __init__(self, repo: HandoffRepository, prazo_sem_atendente_min: int = 30):
        self._repo = repo
        self._prazo = prazo_sem_atendente_min

    def escalar(self, conversa_id: int, gatilho: str) -> ResultadoHandoff:
        """Escala a conversa: atribui a um atendente disponível ou enfileira."""
        self._repo.enfileirar(conversa_id, gatilho)
        disponiveis = self._repo.atendentes_disponiveis()
        if disponiveis:
            atendente_id = disponiveis[0]
            self._repo.atribuir(conversa_id, atendente_id)
            self._repo.notificar_atendente(atendente_id, conversa_id)
            # "disponível" como fallback caso o nome não esteja preenchido
            nome = (self._repo.nome_atendente(atendente_id) or "").strip() or "disponível"
            return ResultadoHandoff(
                atribuido=True,
                atendente_id=atendente_id,
                mensagem_sistema=f"Transferindo para o (a) atendente {nome}.",
            )
        return ResultadoHandoff(
            atribuido=False,
            atendente_id=None,
            mensagem_sistema=(
                "Nenhum atendente disponível no momento. Sua solicitação foi "
                f"registrada; prazo estimado de retorno: {self._prazo} minutos."
            ),
        )
