"""Repositórios: ponte entre orquestrador/handoff e o PostgreSQL."""
from datetime import datetime

from sqlalchemy import text

from app.db import Session
from app.models import (
    AtendenteStatus, Conversa, FaqIntent, Handoff, Mensagem, TopicoCritico,
)
from app.nlp.rules_engine import IntentDef


def carregar_intents() -> list[IntentDef]:
    rows = Session.query(FaqIntent).filter_by(ativo=True).all()
    return [
        IntentDef(intent=r.intent, padroes=r.padroes.splitlines(), resposta=r.resposta)
        for r in rows
    ]


def carregar_topicos_criticos() -> list[str]:
    rows = Session.query(TopicoCritico).filter_by(ativo=True).all()
    return [r.termo for r in rows]


def criar_conversa(usuario_id: int, assunto: str | None) -> Conversa:
    protocolo = Session.execute(text("SELECT gerar_protocolo()")).scalar()
    conversa = Conversa(protocolo=protocolo, usuario_id=usuario_id, assunto=assunto)
    Session.add(conversa)
    Session.commit()
    return conversa


def gravar_mensagem(conversa_id: int, autor: str, texto: str,
                    confianca: float | None = None) -> Mensagem:
    msg = Mensagem(conversa_id=conversa_id, autor=autor, texto=texto,
                   confianca_nlp=confianca)
    Session.add(msg)
    Session.commit()
    return msg


class SqlHandoffRepository:
    """Implementação do HandoffRepository (Protocol) sobre o banco."""

    def atendentes_disponiveis(self) -> list[int]:
        rows = (
            Session.query(AtendenteStatus)
            .filter_by(status="disponivel")
            .order_by(AtendenteStatus.atualizado_em)
            .all()
        )
        return [r.atendente_id for r in rows]

    def enfileirar(self, conversa_id: int, gatilho: str) -> None:
        Session.add(Handoff(conversa_id=conversa_id, gatilho=gatilho))
        Session.query(Conversa).filter_by(id=conversa_id).update({"status": "fila"})
        Session.commit()

    def atribuir(self, conversa_id: int, atendente_id: int) -> None:
        Session.query(Conversa).filter_by(id=conversa_id).update(
            {"status": "humano", "atendente_id": atendente_id}
        )
        Session.query(Handoff).filter_by(conversa_id=conversa_id, resolvido_em=None).update(
            {"resolvido_em": datetime.utcnow()}
        )
        Session.query(AtendenteStatus).filter_by(atendente_id=atendente_id).update(
            {"status": "ocupado", "atualizado_em": datetime.utcnow()}
        )
        Session.commit()

    def notificar_atendente(self, atendente_id: int, conversa_id: int) -> None:
        # MVP: o painel do atendente descobre via polling/SSE; hook para push futuro.
        pass
