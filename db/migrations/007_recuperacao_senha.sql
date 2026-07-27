-- Migration 007 — Recuperação de senha (tokens)
-- O token é guardado como HASH (sha256); o valor em claro só existe no link
-- enviado ao usuário. Idempotente.
--
--   psql -U alosaude -d alosaude -f db/migrations/007_recuperacao_senha.sql

BEGIN;

CREATE TABLE IF NOT EXISTS tokens_recuperacao (
    id          SERIAL PRIMARY KEY,
    usuario_id  INTEGER NOT NULL REFERENCES usuarios(id),
    token_hash  TEXT NOT NULL UNIQUE,     -- sha256 do token; nunca o token em claro
    expira_em   TIMESTAMPTZ NOT NULL,
    usado_em    TIMESTAMPTZ,              -- NULL = ainda válido (uso único)
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tokens_recuperacao_usuario
    ON tokens_recuperacao (usuario_id);

COMMIT;
