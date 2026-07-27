-- Migration 008 — Configuração de e-mail (SMTP) + fluxo de senha temporária
-- Pivô: a recuperação passa a enviar uma SENHA TEMPORÁRIA (troca obrigatória no
-- 1º acesso), configurada na área administrativa. O fluxo de token (migration
-- 007) é descontinuado. Idempotente.
--
--   psql -U alosaude -d alosaude -f db/migrations/008_config_email_senha_temporaria.sql

BEGIN;

-- Configuração do servidor de e-mail (linha única, id=1). A senha do SMTP é
-- guardada CIFRADA (Fernet, chave derivada de SECRET_KEY) — nunca em claro.
CREATE TABLE IF NOT EXISTS config_email (
    id             SERIAL PRIMARY KEY,
    smtp_host      TEXT NOT NULL DEFAULT '',
    smtp_port      INTEGER NOT NULL DEFAULT 587,
    smtp_email     TEXT NOT NULL DEFAULT '',
    smtp_senha_cif TEXT,                        -- senha do SMTP cifrada
    assunto        TEXT NOT NULL DEFAULT 'Recuperação de senha — Alô Saúde',
    corpo          TEXT NOT NULL DEFAULT
        E'Olá {{username}}!\n\nRecebemos um pedido para redefinir sua senha. '
        'Segue sua senha temporária: {{senha_temp}}\n\n'
        'Ela deve ser trocada no primeiro acesso.\n\nEquipe Alô Saúde.',
    atualizado_em  TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO config_email (id) SELECT 1
WHERE NOT EXISTS (SELECT 1 FROM config_email WHERE id = 1);

-- Flag de senha temporária: obriga a troca no próximo login.
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS senha_temporaria BOOLEAN NOT NULL DEFAULT FALSE;

-- Fluxo de token descontinuado.
DROP TABLE IF EXISTS tokens_recuperacao;

COMMIT;
