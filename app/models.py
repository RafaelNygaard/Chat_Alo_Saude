"""Models SQLAlchemy espelhando db/schema.sql (fonte canônica do DDL)."""
from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer,
    Interval, Numeric, Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class UBS(Base):
    __tablename__ = "ubs"
    id = Column(Integer, primary_key=True)
    nome = Column(Text, nullable=False)
    municipio = Column(Text, nullable=False)


class Funcao(Base):
    __tablename__ = "funcoes"
    id = Column(Integer, primary_key=True)
    nome = Column(Text, nullable=False, unique=True)
    ativo = Column(Boolean, nullable=False, default=True)


class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True)
    nome = Column(Text, nullable=False)
    email = Column(Text)
    cns = Column(Text, unique=True)  # validado no DDL: ^[0-9]{15}$
    matricula = Column(Text, unique=True)
    ubs_id = Column(Integer, ForeignKey("ubs.id"))
    funcao_id = Column(Integer, ForeignKey("funcoes.id"))
    papel = Column(Text, nullable=False)  # servidor | enfermeiro | atendente | admin
    senha_hash = Column(Text)  # apenas para papéis com login (admin/atendente)
    criado_em = Column(DateTime(timezone=True), default=datetime.utcnow)

    ubs = relationship("UBS")
    funcao = relationship("Funcao")


class Conversa(Base):
    __tablename__ = "conversas"
    id = Column(Integer, primary_key=True)
    protocolo = Column(Text, nullable=False, unique=True)  # AS-AAAA-NNNNN
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    assunto = Column(Text)
    status = Column(Text, nullable=False, default="bot")  # bot|fila|humano|encerrada
    atendente_id = Column(Integer, ForeignKey("usuarios.id"))
    criada_em = Column(DateTime(timezone=True), default=datetime.utcnow)

    mensagens = relationship("Mensagem", back_populates="conversa", order_by="Mensagem.criada_em")

    # Mapeamento status -> rótulo exibido na UI (ADR: vocabulário único)
    STATUS_UI = {"bot": "Aberto", "fila": "Aguardando", "humano": "Em atendimento", "encerrada": "Encerrado"}


class Mensagem(Base):
    __tablename__ = "mensagens"
    id = Column(Integer, primary_key=True)
    conversa_id = Column(Integer, ForeignKey("conversas.id"), nullable=False)
    autor = Column(Text, nullable=False)  # usuario | bot | atendente | sistema
    texto = Column(Text, nullable=False)
    confianca_nlp = Column(Numeric(4, 3))
    criada_em = Column(DateTime(timezone=True), default=datetime.utcnow)

    conversa = relationship("Conversa", back_populates="mensagens")


class Anexo(Base):
    __tablename__ = "anexos"
    id = Column(Integer, primary_key=True)
    mensagem_id = Column(Integer, ForeignKey("mensagens.id"), nullable=False)
    nome_original = Column(Text, nullable=False)
    caminho_storage = Column(Text, nullable=False)
    mime_type = Column(Text, nullable=False)
    tamanho = Column(Integer, nullable=False)
    verificado_em = Column(DateTime(timezone=True))  # NULL = antimalware pendente


class AtendenteStatus(Base):
    __tablename__ = "atendentes_status"
    atendente_id = Column(Integer, ForeignKey("usuarios.id"), primary_key=True)
    status = Column(Text, nullable=False, default="ausente")  # disponivel|ocupado|ausente
    atualizado_em = Column(DateTime(timezone=True), default=datetime.utcnow)
    # Ordena a fila round-robin: quem encerra vai para o fim (NULL = nunca atendeu)
    ultimo_encerramento_em = Column(DateTime(timezone=True))


class FaqIntent(Base):
    __tablename__ = "faq_intents"
    id = Column(Integer, primary_key=True)
    intent = Column(Text, nullable=False, unique=True)
    padroes = Column(Text, nullable=False)  # exemplos, um por linha
    resposta = Column(Text, nullable=False)
    chip_label = Column(Text)
    ativo = Column(Boolean, nullable=False, default=True)


class Handoff(Base):
    __tablename__ = "handoffs"
    id = Column(Integer, primary_key=True)
    conversa_id = Column(Integer, ForeignKey("conversas.id"), nullable=False)
    gatilho = Column(Text, nullable=False)  # pedido_explicito|baixa_confianca|topico_critico
    tempo_espera = Column(Interval)
    criado_em = Column(DateTime(timezone=True), default=datetime.utcnow)
    resolvido_em = Column(DateTime(timezone=True))


class LogAcessoExterno(Base):
    __tablename__ = "log_acessos_externos"
    id = Column(Integer, primary_key=True)
    conversa_id = Column(Integer, ForeignKey("conversas.id"), nullable=False)
    base = Column(Text, nullable=False)  # sinan | e-sus
    operacao = Column(Text, nullable=False)
    executado_em = Column(DateTime(timezone=True), default=datetime.utcnow)


class PesquisaSatisfacao(Base):
    __tablename__ = "pesquisas_satisfacao"
    id = Column(Integer, primary_key=True)
    conversa_id = Column(Integer, ForeignKey("conversas.id"), nullable=False, unique=True)
    nota = Column(Integer, nullable=False)  # 1..5 (validado no DDL)
    comentario = Column(Text)
    criada_em = Column(DateTime(timezone=True), default=datetime.utcnow)


class ConfigEncerramento(Base):
    """Linha única (id=1): mensagem final configurável pelo admin."""
    __tablename__ = "config_encerramento"
    id = Column(Integer, primary_key=True)
    texto = Column(Text, nullable=False)
    imagem_caminho = Column(Text)
    imagem_como_fundo = Column(Boolean, nullable=False, default=False)
    cor_fundo = Column(Text, nullable=False, default="#e8f0fe")
    cor_texto = Column(Text, nullable=False, default="#071d41")
    atualizado_em = Column(DateTime(timezone=True), default=datetime.utcnow)


class ConfigCabecalho(Base):
    """Linha única (id=1): logo e identidade do cabeçalho, editáveis no admin."""
    __tablename__ = "config_cabecalho"
    id = Column(Integer, primary_key=True)
    logo_caminho = Column(Text)
    titulo = Column(Text, nullable=False, default="Alô Saúde")
    subtitulo = Column(Text, nullable=False, default="Central de Apoio à Atenção Básica")
    orgao = Column(Text, nullable=False, default="Prefeitura de Poços de Caldas - SMS")
    cor_fundo = Column(Text, nullable=False, default="#1351b4")
    atualizado_em = Column(DateTime(timezone=True), default=datetime.utcnow)


class TokenRecuperacao(Base):
    """Token de recuperação de senha. Guardado como hash; uso único e com prazo."""
    __tablename__ = "tokens_recuperacao"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    token_hash = Column(Text, nullable=False, unique=True)
    expira_em = Column(DateTime(timezone=True), nullable=False)
    usado_em = Column(DateTime(timezone=True))
    criado_em = Column(DateTime(timezone=True), default=datetime.utcnow)


class TopicoCritico(Base):
    __tablename__ = "topicos_criticos"
    id = Column(Integer, primary_key=True)
    termo = Column(Text, nullable=False, unique=True)
    ativo = Column(Boolean, nullable=False, default=True)
