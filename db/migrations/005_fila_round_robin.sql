-- Migration 005 — Fila de atendentes com distribuição balanceada (round-robin)
--
-- Quem encerra um atendimento vai para o FIM da fila: guardamos o instante do
-- último encerramento e ordenamos por ele (quem nunca encerrou vem primeiro).
-- Idempotente.
--
--   psql -U alosaude -d alosaude -f db/migrations/005_fila_round_robin.sql

BEGIN;

ALTER TABLE atendentes_status
    ADD COLUMN IF NOT EXISTS ultimo_encerramento_em TIMESTAMPTZ;

COMMENT ON COLUMN atendentes_status.ultimo_encerramento_em IS
    'Instante do último atendimento encerrado; ordena a fila (NULL = nunca atendeu, vai na frente).';

COMMIT;
