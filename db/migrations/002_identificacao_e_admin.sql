-- Migration 002 — Identificação do servidor + área administrativa
-- ADR-003. Idempotente. Aplicar após schema.sql (migration 001 = schema base).
--
--   psql -U alosaude -d alosaude -f db/migrations/002_identificacao_e_admin.sql

BEGIN;

-- Tabela de funções (combo do popup; gerenciável na área admin)
CREATE TABLE IF NOT EXISTS funcoes (
    id    SERIAL PRIMARY KEY,
    nome  TEXT NOT NULL UNIQUE,
    ativo BOOLEAN NOT NULL DEFAULT TRUE
);

INSERT INTO funcoes (nome) VALUES
    ('Enfermeiro(a)'),
    ('Técnico(a) de Enfermagem'),
    ('Agente Comunitário de Saúde'),
    ('Médico(a)'),
    ('Coordenador(a) de Unidade'),
    ('Farmacêutico(a)'),
    ('Cirurgião(ã)-Dentista'),
    ('Assistente Social')
ON CONFLICT (nome) DO NOTHING;

-- usuarios: dados de identificação (email/função) e credencial de login (senha_hash)
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email      TEXT;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS funcao_id  INTEGER REFERENCES funcoes(id);
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS senha_hash TEXT;

-- papel passa a aceitar 'servidor' (quem solicita atendimento pelo popup, sem login)
ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS usuarios_papel_check;
ALTER TABLE usuarios ADD CONSTRAINT usuarios_papel_check
    CHECK (papel IN ('servidor', 'enfermeiro', 'atendente', 'admin'));

COMMIT;
