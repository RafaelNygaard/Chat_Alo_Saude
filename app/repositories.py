"""Repositórios: ponte entre orquestrador/handoff e o PostgreSQL."""
from datetime import datetime

from sqlalchemy import or_, text

from app.db import Session
from app.models import (
    AtendenteStatus, Conversa, FaqIntent, Funcao, Handoff, Mensagem,
    TopicoCritico, UBS, Usuario,
)
from app.nlp.rules_engine import IntentDef


# ------------------------------------------------------------- identificação
def listar_funcoes() -> list[dict]:
    rows = Session.query(Funcao).filter_by(ativo=True).order_by(Funcao.nome).all()
    return [{"id": f.id, "nome": f.nome} for f in rows]


def listar_ubs() -> list[dict]:
    rows = Session.query(UBS).order_by(UBS.nome).all()
    return [{"id": u.id, "nome": u.nome, "municipio": u.municipio} for u in rows]


def autenticar_servidor(identificador: str, senha: str) -> tuple[Usuario | None, str | None]:
    """Login do servidor por e-mail OU matrícula. Não cria cadastro (ADR-003).

    Retorna (usuario, None) em sucesso ou (None, erro).
    """
    from werkzeug.security import check_password_hash

    u = (
        Session.query(Usuario)
        .filter(or_(Usuario.email == identificador, Usuario.matricula == identificador))
        .first()
    )
    if u is None:
        return None, 'Cadastro não encontrado. Use "Cadastrar usuário".'
    if not u.senha_hash or not check_password_hash(u.senha_hash, senha):
        return None, "E-mail/matrícula ou senha incorretos."
    return u, None


def identificar_servidor(nome: str, email: str, matricula: str, funcao_id: int,
                         ubs_id: int, senha: str) -> tuple[Usuario | None, str | None]:
    """Cadastra (matrícula nova) ou autentica (matrícula existente) o servidor.

    - Matrícula nova: cria com a senha (hash).
    - Matrícula existente com senha definida: exige a senha correta.
    - Matrícula existente sem senha (registro legado): define a senha agora.

    Retorna (usuario, None) em sucesso ou (None, erro) em falha de autenticação.
    Não rebaixa o papel de quem já é atendente/admin.
    """
    from werkzeug.security import check_password_hash, generate_password_hash

    u = Session.query(Usuario).filter_by(matricula=matricula).first()
    novo = u is None
    if not novo and u.senha_hash:
        if not check_password_hash(u.senha_hash, senha):
            return None, "Matrícula já cadastrada e a senha está incorreta."
    if novo:
        u = Usuario(papel="servidor")
        Session.add(u)

    u.nome = nome
    u.email = email or u.email
    u.matricula = matricula or u.matricula
    u.funcao_id = funcao_id
    u.ubs_id = ubs_id
    if novo or not u.senha_hash:          # cadastra a senha na 1ª vez
        u.senha_hash = generate_password_hash(senha)
    if u.papel not in ("atendente", "admin"):
        u.papel = "servidor"
    Session.commit()
    return u, None


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
