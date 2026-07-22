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
| **Relatórios** | Total de atendimentos e quebras por status, unidade, função e handoff por gatilho no período; **satisfação** (média, nº de respostas e distribuição de notas). Botão **Exportar CSV** (`;` como separador). |
| **Mensagem de encerramento** | Texto exibido após a pesquisa de satisfação. Aceita **emojis** (barra de atalho), **imagem** (PNG/JPG/GIF/WEBP até 2 MB), **cores** de fundo e texto, e opção de usar a imagem como **plano de fundo**. Tem pré-visualização ao vivo. |
| **Servidores** | Lista/filtra usuários por papel; cria e edita (inclusive definir senha para papéis com login). |
| **Funções** | Cadastra e ativa/desativa as funções do combo do popup. |
| **Unidades de saúde** | Cadastra UBS/ESF (nome + município). |
| **Intents (FAQ)** | Cria/edita/ativa/exclui intents do bot (padrões e resposta). Alimenta o motor A1 e os chips. |
| **Tópicos críticos** | Termos que forçam handoff (Decisão B do ADR-001). |
| **Atendentes** | Ajusta a disponibilidade (disponível/ocupado/ausente). |

## Fila de atendentes (distribuição balanceada)

Quando um profissional pede atendimento humano, o sistema procura um atendente
com status **disponível** e transfere na hora. A ordem é um **rodízio**:

1. Quem **nunca** atendeu vem primeiro.
2. Quem **encerra** um atendimento vai para o **fim** da fila.

Assim a carga fica equilibrada. Ao encerrar, o atendente volta automaticamente
para `disponível` — exceto se ele mesmo tiver se marcado como `ausente`, que é
respeitado. Quem está `ocupado` ou `ausente` fica fora da fila.

## Função "Atendente chat"

Profissionais cadastrados com a **função** `Atendente chat` são levados direto ao
**painel do atendente** (`/atendente`) ao fazer login — não passam pelo chat. Ao
entrar, eles são incluídos na disponibilidade da fila (status inicial
*disponível*), podendo alterar no próprio painel.

Para transformar alguém em atendente de chat: **Servidores → Editar → Função =
"Atendente chat"**. Note que `função` é o cargo; o `papel` (abaixo) continua
controlando o acesso ao console administrativo.

## Papéis (campo `papel`)

- `servidor` — quem solicita atendimento pelo popup (sem login).
- `enfermeiro` — solicitante legado (ADR-001).
- `atendente` — responde na fila; tem login.
- `admin` — acesso total ao console; tem login.

## Pesquisa de satisfação

Ao clicar em **Encerrar** no chat, o profissional avalia o atendimento (nota 1–5 +
comentário opcional) ou escolhe **Pular**. Em seguida a conversa é encerrada e
aparece o cartão com a mensagem configurada acima. As respostas alimentam o card
de satisfação em **Relatórios**.

## Notas

- Alterações em intents/tópicos entram em vigor no próximo atendimento (os intents
  são lidos do banco a cada requisição).
- A mensagem de encerramento é **sempre a versão atual**: conversas antigas
  reabertas exibem o texto configurado hoje, não o vigente à época.
- Imagens enviadas ficam em `app/static/uploads/` (fora do banco) e não são
  versionadas no git.
- Segurança: em produção, usar `SECRET_KEY` forte e HTTPS. Login ainda não tem
  rate-limiting/2FA; o painel do atendente ainda usa `?atendente_id=` (ver dívidas
  no ADR-003).
