"""Repositórios: ponte entre orquestrador/handoff e o PostgreSQL."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, text
from werkzeug.security import generate_password_hash

from app.db import Session
from app.models import (
    AtendenteStatus, ConfigCabecalho, ConfigEncerramento, Conversa, FaqIntent,
    Funcao, Handoff, Mensagem, PesquisaSatisfacao, TokenRecuperacao,
    TopicoCritico, UBS, Usuario,
)

TEXTO_ENCERRAMENTO_PADRAO = (
    "A equipe do Alô Saúde agradece seu contato e deseja uma ótima semana!"
)

# Função cujo titular opera a fila: ao logar, vai direto ao painel do atendente.
FUNCAO_ATENDENTE_CHAT = "Atendente chat"

# Sentinela para ordenar quem nunca encerrou um atendimento no início da fila.
EPOCH = datetime(1970, 1, 1)


def liberar_atendente(atendente_id: int) -> None:
    """Encerrou um atendimento: volta a ficar disponível e vai para o FIM da fila."""
    row = Session.get(AtendenteStatus, atendente_id)
    if row is None:
        return
    agora = datetime.utcnow()
    row.ultimo_encerramento_em = agora   # manda para o fim da fila
    row.atualizado_em = agora
    if row.status == "ocupado":          # respeita quem se marcou 'ausente'
        row.status = "disponivel"
    Session.commit()


def destino_pos_login(u: Usuario) -> str | None:
    """Para onde redirecionar o profissional após o login (None = chat padrão)."""
    if u.funcao is not None and u.funcao.nome == FUNCAO_ATENDENTE_CHAT:
        return f"/atendente?atendente_id={u.id}"
    return None


def garantir_status_atendente(usuario_id: int, status: str = "disponivel") -> None:
    """Cria a linha de disponibilidade se faltar (sem sobrescrever a existente)."""
    if Session.get(AtendenteStatus, usuario_id) is None:
        Session.add(AtendenteStatus(atendente_id=usuario_id, status=status))
        Session.commit()
from app.nlp.rules_engine import IntentDef


# ------------------------------------------------------------- cabeçalho
CABECALHO_PADRAO = {
    "logo": "/static/img/logo-alo-saude.png",
    "titulo": "Alô Saúde",
    "subtitulo": "Central de Apoio à Atenção Básica",
    "orgao": "Prefeitura de Poços de Caldas - SMS",
    "cor_fundo": "#1351b4",
}


def obter_config_cabecalho() -> ConfigCabecalho:
    """Config de linha única (id=1). Cria com o padrão se ainda não existir."""
    cfg = Session.get(ConfigCabecalho, 1)
    if cfg is None:
        cfg = ConfigCabecalho(id=1, logo_caminho=CABECALHO_PADRAO["logo"])
        Session.add(cfg)
        Session.commit()
    return cfg


def config_cabecalho_json(cfg: ConfigCabecalho) -> dict:
    return {"logo": cfg.logo_caminho, "titulo": cfg.titulo,
            "subtitulo": cfg.subtitulo, "orgao": cfg.orgao,
            "cor_fundo": cfg.cor_fundo}


# --------------------------------------------- pesquisa / mensagem de encerramento
def obter_config_encerramento() -> ConfigEncerramento:
    """Config de linha única (id=1). Cria com o padrão se ainda não existir."""
    cfg = Session.get(ConfigEncerramento, 1)
    if cfg is None:
        cfg = ConfigEncerramento(id=1, texto=TEXTO_ENCERRAMENTO_PADRAO)
        Session.add(cfg)
        Session.commit()
    return cfg


def config_encerramento_json(cfg: ConfigEncerramento) -> dict:
    return {"texto": cfg.texto, "imagem": cfg.imagem_caminho,
            "imagem_como_fundo": bool(cfg.imagem_como_fundo),
            "cor_fundo": cfg.cor_fundo, "cor_texto": cfg.cor_texto}


def registrar_pesquisa(conversa_id: int, nota: int,
                       comentario: str | None) -> PesquisaSatisfacao:
    """Grava (ou atualiza) a pesquisa da conversa — uma por conversa."""
    p = Session.query(PesquisaSatisfacao).filter_by(conversa_id=conversa_id).first()
    if p is None:
        p = PesquisaSatisfacao(conversa_id=conversa_id)
        Session.add(p)
    p.nota = nota
    p.comentario = (comentario or "").strip() or None
    Session.commit()
    return p


# ------------------------------------------------------------- identificação
def listar_funcoes() -> list[dict]:
    rows = Session.query(Funcao).filter_by(ativo=True).order_by(Funcao.nome).all()
    return [{"id": f.id, "nome": f.nome} for f in rows]


def listar_ubs() -> list[dict]:
    rows = Session.query(UBS).order_by(UBS.nome).all()
    return [{"id": u.id, "nome": u.nome, "municipio": u.municipio} for u in rows]


# ------------------------------------------------------- recuperação de senha
def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _expirado(dt: datetime) -> bool:
    """Compara tratando datetime sem tzinfo como UTC (SQLite dos testes)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt < datetime.now(timezone.utc)


def usuario_por_identificador(identificador: str) -> Usuario | None:
    return (
        Session.query(Usuario)
        .filter(or_(Usuario.email == identificador, Usuario.matricula == identificador))
        .first()
    )


def criar_token_recuperacao(usuario_id: int, ttl_min: int = 60) -> str:
    """Gera um token de uso único; guarda só o hash. Invalida os anteriores."""
    Session.query(TokenRecuperacao).filter_by(usuario_id=usuario_id, usado_em=None).update(
        {"usado_em": datetime.now(timezone.utc)}
    )
    token = secrets.token_urlsafe(32)
    Session.add(TokenRecuperacao(
        usuario_id=usuario_id,
        token_hash=_hash_token(token),
        expira_em=datetime.now(timezone.utc) + timedelta(minutes=ttl_min),
    ))
    Session.commit()
    return token   # valor em claro só existe aqui e no link enviado


def token_recuperacao_valido(token: str) -> TokenRecuperacao | None:
    t = Session.query(TokenRecuperacao).filter_by(
        token_hash=_hash_token(token), usado_em=None).first()
    if t is None or _expirado(t.expira_em):
        return None
    return t


def redefinir_senha_por_token(token: str, nova_senha: str) -> bool:
    t = token_recuperacao_valido(token)
    if t is None:
        return False
    usuario = Session.get(Usuario, t.usuario_id)
    usuario.senha_hash = generate_password_hash(nova_senha)
    t.usado_em = datetime.now(timezone.utc)   # consome (uso único)
    Session.commit()
    return True


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
        """Fila round-robin dos atendentes disponíveis.

        Ordem: quem há mais tempo não encerra um atendimento vem primeiro; quem
        acabou de encerrar vai para o fim. `coalesce` põe quem nunca atendeu na
        frente (e evita depender de NULLS FIRST, que varia entre bancos).
        """
        rows = (
            Session.query(AtendenteStatus)
            .filter_by(status="disponivel")
            .order_by(
                func.coalesce(AtendenteStatus.ultimo_encerramento_em, EPOCH),
                AtendenteStatus.atendente_id,   # desempate estável
            )
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

    def nome_atendente(self, atendente_id: int) -> str:
        u = Session.get(Usuario, atendente_id)
        return u.nome if u else ""

    def notificar_atendente(self, atendente_id: int, conversa_id: int) -> None:
        # MVP: o painel do atendente descobre via polling/SSE; hook para push futuro.
        pass
