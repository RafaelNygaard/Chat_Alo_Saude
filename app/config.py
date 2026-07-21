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
