-- Migration 003 — Pesquisa de satisfação + mensagem de encerramento configurável
-- Idempotente. Aplicar após schema.sql / migration 002.
--
--   psql -U alosaude -d alosaude -f db/migrations/003_pesquisa_e_encerramento.sql

BEGIN;

-- Pesquisa de satisfação: uma por conversa (CSAT 1-5 + comentário opcional)
CREATE TABLE IF NOT EXISTS pesquisas_satisfacao (
    id          SERIAL PRIMARY KEY,
    conversa_id INTEGER NOT NULL UNIQUE REFERENCES conversas(id),
    nota        INTEGER NOT NULL CHECK (nota BETWEEN 1 AND 5),
    comentario  TEXT,
    criada_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Mensagem de encerramento (linha única, id=1), configurável pelo admin.
-- Texto aceita emojis (UTF-8); imagem opcional; cores/background personalizáveis.
CREATE TABLE IF NOT EXISTS config_encerramento (
    id                SERIAL PRIMARY KEY,
    texto             TEXT NOT NULL,
    imagem_caminho    TEXT,
    imagem_como_fundo BOOLEAN NOT NULL DEFAULT FALSE,
    cor_fundo         TEXT NOT NULL DEFAULT '#e8f0fe',
    cor_texto         TEXT NOT NULL DEFAULT '#071d41',
    atualizado_em     TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO config_encerramento (id, texto)
SELECT 1, 'A equipe do Alô Saúde agradece seu contato e deseja uma ótima semana!'
WHERE NOT EXISTS (SELECT 1 FROM config_encerramento WHERE id = 1);

COMMIT;
