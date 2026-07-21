# ADR-003: Identificação do servidor e área administrativa (com autenticação)

**Status:** Proposto
**Data:** 2026-07-21
**Decisores:** Rafael Nygaard Rocha (Analista de Sistemas) + coordenação do serviço Alô Saúde
**Relação:** estende o [ADR-001](ADR-001-chatbot-alo-saude.md) — que deixou autenticação como "item futuro". Este ADR entrega identificação e a camada técnico-administrativa.

## Contexto

No MVP, o solicitante era identificado por um parâmetro de URL (`?usuario_id=`),
sem coleta de dados nem gestão. Necessidades:

1. Cada servidor deve **se identificar ao solicitar um novo atendimento** — nome,
   e-mail, matrícula, **função** e **unidade de saúde**.
2. Uma **área administrativa** para inserir esses dados, gerar relatórios e demais
   funções técnico-administrativas, com **acesso controlado**.

## Decisões

### D1 — Modelo de dados
- Nova tabela **`funcoes`** (gerenciável no admin), separada de `usuarios.papel`.
  Motivo: `papel` é **nível de acesso** (servidor/enfermeiro/atendente/admin);
  `funcao` é o **cargo** do servidor (Enfermeiro, ACS, Médico…). Misturar os dois
  seria um erro de modelagem.
- `usuarios` ganha `email`, `funcao_id` (FK) e `senha_hash`; `papel` passa a
  aceitar `servidor`. Migration idempotente `db/migrations/002_*.sql`.

### D2 — Identificação (popup)
- Modal no "Novo Atendimento" coleta nome, e-mail, matrícula, função, unidade e
  **senha**, e chama `POST /api/servidores/identificar` (chave natural =
  matrícula), sem rebaixar quem já é atendente/admin.
- **Cadastro-ou-autenticação** (rev. 2026-07-21): matrícula nova → cadastra com
  senha (hash); matrícula existente → exige a senha correta (senha errada = 401);
  registro legado sem senha → define a senha no próximo acesso. Isso evita que
  qualquer pessoa assuma a matrícula de outra. A senha nunca é persistida no
  navegador; a identidade (sem senha) fica em `localStorage` para pré-preencher.
- O campo "Assunto do atendimento" foi **substituído** pela senha; o assunto
  passa a usar o padrão "Atendimento".

### D3 — Autenticação (decisão do responsável: login completo)
- **Sessão Flask** (cookie assinado por `SECRET_KEY`) + **hash de senha do
  Werkzeug** (`generate_password_hash`/`check_password_hash`). Sem dependências
  novas.
- Apenas papéis **admin** e **atendente** têm credencial e login; `admin_required`
  protege `/admin` e `/api/admin/*`. Sem tabela de sessões — cookie assinado é
  suficiente para a escala (centenas de usuários, ADR-001).
- Admin criado via `python manage.py create-admin`.

### D4 — Escopo da área administrativa
Módulos entregues (todos protegidos):
- **Cadastros:** funções, unidades (UBS), servidores/usuários.
- **Relatórios:** atendimentos por período, status, unidade, função; handoffs por
  gatilho; **exportação CSV**.
- **Gestão do bot:** editar `faq_intents` e `topicos_criticos` pela UI.
- **Operação:** disponibilidade dos atendentes.

## Consequências

**Positivas**
- Rastreabilidade real: cada atendimento fica ligado a um servidor, função e
  unidade — base dos relatórios.
- Gestão do bot e dos cadastros sem SQL manual.
- Caminho para aposentar o hack `?usuario_id=`.

**Custos / riscos**
- Superfície de autenticação a manter. Em produção exige `SECRET_KEY` forte
  (hoje valor de dev) e HTTPS obrigatório para o cookie de sessão.
- **LGPD:** passamos a coletar PII de **servidores** (não de pacientes) — dado
  funcional e mínimo; definir retenção e base legal (RH/vínculo funcional).

**Dívidas conhecidas (futuras)**
- Sem rate-limiting/lockout de login nem 2FA.
- O **painel do atendente ainda usa `?atendente_id=`** (não migrado para login) —
  migração fica para iteração seguinte.

## Alternativas consideradas
- **Reusar `papel` como função** — rejeitado: mistura acesso com cargo, não
  expansível.
- **Área admin sem proteção** — rejeitado pelo responsável; optou-se por login.

## Referências
- `db/migrations/002_identificacao_e_admin.sql`, `app/api/servidores.py`,
  `app/api/admin.py`, `app/auth.py`, `app/api/auth.py`, `manage.py`
- Frontend: modal em `templates/index.html` + `static/js/chat.js`;
  `templates/login.html`, `templates/admin.html`, `static/js/admin.js`
- [docs/guia-admin.md](docs/guia-admin.md), [docs/CHANGELOG.md](docs/CHANGELOG.md)
