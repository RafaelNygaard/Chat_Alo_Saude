"""Configuração centralizada. Valores de handoff são parametrizáveis (ADR-001, Decisão B)."""
import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg2://alosaude:senha@localhost:5432/alosaude"
    )

    # Gatilhos de handoff (Decisão B)
    HANDOFF_LIMIAR_CONFIANCA = float(os.environ.get("HANDOFF_LIMIAR_CONFIANCA", "0.6"))
    HANDOFF_MSGS_CONSECUTIVAS = int(os.environ.get("HANDOFF_MSGS_CONSECUTIVAS", "2"))
    HANDOFF_PRAZO_SEM_ATENDENTE_MIN = int(
        os.environ.get("HANDOFF_PRAZO_SEM_ATENDENTE_MIN", "30")
    )

    # Recuperação de senha
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:5000")
    RECUPERACAO_TTL_MIN = int(os.environ.get("RECUPERACAO_TTL_MIN", "60"))

    # SMTP (opcional). Sem SMTP_HOST, o link é registrado no log (modo dev).
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_FROM = os.environ.get("SMTP_FROM", "nao-responder@alosaude.local")
    SMTP_TLS = os.environ.get("SMTP_TLS", "1") == "1"
