-- Migration 009 — Feedback "Útil / Não útil" por mensagem do bot (gov.br DS)
-- Idempotente.
--
--   psql -U alosaude -d alosaude -f db/migrations/009_feedback_mensagens.sql

BEGIN;

CREATE TABLE IF NOT EXISTS feedback_mensagens (
    id          SERIAL PRIMARY KEY,
    mensagem_id INTEGER NOT NULL UNIQUE REFERENCES mensagens(id),
    util        BOOLEAN NOT NULL,
    criada_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
