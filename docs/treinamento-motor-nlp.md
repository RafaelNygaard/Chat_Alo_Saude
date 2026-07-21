# Treinamento do motor de NLP (A1)

Como "treinar" e avaliar o motor de conversa. Referência: ADR-001, Decisão A.

## O que "treinar" significa aqui

O motor ativo é o **A1 — regras + FAQ** (`app/nlp/rules_engine.py`). Ele **não
tem treino por gradiente**: classifica a mensagem por **similaridade de
trigramas** (Jaccard, equivalente ao `pg_trgm`) contra os `padroes` de cada
intent na tabela `faq_intents`. Portanto, "treinar" = **curar a base de
intents**: adicionar/ajustar intenções, frases de exemplo e respostas, e
**calibrar o limiar de confiança** do handoff.

```
mensagem → normalizar (preprocess) → similaridade trigram vs padroes
         → (intent, confiança) → se confiança < limiar: handoff
```

## Fonte dos intents

Os intents vêm do **uso real** — corpus de conversas do WhatsApp em
`dataset/`. As intenções mais frequentes observadas: localizar ESF/UBS por
endereço (dominante), especialista atende pelo SUS, agendamento de especialista,
sala de vacina/campanha, aplicação de medicamento no PSF, notificação (VEPI),
pedido de exame, visita médica domiciliar.

### ⚠️ De-identificação obrigatória (LGPD)

O corpus contém **PII real** (nomes, CPF, CNS, telefones, endereços). O ADR-001
mantém o corpus **bloqueado** até os itens 1, 2 e 4 (jurídico/DPO/anonimização).

Regra ao derivar intents: **usar apenas a formulação genérica da pergunta**,
nunca dados de um caso real. Os `padroes` são exemplos de frase para o matching,
não registros de paciente. `db/seed_intents.sql` segue essa regra e **não contém
PII**.

## Como adicionar ou alterar um intent

Editar `db/seed_intents.sql` — `INSERT ... ON CONFLICT (intent) DO UPDATE`
(idempotente). Campos de `faq_intents`:

| Campo | Uso |
|-------|-----|
| `intent` | Identificador único (snake_case) |
| `padroes` | Frases de exemplo, **uma por linha** (`E'...\n...'`) |
| `resposta` | Texto que o bot responde |
| `chip_label` | Se preenchido, vira chip de ação rápida na UI |
| `ativo` | `TRUE` para entrar no motor |

Reaplicar após editar:

```powershell
$env:PGPASSWORD='senha'
& 'C:\Program Files\PostgreSQL\17\bin\psql.exe' -U alosaude -h localhost -d alosaude -f db\seed_intents.sql
```

Reiniciar o servidor para recarregar (os intents são lidos do banco a cada
requisição via `repositories.carregar_intents`).

## Avaliação (harness)

`eval/run_eval.py` roda o `RulesEngine` contra o conjunto rotulado
`eval/casos.py` (frases de-identificadas → intent esperada, incluindo negativos
que devem cair em fallback).

```powershell
.\.venv\Scripts\python.exe -m eval.run_eval                 # intents do banco
.\.venv\Scripts\python.exe -m eval.run_eval --sql db\seed_intents.sql   # sem Postgres
```

Saída: acurácia top-1, confiança média dos acertos, erros de classificação e um
**sweep do limiar** (cobertura × precisão × falsos positivos em negativos).

### Como ler o resultado / calibrar o limiar

- **Cobertura** = fração das perguntas respondíveis aceitas no limiar.
- **Precisão** = das respostas aceitas, quantas estão certas.
- **Falsos+ (neg)** = negativos aceitos (bot responde quando deveria escalar).

O limiar de produção é `HANDOFF_LIMIAR_CONFIANCA` no `.env`. **Subir** o limiar
= menos respostas erradas, mais handoff desnecessário; **baixar** = mais
cobertura, risco de aceitar ruído.

## Estado atual (2026-07-21)

14 intents ativos. Medição em **dois conjuntos**:

| Conjunto | Frases | Acurácia top-1 | Confiança média (acertos) |
|----------|--------|----------------|---------------------------|
| Autoria (paráfrases próximas dos padrões) | 27 | 100% | 0.669 |
| **Held-out** (vocabulário diferente, ver `eval/casos.py`) | 34 | **64,7%** | **0,223** (máx 0,348) |

O número honesto é o **held-out: ~65%**. O de autoria (100%) media memorização
dos padrões, não generalização.

### Achado principal — o motor A1 generaliza mal

As confianças no held-out ficam comprimidas numa faixa **muito baixa (0,09–0,35)**,
até nos acertos. Consequência: **não existe limiar que dê boa cobertura e boa
precisão ao mesmo tempo** (sweep em `eval/run_eval.py`):

| Limiar | Cobertura | Precisão | Falsos+ (fora de escopo) |
|--------|-----------|----------|--------------------------|
| 0,30 (atual) | 9% | 100% | 0 |
| 0,20 | 56% | 79% | 1 |
| 0,15 | 85% | 69% | 3 |

**Ponto de operação em 0,30:** de 34 perguntas in-scope, o bot responde 3
(9%), erra 0 e **escala 31 (91%)** para humano; nos 12 casos fora de escopo,
acerta o handoff em 100%. Ou seja, no limiar atual o bot é **seguro mas quase só
um roteador para humano** — automatiza pouco.

Os erros são majoritariamente confusões entre intents vizinhos que compartilham
tokens ("paciente", "unidade"): `localizar_esf` ↔ `lotacao_paciente`,
`pedido_exame` → `lotacao_paciente`. O trigrama se prende a palavras comuns.

### Implicação para a Decisão A (A1 → A2/A3)

Este é o dado que embasa a evolução do motor:

- **Baixar o limiar** (ex.: 0,20) aumenta cobertura para ~56%, mas ~21% das
  respostas aceitas ficam **erradas** — inaceitável num contexto de saúde.
- **Manter 0,30** é seguro, porém automatiza ~9%.
- Melhorar o A1 exigiria cobrir manualmente o espaço de vocabulário (muitos
  sinônimos por intent) — trabalhoso e frágil.
- **A2 (Rasa) / A3 (LLM/embeddings)** tratam paráfrase/semântica nativamente e
  são o caminho para ganho real de acurácia — dependem da anonimização (item 4
  do ADR) e das validações jurídicas (itens 1–2).

**Recomendação:** manter `HANDOFF_LIMIAR_CONFIANCA=0.30` (seguro) enquanto o
motor for A1, e priorizar A2/A3 em vez de baixar a barra de confiança.

### Próximos passos

1. ✅ Conjunto held-out em `eval/casos.py` (feito).
2. Se permanecer em A1: enriquecer `padroes` com sinônimos e reavaliar (meta:
   subir a confiança dos acertos acima de 0,30).
3. Planejar A2/A3 conforme ADR — usar este harness como linha de base de acurácia.
