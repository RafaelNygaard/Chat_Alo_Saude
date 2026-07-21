# Guia da área administrativa

Referência operacional do console técnico-administrativo (ADR-003).

## Acesso

1. Criar um administrador (uma vez):

   ```powershell
   python manage.py create-admin --nome "Seu Nome" --email voce@pmpc.sp.gov.br --senha "SENHA_FORTE"
   ```

2. Acessar `http://localhost:5000/login` e entrar com e-mail (ou matrícula) e senha.
3. O painel fica em `http://localhost:5000/admin` (redireciona para o login se não houver sessão).

Redefinir senha: `python manage.py set-senha --email voce@... --senha NOVA`.

## Módulos

| Seção | O que faz |
|-------|-----------|
| **Relatórios** | Total de atendimentos e quebras por status, unidade, função e handoff por gatilho no período. Botão **Exportar CSV** (`;` como separador). |
| **Servidores** | Lista/filtra usuários por papel; cria e edita (inclusive definir senha para papéis com login). |
| **Funções** | Cadastra e ativa/desativa as funções do combo do popup. |
| **Unidades de saúde** | Cadastra UBS/ESF (nome + município). |
| **Intents (FAQ)** | Cria/edita/ativa/exclui intents do bot (padrões e resposta). Alimenta o motor A1 e os chips. |
| **Tópicos críticos** | Termos que forçam handoff (Decisão B do ADR-001). |
| **Atendentes** | Ajusta a disponibilidade (disponível/ocupado/ausente). |

## Papéis (campo `papel`)

- `servidor` — quem solicita atendimento pelo popup (sem login).
- `enfermeiro` — solicitante legado (ADR-001).
- `atendente` — responde na fila; tem login.
- `admin` — acesso total ao console; tem login.

## Notas

- Alterações em intents/tópicos entram em vigor no próximo atendimento (os intents
  são lidos do banco a cada requisição).
- Segurança: em produção, usar `SECRET_KEY` forte e HTTPS. Login ainda não tem
  rate-limiting/2FA; o painel do atendente ainda usa `?atendente_id=` (ver dívidas
  no ADR-003).
