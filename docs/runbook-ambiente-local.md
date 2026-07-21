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
```

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

## 3. Executar

```powershell
.\.venv\Scripts\python.exe run.py
```

- Chat do enfermeiro: <http://localhost:5000/?usuario_id=1>
- Painel do atendente: <http://localhost:5000/atendente?atendente_id=2>

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
