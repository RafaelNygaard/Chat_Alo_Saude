# ADR-001: Chatbot de comunicação UBS ↔ Alô Saúde

**Status:** Proposto (rev. 2 — incorpora achados do mockup Figma)
**Data:** 2026-07-06
**Decisores:** Rafael Nygaard Rocha (Analista de Sistemas) + coordenação do serviço Alô Saúde

## Contexto

Enfermeiros das Unidades Básicas de Saúde (UBS) precisam de um canal ágil de comunicação com a equipe de atendimento do serviço Alô Saúde. A proposta é um chatbot web que responde dúvidas via NLP e transfere a conversa para um atendente humano — automaticamente ou quando solicitado.

**Requisitos funcionais**

- Chat web com respostas geradas por NLP
- Handoff para atendente humano: automático (baixa confiança, urgência) ou por pedido explícito, **com marcação visível na conversa** (divisor de sistema: "Transferido para Agente X — hh:mm")
- Controle de disponibilidade dos atendentes
- Histórico de conversas persistido, identificado por **número de protocolo** (formato AS-AAAA-NNNNN)
- **Upload de anexos** na conversa (ex.: ficha clínica em PDF)
- **Chips de ação rápida** no chat (Encaminhamento urgente, Notificação compulsória, etc.) mapeados para intents
- Consulta a bases externas (SINAN, e-SUS) durante o atendimento — ver Decisão E

**Requisitos não funcionais e restrições**

- Stack fixa: HTML5 + CSS3 vanilla + JS ES6 (Fetch API) no frontend; Python 3.10+ / Flask 2.3.3 no backend; PostgreSQL (versão atual)
- Identidade visual gov.br; fontes Inter e Outfit
- LGPD: conversas de enfermeiros sobre pacientes podem conter **dados sensíveis de saúde** (art. 5º, II) — restrição central do projeto
- Público: enfermeiros de UBS (escala municipal/regional — centenas de usuários simultâneos, não milhares)

## Visão geral da arquitetura

```
[Navegador: HTML/CSS/JS]
   │  Fetch API (JSON) + SSE (stream de mensagens)
   ▼
[Flask]
   ├── Frontend estático (/, /static)
   ├── API de chat (/api/chat, /api/conversas/<id>/mensagens)
   ├── Orquestrador de conversa ──► decide: bot responde | escalar p/ humano
   │        ├── Camada NLP (interface NLPEngine, implementação plugável)
   │        └── Gestor de handoff (fila + disponibilidade de atendentes)
   ├── Painel do atendente (/atendente)
   └── SQLAlchemy/psycopg ──► [PostgreSQL]
```

Componentes principais:

1. **Orquestrador de conversa** — recebe cada mensagem, chama o motor NLP, avalia confiança e gatilhos de escalonamento, e decide quem responde (bot ou humano). É o coração do sistema e deve ser independente do motor NLP escolhido.
2. **Camada NLP (`NLPEngine`)** — interface única (`entender(texto) -> intent, confiança` e `gerar_resposta(contexto) -> texto`) com implementações intercambiáveis (ver Decisão A). `unicodedata` + `re` entram aqui como pré-processamento (normalização de acentos, limpeza), não como motor principal.
3. **Gestor de handoff** — mantém fila de conversas aguardando humano e o status de cada atendente (disponível/ocupado/ausente). Se ninguém está disponível, registra pendência e informa prazo estimado.
4. **Painel do atendente** — página simples (mesma stack) onde o atendente do Alô Saúde vê a fila, assume conversas e responde.

## Decisão A — Motor de NLP

### Opção A1: Regras + busca textual no PostgreSQL

Normalização com `unicodedata`/`re` + correspondência de intenções via full-text search / `pg_trgm` sobre uma base de FAQ.

| Dimensão | Avaliação |
|-----------|------------|
| Complexidade | Baixa |
| Custo | Zero (infra existente) |
| Escalabilidade | Alta |
| Familiaridade do time | Alta (Python puro + SQL) |

**Prós:** nenhum dado sai do ambiente (LGPD trivial); sem custo por uso; previsível e auditável.
**Cons:** não **gera** respostas — só recupera respostas prontas; frágil a variações de linguagem; não atende ao requisito "utilizar NLP para gerar as conversas".

### Opção A2: Rasa (NLU self-hosted, open source)

| Dimensão | Avaliação |
|-----------|------------|
| Complexidade | Média/Alta |
| Custo | Infra própria + tempo de treinamento |
| Escalabilidade | Média (exige tuning) |
| Familiaridade do time | Baixa (curva de aprendizado) |

**Prós:** dados permanecem no ambiente do órgão (forte para LGPD); classificação de intenção com confiança nativa — encaixa direto no gatilho de handoff.
**Cons:** exige criar e manter dataset de treinamento; geração de texto limitada (respostas majoritariamente template).

### Opção A3: API de LLM externa (via `requests`)

Chamada HTTP a um provedor de LLM (com contrato/DPA adequado) para entendimento e geração.

| Dimensão | Avaliação |
|-----------|------------|
| Complexidade | Baixa/Média |
| Custo | Por uso (crescente com volume) |
| Escalabilidade | Alta (delegada ao provedor) |
| Familiaridade do time | Média (é só HTTP + prompt) |

**Prós:** melhor qualidade de entendimento e geração; atende plenamente o requisito de "gerar conversas"; rápido de implementar.
**Cons:** dados sensíveis de saúde saindo do ambiente exigem DPA, anonimização/mascaramento prévio de PII e aprovação jurídica; custo recorrente; dependência de terceiro.

### Recomendação

**Híbrido A1 + A3, atrás da interface `NLPEngine`:** regras/FAQ local para os fluxos frequentes e previsíveis (horários, protocolos, encaminhamentos padrão) e LLM externo para perguntas abertas — **com camada de mascaramento de PII antes de qualquer chamada externa** (nomes, CPF, CNS removidos via `re` antes do envio). Se a avaliação jurídica vetar o envio externo, o fallback é A2 (Rasa) sem mudar o resto do sistema — por isso a interface plugável é a decisão mais importante deste ADR.

> **Atualização (2026-07-21):** avaliação empírica do A1 mostrou generalização fraca (held-out ~65%, confianças baixas). Ver [ADR-002](ADR-002-evolucao-motor-nlp.md), que prioriza A3 com base nesses dados.

## Decisão B — Gatilhos de handoff para humano

Handoff disparado por qualquer um dos gatilhos: pedido explícito do enfermeiro (intent "falar com atendente"); confiança do NLP abaixo de 0,6 em 2 mensagens consecutivas; detecção de tópicos críticos (urgência/emergência — lista de palavras-chave mantida em tabela, não em código). Ao escalar: conversa entra na fila com o histórico completo; atendente disponível recebe notificação; se fila vazia de atendentes por mais de N minutos, o bot registra a pendência e informa o prazo.

## Decisão C — Entrega de mensagens em tempo real

Com Fetch API na stack e Flask no backend, as opções são polling curto (simples, mas gera carga e latência de 2–3 s), **Server-Sent Events (recomendado)** — nativo no Flask via generator, unidirecional servidor→cliente, suficiente porque o envio do usuário já é via POST — ou WebSocket (flask-socketio), que adiciona dependência e infra sem necessidade clara aqui. **Recomendação: SSE**, com polling como fallback trivial no MVP.

## Decisão D — Utilidade do `requests` 2.31.0 (pergunta do projeto)

**Resolvida: manter.** O mockup evidencia consultas a SINAN e e-SUS durante o atendimento (Decisão E) — integração HTTP de saída que justifica a biblioteca independentemente da escolha do motor NLP. **Atualizar para a série 2.32.x**, que corrige CVEs da 2.31.0.

## Decisão E — Integração com SINAN / e-SUS

No mockup, a atendente consulta o SINAN e orienta encaminhamento via e-SUS. Duas formas de atender isso:

**Opção E1 — Consulta manual pelo atendente** (fora do sistema): zero integração; o painel apenas exibe a conversa. Simples, mas o histórico da consulta não fica registrado e o bot não pode antecipar nada.

**Opção E2 — Integração via API** (`requests` no backend): o orquestrador consulta registro prévio no SINAN ao receber um CNS validado e anexa o resultado à conversa para o atendente. Exige credenciamento junto ao DATASUS/RNDS, tratamento de indisponibilidade das bases e log de acesso (LGPD art. 37).

**Recomendação:** E1 no MVP, evoluindo para E2 na fase 2 — a arquitetura já prevê o ponto de extensão no orquestrador. Toda consulta automatizada a base externa deve ser registrada em `log_acessos_externos`.

## Decisão F — Anexos de documentos clínicos

Upload de arquivos (ex.: ficha clínica em PDF) requer: armazenamento fora do banco (filesystem/objeto, com caminho em tabela `anexos`), validação de tipo e tamanho (PDF/JPG/PNG, limite sugerido 10 MB), verificação antimalware antes de disponibilizar ao atendente, e política de retenção própria — documento clínico tem prazo legal de guarda distinto do log de conversa. Acesso ao anexo sempre autenticado e registrado.

## Modelo de dados (PostgreSQL)

| Tabela | Campos principais |
|---|---|
| `usuarios` | id, nome, cns/matrícula, ubs_id, papel (enfermeiro/atendente/admin) |
| `ubs` | id, nome, município |
| `conversas` | id, **protocolo (AS-AAAA-NNNNN, único)**, usuario_id, assunto, status, atendente_id, criada_em |
| `mensagens` | id, conversa_id, autor (usuario/bot/atendente/**sistema**), texto, confianca_nlp, criada_em |
| `anexos` | id, mensagem_id, nome_original, caminho_storage, mime_type, tamanho, verificado_em |
| `atendentes_status` | atendente_id, status, atualizado_em |
| `faq_intents` | id, intent, padrões, resposta, **chip_label** (ação rápida no chat), ativo |
| `handoffs` | id, conversa_id, gatilho, tempo_espera, resolvido_em |
| `log_acessos_externos` | id, conversa_id, base (sinan/e-sus), operação, executado_em |

**Mapeamento de status** — vocabulário único entre backend e UI: `bot` → exibe "Aberto"; `fila` e `humano` → "Aguardando" / "Em atendimento"; `encerrada` → "Encerrado". O divisor de handoff é gravado como `mensagens.autor = 'sistema'`, o que o torna auditável e reproduzível no histórico.

Índices de full-text/`pg_trgm` em `faq_intents.padrões`; retenção e anonimização de `mensagens` conforme política LGPD definida com o DPO.

## Análise de trade-offs

O maior tensionamento é **qualidade de geração vs. LGPD**: quanto melhor a geração (LLM externo), maior o cuidado com dados sensíveis. A interface `NLPEngine` plugável resolve o risco de aposta errada — o orquestrador, o handoff, o frontend e o banco não mudam se o motor trocar. A stack fixa (Flask + vanilla JS) limita tempo real a SSE/polling, o que é adequado à escala esperada; WebSocket seria otimização prematura.

## Consequências

- **Fica mais fácil:** trocar o motor NLP no futuro; auditar decisões do bot (confiança gravada por mensagem); atender à LGPD com mascaramento centralizado em um único ponto.
- **Fica mais difícil:** manter duas rotas de NLP (regras + LLM) exige curadoria contínua da base de FAQ.
- **Revisitar quando:** o volume justificar fila dedicada (Redis/RQ) para chamadas ao LLM; ou o Alô Saúde expor API própria de tickets.

## Itens de ação

1. [ ] Validar com jurídico/DPO o envio de texto mascarado a LLM externo (define A3 vs A2)
2. [ ] Especificar a interface `NLPEngine` e implementar A1 (regras + FAQ) como base
3. [ ] Modelar o banco (DDL das 9 tabelas) e configurar `pg_trgm`
4. [ ] Implementar orquestrador + gatilhos de handoff (limiar 0,6 parametrizável) com divisor de sistema na conversa
5. [ ] MVP do frontend (chat + typing-dots + SSE + chips de ação rápida) e painel do atendente
6. [ ] Implementar upload de anexos com validação, antimalware e storage dedicado (Decisão F)
7. [ ] Substituir CNS em texto livre por campo estruturado com validação — pré-requisito do mascaramento de PII
8. [ ] Atualizar `requests` para 2.32.x (Decisão D — resolvida)
9. [ ] Levantar requisitos de credenciamento DATASUS/RNDS para a fase 2 (Decisão E2)
10. [ ] Definir política de retenção/anonimização de mensagens e de anexos clínicos
