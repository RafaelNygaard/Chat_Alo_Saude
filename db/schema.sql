-- ADR-001 — Chatbot UBS <-> Alô Saúde
-- DDL das 9 tabelas (item de ação 6) + extensão pg_trgm
-- PostgreSQL 14+

BEGIN;

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- ---------------------------------------------------------------
-- 1. ubs
-- ---------------------------------------------------------------
CREATE TABLE ubs (
    id          SERIAL PRIMARY KEY,
    nome        TEXT NOT NULL,
    municipio   TEXT NOT NULL
);

-- ---------------------------------------------------------------
-- 2. usuarios  (enfermeiros, atendentes, admins)
-- CNS em campo estruturado com validação (item de ação 10)
-- ---------------------------------------------------------------
CREATE TABLE usuarios (
    id          SERIAL PRIMARY KEY,
    nome        TEXT NOT NULL,
    cns         CHAR(15) UNIQUE CHECK (cns ~ '^[0-9]{15}$'),
    matricula   TEXT UNIQUE,
    ubs_id      INTEGER REFERENCES ubs(id),
    papel       TEXT NOT NULL CHECK (papel IN ('enfermeiro', 'atendente', 'admin')),
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------
-- 3. conversas
-- protocolo AS-AAAA-NNNNN gerado por sequence anual (ver função abaixo)
-- status: vocabulário único backend/UI (ver ADR, "Mapeamento de status")
-- ---------------------------------------------------------------
CREATE SEQUENCE protocolo_seq;

CREATE TABLE conversas (
    id           SERIAL PRIMARY KEY,
    protocolo    TEXT NOT NULL UNIQUE,
    usuario_id   INTEGER NOT NULL REFERENCES usuarios(id),
    assunto      TEXT,
    status       TEXT NOT NULL DEFAULT 'bot'
                 CHECK (status IN ('bot', 'fila', 'humano', 'encerrada')),
    atendente_id INTEGER REFERENCES usuarios(id),
    criada_em    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION gerar_protocolo() RETURNS TEXT AS $$
    SELECT 'AS-' || to_char(now(), 'YYYY') || '-'
           || lpad(nextval('protocolo_seq')::text, 5, '0');
$$ LANGUAGE sql;

-- ---------------------------------------------------------------
-- 4. mensagens
-- autor 'sistema' grava o divisor de handoff (auditável no histórico)
-- confianca_nlp permite auditar decisões do bot
-- ---------------------------------------------------------------
CREATE TABLE mensagens (
    id            SERIAL PRIMARY KEY,
    conversa_id   INTEGER NOT NULL REFERENCES conversas(id),
    autor         TEXT NOT NULL CHECK (autor IN ('usuario', 'bot', 'atendente', 'sistema')),
    texto         TEXT NOT NULL,
    confianca_nlp NUMERIC(4,3) CHECK (confianca_nlp BETWEEN 0 AND 1),
    criada_em     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_mensagens_conversa ON mensagens (conversa_id, criada_em);

-- ---------------------------------------------------------------
-- 5. anexos  (Decisão F: arquivo fora do banco, caminho aqui)
-- ---------------------------------------------------------------
CREATE TABLE anexos (
    id              SERIAL PRIMARY KEY,
    mensagem_id     INTEGER NOT NULL REFERENCES mensagens(id),
    nome_original   TEXT NOT NULL,
    caminho_storage TEXT NOT NULL,
    mime_type       TEXT NOT NULL CHECK (mime_type IN
                    ('application/pdf', 'image/jpeg', 'image/png')),
    tamanho         INTEGER NOT NULL CHECK (tamanho <= 10 * 1024 * 1024),
    verificado_em   TIMESTAMPTZ  -- NULL = antimalware pendente; não liberar ao atendente
);

-- ---------------------------------------------------------------
-- 6. atendentes_status
-- ---------------------------------------------------------------
CREATE TABLE atendentes_status (
    atendente_id  INTEGER PRIMARY KEY REFERENCES usuarios(id),
    status        TEXT NOT NULL DEFAULT 'ausente'
                  CHECK (status IN ('disponivel', 'ocupado', 'ausente')),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------
-- 7. faq_intents  (base do motor A1; chips de ação rápida no chat)
-- ---------------------------------------------------------------
CREATE TABLE faq_intents (
    id         SERIAL PRIMARY KEY,
    intent     TEXT NOT NULL UNIQUE,
    padroes    TEXT NOT NULL,   -- exemplos de frases, um por linha
    resposta   TEXT NOT NULL,
    chip_label TEXT,            -- se preenchido, vira chip de ação rápida na UI
    ativo      BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_faq_padroes_trgm ON faq_intents USING gin (padroes gin_trgm_ops);

-- ---------------------------------------------------------------
-- 8. handoffs  (auditoria da Decisão B)
-- ---------------------------------------------------------------
CREATE TABLE handoffs (
    id           SERIAL PRIMARY KEY,
    conversa_id  INTEGER NOT NULL REFERENCES conversas(id),
    gatilho      TEXT NOT NULL CHECK (gatilho IN
                 ('pedido_explicito', 'baixa_confianca', 'topico_critico')),
    tempo_espera INTERVAL,
    criado_em    TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolvido_em TIMESTAMPTZ
);

-- ---------------------------------------------------------------
-- 9. log_acessos_externos  (Decisão E; LGPD art. 37)
-- ---------------------------------------------------------------
CREATE TABLE log_acessos_externos (
    id           SERIAL PRIMARY KEY,
    conversa_id  INTEGER NOT NULL REFERENCES conversas(id),
    base         TEXT NOT NULL CHECK (base IN ('sinan', 'e-sus')),
    operacao     TEXT NOT NULL,
    executado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------
-- Palavras-chave de tópicos críticos (Decisão B: em tabela, não em código)
-- ---------------------------------------------------------------
CREATE TABLE topicos_criticos (
    id      SERIAL PRIMARY KEY,
    termo   TEXT NOT NULL UNIQUE,
    ativo   BOOLEAN NOT NULL DEFAULT TRUE
);

INSERT INTO topicos_criticos (termo) VALUES
    ('urgente'), ('urgencia'), ('emergencia'), ('grave'),
    ('obito'), ('surto'), ('notificacao compulsoria');

-- ---------------------------------------------------------------
-- Seeds de intents iniciais (derivados do mockup; expandir com corpus WhatsApp)
-- ---------------------------------------------------------------
INSERT INTO faq_intents (intent, padroes, resposta, chip_label) VALUES
(
  'falar_com_atendente',
  E'quero falar com atendente\nfalar com humano\ntransferir para agente\npreciso de um atendente',
  'Certo, vou transferir você para um atendente humano.',
  NULL
),
(
  'encaminhamento_urgente',
  E'encaminhamento urgente\npreciso encaminhar paciente com urgencia\ncomo faço encaminhamento urgente',
  'Para encaminhamento urgente, informe o CNS do paciente e descreva brevemente o quadro clínico. Se for suspeita de agravo de notificação, use também o chip "Notificação compulsória".',
  'Encaminhamento urgente'
),
(
  'notificacao_compulsoria',
  E'notificacao compulsoria\nprazo para notificar dengue\ncomo notificar no sinan',
  'Doenças de notificação compulsória devem ser registradas no SINAN. O prazo padrão é de 24h para agravos imediatos e 7 dias para os demais. Precisa de ajuda com um agravo específico?',
  'Notificação compulsória'
),
(
  'solicitacao_insumos',
  E'solicitar vacinas\nabastecimento de insumos\npedido de material\nfalta de vacina influenza',
  'Solicitações de abastecimento são registradas com protocolo e encaminhadas à central. Informe o insumo e a quantidade necessária.',
  'Solicitação de insumos'
),
(
  'suporte_esus',
  E'acesso bloqueado e-sus\nnao consigo entrar no e-sus\nproblema no e-sus',
  'Para problemas de acesso ao e-SUS, informe sua matrícula e a mensagem de erro exibida. Vou registrar o chamado de suporte.',
  NULL
),
(
  'horario_atendimento',
  E'qual o horario de atendimento\nate que horas funciona o alo saude',
  'O Alô Saúde atende em dias úteis, das 7h às 19h. Fora desse horário, o assistente virtual registra sua solicitação para retorno no próximo expediente.',
  NULL
);

COMMIT;
