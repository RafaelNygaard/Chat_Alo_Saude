-- Migration 004 — Função "Atendente chat"
-- Profissionais com esta função são direcionados ao painel do atendente ao logar.
-- Idempotente.
--
--   psql -U alosaude -d alosaude -f db/migrations/004_funcao_atendente_chat.sql

BEGIN;

INSERT INTO funcoes (nome) VALUES ('Atendente chat')
ON CONFLICT (nome) DO NOTHING;

COMMIT;
