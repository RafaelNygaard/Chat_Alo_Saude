# Changelog

Registro cronológico de mudanças (mais recente primeiro). Formato inspirado em
[Keep a Changelog](https://keepachangelog.com/pt-BR/). Cada entrada referencia os
arquivos afetados. Datas em `AAAA-MM-DD`.

---

## 2026-07-21 (8) — Acesso pela rede (bind configurável)

- `run.py`: host/porta/debug via ambiente (`HOST`, `PORT`, `DEBUG`), default
  seguro `127.0.0.1`. `.env` define `HOST=0.0.0.0` — sistema acessível pela rede
  em `http://10.0.0.212:5000`. `.env.example` documenta as variáveis.
- `DEBUG=0` no `.env` exposto (o debugger do Werkzeug permitiria execução de
  código); reloader fica para dev local (`HOST=127.0.0.1`, `DEBUG=1`).
- Verificado: escuta em `0.0.0.0:5000`, acessível por IP e por localhost. A
  interface Ethernet (10.0.0.212) é rede **Private** com firewall desabilitado —
  máquinas da LAN alcançam sem regra adicional.

---

## 2026-07-21 (7) — Área administrativa + autenticação (ADR-003, parte 2)

- **Autenticação** ([ADR-003](../ADR-003-identificacao-e-admin.md)): `app/auth.py`
  (decorators `login_required`/`admin_required`), `app/api/auth.py`
  (`/api/login`, `/api/logout`, `/api/sessao`) via sessão Flask + hash Werkzeug;
  `manage.py create-admin`/`set-senha`; página `/login`.
- **Console administrativo** (`/admin`, protegido): `app/api/admin.py` +
  `templates/admin.html` + `static/js/admin.js`. Módulos: cadastros (funções,
  UBS, usuários), relatórios (por status/unidade/função + handoffs, **CSV**),
  gestão do bot (intents e tópicos críticos) e disponibilidade de atendentes.
- **Testes**: `tests/test_admin_auth.py` (identificação find-or-create, login,
  proteção admin) em SQLite in-memory — 33 testes no total, CI verde.
- Validado no navegador: login, relatórios agregados, cadastros; API admin
  retorna 401 sem sessão e `/admin` redireciona para `/login`.
- Correção: agregações por unidade/função ancoradas em `Conversa`
  (`select_from`) — evitava `conversas` fora do FROM.
- Docs: [guia-admin.md](guia-admin.md) adicionado.

---

## 2026-07-21 (6) — Popup de identificação do servidor (ADR-003, parte 1)

- **Schema** (migration `db/migrations/002_identificacao_e_admin.sql` + `schema.sql`
  + `models.py`): tabela `funcoes` (8 seeds), `usuarios` ganha `email`,
  `funcao_id`, `senha_hash`; `papel` passa a aceitar `servidor`. Aplicado no banco.
- **Backend**: `app/api/servidores.py` — `GET /api/funcoes`, `GET /api/ubs`,
  `POST /api/servidores/identificar` (find-or-create por matrícula); repositórios
  correspondentes.
- **Frontend**: modal de identificação (Nome, e-mail, matrícula + combos Função e
  Unidade + assunto) substitui o `prompt` do "Novo Atendimento"; identidade
  persistida em `localStorage` e exibida no cabeçalho. Estilos do modal em
  `estilo.css`.
- Validado no navegador ponta a ponta (servidor criado com papel `servidor`,
  função e unidade vinculadas; atendimento AS-2026-00003 aberto).

---

## 2026-07-21 (5) — Publicação no GitHub e CI

- Repositório publicado em <https://github.com/RafaelNygaard/Chat_Alo_Saude>
  (remote `origin`, branch `main`).
- **CI (GitHub Actions)** `.github/workflows/ci.yml`: roda `pytest` a cada push
  e pull request na `main` (Python 3.12; testes usam SQLite in-memory, sem
  Postgres). 23 testes validados localmente antes de publicar.
- Badge de status do CI adicionado ao `README.md`.

---

## 2026-07-21 (4) — Versionamento (git) e consistência de dependências

- Repositório git inicializado (branch `main`, commit inicial). `.gitignore`
  protege `.env` e `dataset/` (PII) — confirmado fora do controle de versão.
- `requirements.txt`: `psycopg2-binary` `2.9.9 → 2.9.12` (2.9.9 não tem wheel
  para Python 3.14); `Werkzeug==3.1.8` fixado (versão puxada pelo Flask 2.3.3 e
  validada em runtime).
- `.gitattributes` adicionado: normaliza fim de linha para LF e marca binários,
  eliminando os avisos CRLF↔LF no Windows.

---

## 2026-07-21 (3) — ADR-002: evolução do motor de NLP

- Criado [ADR-002](../ADR-002-evolucao-motor-nlp.md), que refina a Decisão A do
  ADR-001 com a evidência do harness: A1 generaliza mal → **A3 (LLM) priorizado**
  (com A1 como roteador seguro interino; A2/Rasa como fallback), condicionado à
  anonimização (item 4) e ao jurídico (itens 1–2). Inclui critérios de aceitação
  medidos pelo mesmo harness.
- Ponteiro adicionado na Decisão A do ADR-001; ADR-002 indexado em `docs/README.md`.

---

## 2026-07-21 (2) — Avaliação held-out realista do motor A1

- `eval/casos.py` ampliado para **46 casos** (34 in-scope *held-out* com
  vocabulário distinto dos padrões + 12 negativos, incluindo ruído de
  coordenação interna do grupo).
- `eval/run_eval.py`: adicionado **relatório de ponto de operação** no limiar de
  produção (resposta certa / errada / handoff; falsos positivos) e correção de
  encoding para console Windows (UTF-8 + marcadores ASCII).
- **Resultado honesto:** acurácia top-1 cai de 100% (autoria) para **64,7%**
  (held-out); confianças comprimidas em 0,09–0,35. No limiar 0,30 o bot responde
  ~9% e escala ~91% (0 erros). Evidência de que o A1 generaliza mal → embasa a
  evolução para A2/A3. Análise completa em
  [treinamento-motor-nlp.md](treinamento-motor-nlp.md).
- Justificativa do `HANDOFF_LIMIAR_CONFIANCA` no `.env` corrigida (a anterior,
  baseada no conjunto de autoria, era otimista).

---

## 2026-07-21 — Treino do motor A1 + ambiente local de desenvolvimento

### Infraestrutura
- **PostgreSQL 17** instalado localmente via `winget` (não havia Postgres nem
  Docker na máquina). Serviço `postgresql-x64-17` na porta 5432.
- Criados role e banco `alosaude`; schema aplicado; usuários seed inseridos
  (enfermeiro `id=1`, atendente `id=2`). Passo a passo em
  [runbook-ambiente-local.md](runbook-ambiente-local.md).

### NLP — "treinamento" do motor de regras (A1)
- **Novos intents** derivados do corpus real de WhatsApp, **de-identificados**
  (sem PII). Arquivo `db/seed_intents.sql` (upsert idempotente sobre
  `faq_intents`, total de 14 intents). Intents adicionados:
  `localizar_esf_por_endereco`, `lotacao_paciente`, `especialista_atende_sus`,
  `agendamento_especialista`, `sala_vacina_campanha`,
  `aplicacao_medicamento_psf`, `pedido_exame`, `visita_medica_domiciliar`;
  `notificacao_compulsoria` ampliado com o fluxo VEPI.
- **Harness de avaliação** `eval/run_eval.py` + conjunto rotulado
  `eval/casos.py`: mede acurácia top-1 e faz *sweep* do limiar de confiança.
  Detalhes e resultados em [treinamento-motor-nlp.md](treinamento-motor-nlp.md).

### Configuração / correções
- `run.py`: passou a chamar `load_dotenv()` — o `.env` não era carregado antes
  (bug latente; a config só lia `os.environ`).
- `app/db.py`: `init_db` agora tolera banco/driver indisponível na inicialização
  (loga aviso em vez de derrubar o boot) — permite ver as telas sem Postgres.
- `.env` criado com `HANDOFF_LIMIAR_CONFIANCA=0.30` (reduzido de `0.60`
  conforme o *sweep* do harness — em 0.60 a cobertura caía para 63%).
- `.claude/launch.json` adicionado para subir o servidor de desenvolvimento.

### Pendências conhecidas / dívida
- Role `alosaude` recebeu **SUPERUSER** apenas para `CREATE EXTENSION` no dev
  local; **rever para produção** (privilégio mínimo).
- Acurácia de 100% no harness é otimista (frases de teste espelham os padrões);
  falta conjunto *held-out* e mais casos negativos.
- Corpus WhatsApp permanece **bloqueado** para uso além de padrões
  de-identificados até os itens 1, 2 e 4 do ADR-001 (jurídico/DPO/anonimização).

---

## Baseline — Fundação do MVP (ADR-001, itens de ação 3, 6 e 7)

Estado do repositório antes desta sessão (documentado retroativamente ao adotar
docs as code). Implementação inicial conforme [ADR-001](../ADR-001-chatbot-alo-saude.md):

- **App factory Flask** (`app/__init__.py`, `app/config.py`) e sessão SQLAlchemy
  (`app/db.py`).
- **Schema PostgreSQL** (`db/schema.sql`): 10 tabelas do ADR + `topicos_criticos`,
  extensões `pg_trgm`/`unaccent`, função `gerar_protocolo()` e seeds iniciais de
  intents (derivados do mockup).
- **Camada NLP plugável** (Decisão A): interface `NLPEngine` (`app/nlp/engine.py`),
  implementação `RulesEngine` A1 com similaridade por trigramas
  (`app/nlp/rules_engine.py`) e normalização (`app/nlp/preprocess.py`).
- **Orquestrador + handoff** (Decisão B): `app/orchestrator/` com gatilhos de
  escalonamento (pedido explícito, baixa confiança, tópico crítico).
- **API** (`app/api/chat.py`, `app/api/atendente.py`) com stream SSE (Decisão C).
- **Frontend** (mesma stack HTML/CSS/JS): telas de chat e painel do atendente,
  identidade gov.br, VLibras.
- **Testes** sem banco (fakes) em `tests/`.
