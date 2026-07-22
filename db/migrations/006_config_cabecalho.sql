-- Migration 006 — Cabeçalho configurável (logo e identidade visual)
-- Linha única (id=1), editável na área administrativa. Idempotente.
--
--   psql -U alosaude -d alosaude -f db/migrations/006_config_cabecalho.sql

BEGIN;

CREATE TABLE IF NOT EXISTS config_cabecalho (
    id            SERIAL PRIMARY KEY,
    logo_caminho  TEXT,
    titulo        TEXT NOT NULL DEFAULT 'Alô Saúde',
    subtitulo     TEXT NOT NULL DEFAULT 'Central de Apoio à Atenção Básica',
    orgao         TEXT NOT NULL DEFAULT 'Prefeitura de Poços de Caldas - SMS',
    cor_fundo     TEXT NOT NULL DEFAULT '#1351b4',
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO config_cabecalho (id, logo_caminho)
SELECT 1, '/static/img/logo-alo-saude.png'
WHERE NOT EXISTS (SELECT 1 FROM config_cabecalho WHERE id = 1);

COMMIT;
