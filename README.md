# Chatbot UBS ↔ Alô Saúde

[![CI](https://github.com/RafaelNygaard/Chat_Alo_Saude/actions/workflows/ci.yml/badge.svg)](https://github.com/RafaelNygaard/Chat_Alo_Saude/actions/workflows/ci.yml)

Implementação do [ADR-001](ADR-001-chatbot-alo-saude.md). Fundação do MVP: itens de ação 3, 6 e 7.

## Documentação (docs as code)

O projeto segue **docs as code**: a documentação é versionada e atualizada junto
com cada mudança. Ver [`docs/`](docs/README.md) — em especial o
[CHANGELOG](docs/CHANGELOG.md), o [runbook de ambiente](docs/runbook-ambiente-local.md)
e o [guia de treino do motor NLP](docs/treinamento-motor-nlp.md).

## Estrutura

```
app/
  __init__.py        App factory Flask
  config.py          Config (limiar de handoff parametrizável)
  db.py              Sessão SQLAlchemy
  models.py          Models das 10 tabelas (espelham db/schema.sql)
  repositories.py    Acesso a dados (intents, tópicos, handoff)
  api/chat.py        Chat: conversas, mensagens, chips, stream SSE, encerrar
  api/atendente.py   Painel: fila, disponibilidade, assumir, responder
  pages.py           Rotas / (chat) e /atendente (painel)
  templates/         index.html, atendente.html (gov.br, Inter/Outfit, VLibras)
  static/            estilo.css, comum.js, chat.js, atendente.js
  nlp/
    engine.py        Interface NLPEngine (Decisão A — plugável)
    preprocess.py    Normalização (unicodedata + re)
    rules_engine.py  Motor A1: regras + FAQ, similaridade trigram
  orchestrator/
    orchestrator.py  Orquestrador: gatilhos de handoff (Decisão B)
    handoff.py       Fila + disponibilidade de atendentes
db/schema.sql        DDL PostgreSQL: 9 tabelas do ADR + topicos_criticos,
                     pg_trgm, função gerar_protocolo(), seeds de intents
tests/               Testes sem banco (fakes) — pytest
```

## Setup

```bash
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
createdb alosaude && psql alosaude < db/schema.sql
copy .env.example .env                            # ajustar DATABASE_URL
python run.py
```

## Testes

```bash
python -m pytest tests/ -q
```

## Gatilhos de handoff (Decisão B)

Qualquer um escala a conversa, gravando divisor de sistema (`mensagens.autor='sistema'`):

1. Pedido explícito — intent `falar_com_atendente`
2. Confiança < 0,6 em 2 mensagens consecutivas (parametrizável via `.env`)
3. Tópico crítico — termos na tabela `topicos_criticos`, não em código

## Uso (MVP sem autenticação)

- Chat do enfermeiro: `http://localhost:5000/?usuario_id=1`
- Painel do atendente: `http://localhost:5000/atendente?atendente_id=2`
- Requer usuários seed no banco (papel `enfermeiro` e `atendente`); autenticação é item futuro.

## Próximos passos (itens do ADR)

- Item 4: pipeline de anonimização de PII (pré-requisito para motor A3/LLM)
- Item 9: upload de anexos (Decisão F)
- Itens 1–2: validações jurídicas/DPO (bloqueantes para A3 e corpus WhatsApp)
