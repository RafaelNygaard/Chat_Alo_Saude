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
-- 2b. funcoes  (função do servidor; combo do popup, gerenciável no admin — ADR-003)
-- ---------------------------------------------------------------
CREATE TABLE funcoes (
    id    SERIAL PRIMARY KEY,
    nome  TEXT NOT NULL UNIQUE,
    ativo BOOLEAN NOT NULL DEFAULT TRUE
);

-- 'Atendente chat': ao logar, o profissional vai direto ao painel do atendente
INSERT INTO funcoes (nome) VALUES
    ('Enfermeiro(a)'), ('Técnico(a) de Enfermagem'), ('Agente Comunitário de Saúde'),
    ('Médico(a)'), ('Coordenador(a) de Unidade'), ('Farmacêutico(a)'),
    ('Cirurgião(ã)-Dentista'), ('Assistente Social'), ('Atendente chat');

-- ---------------------------------------------------------------
-- 2. usuarios  (servidores, enfermeiros, atendentes, admins)
-- CNS em campo estruturado com validação (item de ação 10)
-- email/funcao_id: identificação pelo popup; senha_hash: login (admin) — ADR-003
-- ---------------------------------------------------------------
CREATE TABLE usuarios (
    id          SERIAL PRIMARY KEY,
    nome        TEXT NOT NULL,
    email       TEXT,
    cns         CHAR(15) UNIQUE CHECK (cns ~ '^[0-9]{15}$'),
    matricula   TEXT UNIQUE,
    ubs_id      INTEGER REFERENCES ubs(id),
    funcao_id   INTEGER REFERENCES funcoes(id),
    papel       TEXT NOT NULL CHECK (papel IN ('servidor', 'enfermeiro', 'atendente', 'admin')),
    senha_hash  TEXT,
    senha_temporaria BOOLEAN NOT NULL DEFAULT FALSE,  -- obriga troca no próximo login
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
-- ultimo_encerramento_em ordena a fila round-robin: quem encerra vai para o fim
-- (NULL = ainda não atendeu, portanto vem na frente).
CREATE TABLE atendentes_status (
    atendente_id           INTEGER PRIMARY KEY REFERENCES usuarios(id),
    status                 TEXT NOT NULL DEFAULT 'ausente'
                           CHECK (status IN ('disponivel', 'ocupado', 'ausente')),
    atualizado_em          TIMESTAMPTZ NOT NULL DEFAULT now(),
    ultimo_encerramento_em TIMESTAMPTZ
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
-- 11. pesquisas_satisfacao  (CSAT ao encerrar a conversa)
-- ---------------------------------------------------------------
CREATE TABLE pesquisas_satisfacao (
    id          SERIAL PRIMARY KEY,
    conversa_id INTEGER NOT NULL UNIQUE REFERENCES conversas(id),
    nota        INTEGER NOT NULL CHECK (nota BETWEEN 1 AND 5),
    comentario  TEXT,
    criada_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------
-- 12. config_encerramento  (linha única; mensagem final configurável no admin)
-- ---------------------------------------------------------------
CREATE TABLE config_encerramento (
    id                SERIAL PRIMARY KEY,
    texto             TEXT NOT NULL,
    imagem_caminho    TEXT,
    imagem_como_fundo BOOLEAN NOT NULL DEFAULT FALSE,
    cor_fundo         TEXT NOT NULL DEFAULT '#e8f0fe',
    cor_texto         TEXT NOT NULL DEFAULT '#071d41',
    atualizado_em     TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO config_encerramento (id, texto) VALUES
    (1, 'A equipe do Alô Saúde agradece seu contato e deseja uma ótima semana!');

-- ---------------------------------------------------------------
-- 13. config_cabecalho  (linha única; logo e identidade do cabeçalho)
-- ---------------------------------------------------------------
CREATE TABLE config_cabecalho (
    id            SERIAL PRIMARY KEY,
    logo_caminho  TEXT,
    titulo        TEXT NOT NULL DEFAULT 'Alô Saúde',
    subtitulo     TEXT NOT NULL DEFAULT 'Central de Apoio à Atenção Básica',
    orgao         TEXT NOT NULL DEFAULT 'Prefeitura de Poços de Caldas - SMS',
    cor_fundo     TEXT NOT NULL DEFAULT '#0c326f',  -- azul brand gov.br
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO config_cabecalho (id, logo_caminho) VALUES
    (1, '/static/img/logo-alo-saude.png');

-- ---------------------------------------------------------------
-- 14. config_email  (linha única; SMTP + modelo de recuperação de senha)
-- A senha do SMTP é guardada CIFRADA (Fernet, chave derivada de SECRET_KEY).
-- ---------------------------------------------------------------
CREATE TABLE config_email (
    id             SERIAL PRIMARY KEY,
    smtp_host      TEXT NOT NULL DEFAULT '',
    smtp_port      INTEGER NOT NULL DEFAULT 587,
    smtp_email     TEXT NOT NULL DEFAULT '',
    smtp_senha_cif TEXT,
    assunto        TEXT NOT NULL DEFAULT 'Recuperação de senha — Alô Saúde',
    corpo          TEXT NOT NULL DEFAULT
        E'Olá {{username}}!\n\nRecebemos um pedido para redefinir sua senha. '
        'Segue sua senha temporária: {{senha_temp}}\n\n'
        'Use-a para acessar o sistema. Para definir uma senha própria, acesse '
        '"Esqueci minha senha".\n\nEquipe Alô Saúde.',
    atualizado_em  TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO config_email (id) VALUES (1);

-- ---------------------------------------------------------------
-- 15. feedback_mensagens  (Útil/Não útil por resposta do bot — gov.br DS)
-- ---------------------------------------------------------------
CREATE TABLE feedback_mensagens (
    id          SERIAL PRIMARY KEY,
    mensagem_id INTEGER NOT NULL UNIQUE REFERENCES mensagens(id),
    util        BOOLEAN NOT NULL,
    criada_em   TIMESTAMPTZ NOT NULL DEFAULT now()
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
