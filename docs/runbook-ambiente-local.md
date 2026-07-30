# Runbook — Ambiente local de desenvolvimento

Como subir o Chatbot Alô Saúde do zero em uma máquina Windows. Reflete o que foi
feito em 2026-07-21 (ver [CHANGELOG](CHANGELOG.md)).

## Pré-requisitos

- Windows 10/11, PowerShell
- Python 3.10+ (validado com 3.14)
- PostgreSQL 14+ (instruções abaixo se não houver)

## 1. PostgreSQL

Se não houver Postgres nem Docker, instalar o servidor via `winget`:

```powershell
winget install --id PostgreSQL.PostgreSQL.17 --source winget --silent `
  --accept-package-agreements --accept-source-agreements `
  --override "--mode unattended --unattendedmodeui none --superpassword postgres --serverport 5432 --enable-components server,commandlinetools"
```

Isso cria o serviço `postgresql-x64-17` (porta 5432) e o superusuário
`postgres` / senha `postgres`. O `psql` fica em
`C:\Program Files\PostgreSQL\17\bin\psql.exe`.

### Criar role e banco da aplicação

```powershell
$env:PGPASSWORD='postgres'; $psql='C:\Program Files\PostgreSQL\17\bin\psql.exe'
& $psql -U postgres -h localhost -c "CREATE ROLE alosaude LOGIN PASSWORD 'senha'"
& $psql -U postgres -h localhost -c "CREATE DATABASE alosaude OWNER alosaude"
# DEV apenas — SUPERUSER habilita CREATE EXTENSION do schema. Rever em produção.
& $psql -U postgres -h localhost -c "ALTER ROLE alosaude SUPERUSER"
```

### Aplicar schema e seeds

```powershell
$env:PGPASSWORD='senha'
& $psql -U alosaude -h localhost -d alosaude -f db\schema.sql
& $psql -U alosaude -h localhost -d alosaude -f db\seed_intents.sql
# Migrations incrementais (após o schema base):
& $psql -U alosaude -h localhost -d alosaude -f db\migrations\002_identificacao_e_admin.sql
& $psql -U alosaude -h localhost -d alosaude -f db\migrations\003_pesquisa_e_encerramento.sql
& $psql -U alosaude -h localhost -d alosaude -f db\migrations\004_funcao_atendente_chat.sql
& $psql -U alosaude -h localhost -d alosaude -f db\migrations\005_fila_round_robin.sql
& $psql -U alosaude -h localhost -d alosaude -f db\migrations\006_config_cabecalho.sql
& $psql -U alosaude -h localhost -d alosaude -f db\migrations\007_recuperacao_senha.sql
& $psql -U alosaude -h localhost -d alosaude -f db\migrations\008_config_email_senha_temporaria.sql
& $psql -U alosaude -h localhost -d alosaude -f db\migrations\009_feedback_mensagens.sql
```

> Nota: `schema.sql` já inclui a tabela `funcoes` e as colunas novas de
> `usuarios`. A migration 002 é para bancos criados antes do ADR-003 (idempotente).

### Usuários seed (necessários para o MVP sem autenticação)

```sql
INSERT INTO ubs (nome, municipio) VALUES ('UBS Centro','Poços de Caldas');
INSERT INTO usuarios (id, nome, papel, ubs_id) VALUES
  (1,'Enfermeiro Demo','enfermeiro',1),
  (2,'Atendente Demo','atendente',1);
INSERT INTO atendentes_status (atendente_id, status) VALUES (2,'disponivel');
```

## 2. Ambiente Python

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env   # ajustar se necessário
```

`run.py` carrega o `.env` via `load_dotenv()`. Variáveis relevantes:

| Variável | Dev | Papel |
|----------|-----|-------|
| `DATABASE_URL` | `postgresql+psycopg2://alosaude:senha@localhost:5432/alosaude` | Conexão |
| `HANDOFF_LIMIAR_CONFIANCA` | `0.30` | Limiar de confiança do handoff (ver treino do NLP) |
| `APP_BASE_URL` | `http://localhost:5000` | Base do link de recuperação de senha |
| `RECUPERACAO_TTL_MIN` | `60` | Validade do token de recuperação (minutos) |
| `SMTP_HOST` … | vazio | E-mail de recuperação. **Vazio = link vai para o log** (dev) |

### Recuperação de senha / SMTP

O SMTP é configurado na **área administrativa** (Configurações → Servidor de
e-mail); a senha fica **cifrada** no banco. As variáveis `SMTP_*` do `.env` são
apenas um **fallback** quando o SMTP não foi definido no admin. Sem nenhum SMTP,
a **senha temporária** de recuperação é escrita no **log do servidor**
(`WARNING in emailer`), o que permite testar o fluxo em desenvolvimento.

## 3. Criar um administrador (área admin — ADR-003)

```powershell
.\.venv\Scripts\python.exe manage.py create-admin --nome "Admin" --email admin@pmpc.sp.gov.br --senha "SENHA_FORTE"
```

## 4. Executar

```powershell
.\.venv\Scripts\python.exe run.py
```

- Chat (identificação via popup): <http://localhost:5000/>
- Painel do atendente: <http://localhost:5000/atendente?atendente_id=2>
- Área administrativa: <http://localhost:5000/admin> (via <http://localhost:5000/login>)

### Acesso pela rede

O `.env` usa `HOST=0.0.0.0`, então o sistema responde no IP da máquina —
ex.: <http://10.0.0.212:5000>. Variáveis (em `.env`):

| Variável | Efeito |
|----------|--------|
| `HOST` | `0.0.0.0` = todas as interfaces (rede); `127.0.0.1` = só local |
| `PORT` | porta HTTP (padrão 5000) |
| `DEBUG` | `0` recomendado ao expor na rede; `1` liga reloader/debugger (dev local) |

Se outra máquina não alcançar, verifique a categoria da rede
(`Get-NetConnectionProfile`) e o firewall do perfil correspondente. Numa rede
**Private** com firewall desativado, o acesso funciona sem regra extra; num perfil
**Public** ativo, é preciso liberar a porta 5000 (com privilégio de admin):

```powershell
# Executar como administrador — libera a porta 5000 para entrada
New-NetFirewallRule -DisplayName "Alo Saude 5000" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5000
```

> Segurança: o servidor Flask de desenvolvimento não é hardened para produção.
> Para uso além de demo/rede interna, servir atrás de gunicorn/uwsgi + proxy
> reverso (nginx) com HTTPS e `SECRET_KEY` forte.

## Troubleshooting

- **`ModuleNotFoundError: No module named 'psycopg2'` no boot** — o
  `create_engine` importa o driver na inicialização. Instalar
  `psycopg2-binary` (há wheel para Python 3.14). O `init_db` também tolera o
  driver ausente, subindo só as páginas.
- **Chat responde mas nada persiste** — verificar se o serviço Postgres está
  `Running` e a porta 5432 aberta (`Test-NetConnection localhost -Port 5432`).
- **`.env` ignorado** — garantir que `run.py` chama `load_dotenv()` antes de
  `create_app()`.

## Credenciais de desenvolvimento

Apenas para a máquina local; **não usar em produção**.

| O quê | Valor |
|-------|-------|
| Superusuário Postgres | `postgres` / `postgres` |
| Role da aplicação | `alosaude` / `senha` |
