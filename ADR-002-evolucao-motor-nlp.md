# ADR-002: Evolução do motor de NLP — A1 (regras) insuficiente, priorizar A3 (LLM)

**Status:** Proposto
**Data:** 2026-07-21
**Decisores:** Rafael Nygaard Rocha (Analista de Sistemas) + coordenação do serviço Alô Saúde
**Relação:** refina a **Decisão A** do [ADR-001](ADR-001-chatbot-alo-saude.md) com evidência empírica. Não altera as demais decisões.

## Contexto

O ADR-001 (Decisão A) recomendou um **híbrido A1 + A3** atrás da interface
`NLPEngine`, com A1 (regras + `pg_trgm`) para fluxos frequentes e A3 (LLM) para
perguntas abertas. O A1 foi implementado e "treinado": curamos os intents a
partir do corpus real de WhatsApp (de-identificado) em `db/seed_intents.sql` e
construímos um harness de avaliação (`eval/`).

Este ADR registra o que a **medição empírica** revelou sobre o A1 e formaliza o
próximo passo do motor. Contexto operacional completo em
[docs/treinamento-motor-nlp.md](docs/treinamento-motor-nlp.md).

## Evidência

Avaliação em conjunto **held-out** (34 frases in-scope com vocabulário distinto
dos padrões + 12 negativos), via `python -m eval.run_eval`:

| Conjunto | Acurácia top-1 | Confiança média (acertos) |
|----------|----------------|---------------------------|
| Autoria (paráfrases próximas dos padrões) | 100% | 0,669 |
| **Held-out (generalização real)** | **64,7%** | **0,223** (máx 0,348) |

As confianças dos acertos ficam comprimidas numa faixa **muito baixa
(0,09–0,35)**. Consequência: não há limiar que concilie cobertura e precisão.

| Limiar | Cobertura | Precisão | Falsos+ (fora de escopo) |
|--------|-----------|----------|--------------------------|
| 0,30 (atual) | 9% | 100% | 0 |
| 0,20 | 56% | 79% | 1 |
| 0,15 | 85% | 69% | 3 |

**Ponto de operação em 0,30:** de 34 perguntas in-scope, o bot responde 3 (9%),
erra 0 e escala 31 (91%). Os erros são confusões entre intents que compartilham
tokens comuns ("paciente", "unidade") — o trigrama se prende a palavras
frequentes, não ao sentido.

## Decisão

1. **A1 permanece como camada interna segura** (roteador para humano) enquanto
   for o motor ativo, no limiar `HANDOFF_LIMIAR_CONFIANCA=0.30` — automatiza
   pouco (~9%), mas não entrega resposta errada.
2. **A3 (LLM externo) passa de "recomendado" a planejado e priorizado** como
   motor de entendimento/geração para perguntas abertas, atrás da interface
   `NLPEngine` — sem reescrever orquestrador, handoff, API ou UI.
3. **Pré-requisitos bloqueantes** (herdados do ADR-001, agora inegociáveis antes
   de qualquer envio externo):
   - Itens 1–2: validações jurídicas / DPO e DPA com o provedor.
   - Item 4: pipeline de anonimização/mascaramento de PII (CPF, CNS, nome,
     telefone, endereço) **antes** de qualquer chamada externa.
4. **Fallback:** se o jurídico vetar o envio externo, adotar **A2 (Rasa)**
   self-hosted, sem alterar o restante do sistema. O mesmo harness serve de
   linha de base para qualquer motor.

## Alternativas consideradas

- **Enriquecer o A1 com mais sinônimos por intent** — rejeitado como solução
  principal: trabalho manual, frágil e sem teto de qualidade. Mantido apenas como
  melhoria incremental de curto prazo, se o A1 seguir ativo.
- **Baixar o limiar (ex.: 0,20)** — rejeitado: elevaria a cobertura a ~56%, mas
  ~21% das respostas aceitas ficariam **erradas**, inaceitável em contexto de
  saúde.

## Consequências

**Positivas**
- Caminho de evolução claro e baseado em dados, não em intuição.
- Baseline de acurácia estabelecida (`eval/`) — mede diretamente o ganho de
  A2/A3.
- A arquitetura já suporta a troca (interface `NLPEngine` plugável — a decisão
  mais importante do ADR-001).

**Negativas / custos**
- Depende de aprovação jurídica e da construção do pipeline de anonimização
  (item 4) antes de habilitar A3.
- A3 implica custo recorrente por uso e dependência de terceiro (DPA).
- Enquanto A1 for o motor, a automação real é baixa (~9%); o valor do produto no
  MVP está mais no roteamento/organização do atendimento do que na resposta
  automática.

**Riscos**
- Sem anonimização robusta, o risco LGPD de A3 é alto — daí ser bloqueante.

## Critérios de aceitação (para promover A2/A3 a motor ativo)

Medido pelo mesmo harness (`eval/run_eval.py`), em conjunto held-out:

- Superar a baseline do A1 (held-out top-1 **> 64,7%**; meta de trabalho **≥ 85%**).
- Existir um limiar com **cobertura ≥ 70%** e **precisão ≥ 90%**
  simultaneamente, com **0 falsos positivos** nos negativos.
- Anonimização de PII validada antes de qualquer envio externo (item 4 do ADR-001).

## Referências

- [ADR-001](ADR-001-chatbot-alo-saude.md) — Decisão A (motor de NLP)
- [docs/treinamento-motor-nlp.md](docs/treinamento-motor-nlp.md) — método e resultados
- `eval/run_eval.py`, `eval/casos.py` — harness e conjunto rotulado
- [docs/CHANGELOG.md](docs/CHANGELOG.md)
