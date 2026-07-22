# Changelog

Registro cronológico de mudanças (mais recente primeiro). Formato inspirado em
[Keep a Changelog](https://keepachangelog.com/pt-BR/). Cada entrada referencia os
arquivos afetados. Datas em `AAAA-MM-DD`.

---

## 2026-07-22 (16) — Correção: mensagens repetindo em ciclo no chat

**Sintoma:** mensagens do usuário, do bot, o divisor de transferência e o
"Atendimento encerrado" reapareciam repetidamente a cada ~25 s.

**Causa raiz:** a URL do `EventSource` é montada **uma única vez**
(`assinarStream`, `comum.js`) com o `after` daquele instante. O servidor encerra
o ciclo do stream a cada ~25 s e o navegador **reconecta sozinho na mesma URL** —
com o `after` congelado. A cada reconexão, tudo que havia chegado desde a
abertura da conversa era reenviado.

**Correção (três camadas):**
1. `comum.js`: ao receber `fim_ciclo`, o cliente **fecha e reassina** com o
   `after` atualizado, em vez de deixar o navegador reconectar com a URL antiga.
2. `comum.js`: conjunto `vistos` **descarta ids repetidos** — rede caindo ou
   reconexão inesperada não duplica nada na tela.
3. `chat.py`: o stream passa a emitir `id: <msg_id>` e a honrar o cabeçalho
   `Last-Event-ID`, o mecanismo padrão de retomada do SSE.

Vale para chat e painel do atendente (ambos usam `assinarStream`).

**Sobre o encerramento:** os testes confirmam que o servidor **nunca** gravou
"Atendimento encerrado" em duplicidade (`_encerrar` já era idempotente) — a
repetição era só de exibição, pelo replay do stream.

- Testes: `tests/test_stream_sse.py` (5 casos: entrega com `id:`, sem reenvio,
  `Last-Event-ID` na reconexão, encerrar 2× e pesquisa após encerrar) — **74 no
  total**.
- Verificado no navegador: contagem de mensagens **constante (3, 3, 3)** em
  t=0/30s/60s, atravessando dois ciclos; após encerrar, "Atendimento encerrado"
  e cartão de despedida permanecem **1×** mesmo após novo ciclo.

---

## 2026-07-22 (15) — Fila de atendentes com distribuição balanceada (round-robin)

- **Bug corrigido (bloqueante):** `atribuir()` marcava o atendente como `ocupado`
  e **nada revertia** — cada atendente atendia uma conversa e ficava ocupado para
  sempre, drenando o pool. Agora `_encerrar()` chama
  `repositories.liberar_atendente()`, que devolve ao status `disponivel`.
- **Round-robin** (migration `005`): nova coluna
  `atendentes_status.ultimo_encerramento_em`. Quem encerra vai para o **fim da
  fila**; quem nunca atendeu vem primeiro (`coalesce` com epoch, sem depender de
  `NULLS FIRST`). Desempate estável por `atendente_id`.
- `liberar_atendente` **respeita quem se marcou `ausente`** — só reativa quem
  estava `ocupado`, para não puxar de volta alguém fora do expediente.
- Vale para os dois caminhos de encerramento (com e sem pesquisa de satisfação).
- Testes: `tests/test_fila_atendentes.py` (8 casos, incluindo rodízio de 6
  atendimentos entre 3 atendentes) — **69 no total**.
- Verificado no sistema real: 8 solicitações entre 4 atendentes → **2 para cada**,
  em ordem cíclica.

---

## 2026-07-21 (14) — Função "Atendente chat" entra direto no painel

- Nova função **"Atendente chat"** (migration `004` + seed do `schema.sql`).
  Quem tem essa função é redirecionado ao **painel do atendente** ao fazer login
  (ou logo após se cadastrar), em vez de ir para o chat.
- Regra fica no backend: `repositories.destino_pos_login()` devolve
  `redirecionar` em `/api/servidores/login` e `/api/servidores/identificar`; o
  frontend só obedece. Também garante a linha em `atendentes_status`
  (`garantir_status_atendente`), senão o profissional não receberia da fila.
- **Correções encontradas na verificação:**
  - O painel exibia `"Matrícula <id>"` (era o ID, não a matrícula). Agora mostra
    **nome · matrícula** reais, via novo `GET /api/atendente/<id>/status`.
  - O seletor de disponibilidade sempre abria em "ausente", **divergindo do
    banco** — o atendente se achava fora e mesmo assim recebia da fila. Agora
    carrega o status real.
  - Login administrativo mandava papel `atendente` para `/admin` (403); agora
    roteia por papel: admin → `/admin`, atendente → `/atendente`.
- Testes: 4 novos (redirecionamento no login e no cadastro, disponibilidade
  criada, outras funções sem redirect) — **61 no total**.

---

## 2026-07-21 (13) — Divisor de handoff nomeia o atendente

- `"Transferido para atendente humano"` → **`"Transferindo para o (a) atendente
  <nome>."`**, com o nome do atendente que recebeu a conversa.
- `HandoffRepository` ganhou `nome_atendente(atendente_id)`; implementado em
  `SqlHandoffRepository` e no fake dos testes. Fallback para
  *"...atendente disponível."* se o nome estiver vazio.
- Não altera o divisor de `POST /conversas/<id>/assumir`
  (*"Transferido para Agente X — hh:mm"*), que é o formato exigido pelo ADR-001
  quando o atendente assume manualmente pelo painel.
- Testes: `test_divisor_nomeia_o_atendente` e `test_divisor_sem_nome_usa_fallback`
  — **57 no total**.

---

## 2026-07-21 (12) — Aviso de espera no handoff

- Ao escalar para humano, o bot passa a responder **primeiro**:
  *"Aguarde enquanto transfiro esse atendimento para um atendente disponível."*
  (`MENSAGEM_AGUARDE` em `orchestrator.py`), e só então vem o divisor de sistema
  com o desfecho da fila.
- `Resposta.mensagens_extra` (campo que existia sem uso) passa a carregar o
  divisor; `POST /api/conversas/<id>/mensagens` persiste as duas mensagens **na
  ordem** e as devolve em `mensagens_extra`.
- Vale para os três gatilhos da Decisão B (pedido explícito, tópico crítico,
  baixa confiança) — todos resultam em transferência.
- Verificado nos dois caminhos: com atendente disponível → aviso + "Transferido
  para atendente humano"; sem atendente → aviso + prazo estimado de 30 min.
- Testes: `TestMensagemDeEspera` + ajustes em `TestFilaSemAtendente` — **56 no total**.

---

## 2026-07-21 (11) — Pesquisa de satisfação + mensagem de encerramento configurável

- **Schema** (migration `003_pesquisa_e_encerramento.sql` + `schema.sql` +
  `models.py`): `pesquisas_satisfacao` (nota 1–5 + comentário, uma por conversa) e
  `config_encerramento` (linha única: texto, imagem, `imagem_como_fundo`,
  `cor_fundo`, `cor_texto`).
- **Chat**: "Encerrar" passa pela **pesquisa de satisfação** (notas 1–5 com
  emoji/rótulo + comentário opcional, ou "Pular"). Após responder, a conversa é
  encerrada e exibe o **cartão de despedida** configurado. O cartão também
  reaparece ao reabrir uma conversa encerrada.
- **Endpoints**: `POST /api/conversas/<id>/pesquisa` (grava e encerra),
  `GET /api/encerramento` (público, para o chat); `/encerrar` agora também
  devolve a mensagem final.
- **Admin → "Mensagem de encerramento"**: edita o texto (com barra de emojis),
  cores de fundo/texto, **upload de imagem** (PNG/JPG/GIF/WEBP, até 2 MB) e opção
  de usar a imagem como **plano de fundo**, com **pré-visualização** ao vivo.
- **Relatórios**: card de satisfação (média + nº de respostas) e distribuição de
  notas no período.
- Uploads salvos em `app/static/uploads/` (fora do banco, conforme Decisão F do
  ADR-001) e **ignorados pelo git**; nome de arquivo é gerado, nunca o do usuário.
- Testes: `tests/test_pesquisa_encerramento.py` — **54 no total**. Verificado no
  navegador: pesquisa, cartão final, edição/salvamento no admin e relatório.

---

## 2026-07-21 (10) — Tela de login do profissional + botão "Cadastrar usuário"

- **Novo endpoint** `POST /api/servidores/login` (e-mail **ou** matrícula +
  senha) — autentica **sem criar** cadastro; repositório `autenticar_servidor`.
- **Tela de login** na entrada do chat (`templates/index.html` +
  `static/js/chat.js`), com botão **"Cadastrar usuário"** que abre o popup de
  cadastro; o cadastro ganhou "Já tenho cadastro" para voltar ao login.
- **"Novo Atendimento" não pede mais senha** quando já autenticado (abre o
  atendimento direto); link **"Sair"** no cabeçalho troca de usuário.
- Mensagens de erro distintas: cadastro inexistente orienta ao cadastro; senha
  incorreta é genérica (nota de enumeração registrada no ADR-003 D2).
- Testes: 5 novos (login por matrícula/e-mail, senha errada, não cadastrado,
  login não cria usuário) — **40 no total**. Verificado no navegador: login,
  criação direta de atendimento, Sair e navegação login↔cadastro.

---

## 2026-07-21 (9) — Popup passa a exigir senha (cadastro/autenticação)

- Campo **Assunto do atendimento** substituído por **Senha** no popup
  (`templates/index.html` + `static/js/chat.js`); assunto passa a usar o padrão
  "Atendimento".
- `identificar_servidor` (repositório) vira **cadastro-ou-autenticação**:
  matrícula nova cadastra a senha (hash Werkzeug/scrypt); existente exige a senha
  correta (401 se errada); registro legado sem senha define-a no acesso.
  `POST /api/servidores/identificar` valida senha mínima de 6 caracteres.
- A senha **nunca** é persistida no navegador (removida antes de salvar em
  `localStorage`); armazenada só como hash no banco.
- Testes atualizados (senha obrigatória, senha incorreta → 401, senha curta →
  400) — 35 no total. Verificado no navegador: cadastro, senha errada e senha
  correta. Ver [ADR-003](../ADR-003-identificacao-e-admin.md) D2.

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
