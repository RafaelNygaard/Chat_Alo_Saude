# Documentação — Chatbot UBS ↔ Alô Saúde

Este projeto adota **docs as code**: a documentação vive no repositório, é
versionada junto com o código e **atualizada na mesma mudança** que altera
código, schema ou infraestrutura. Uma tarefa só está concluída quando o
registro documental correspondente foi feito.

## Convenção

- **Toda** criação ou alteração relevante (código, `db/`, infra, decisão de
  design) entra no [CHANGELOG](CHANGELOG.md) na mesma tarefa.
- **Decisões de arquitetura** seguem o formato ADR — ver
  [ADR-001](../ADR-001-chatbot-alo-saude.md). Novas decisões viram `ADR-00N`.
- **Procedimentos operacionais** (subir ambiente, treinar, publicar) ficam em
  runbooks nesta pasta.
- Escrever em português, no mesmo tom do ADR-001.
- **LGPD:** nenhuma documentação pode conter PII real (nome de paciente, CPF,
  CNS, telefone, endereço). Usar exemplos genéricos/de-identificados.

## Índice

| Documento | Conteúdo |
|-----------|----------|
| [CHANGELOG.md](CHANGELOG.md) | Histórico cronológico de mudanças (código, schema, infra) |
| [runbook-ambiente-local.md](runbook-ambiente-local.md) | Subir o ambiente de desenvolvimento (Postgres, venv, `.env`, executar) |
| [treinamento-motor-nlp.md](treinamento-motor-nlp.md) | Como "treinar" o motor A1: curar intents, de-identificar, avaliar |
| [ADR-001](../ADR-001-chatbot-alo-saude.md) | Decisão de arquitetura fundadora do projeto |
| [ADR-002](../ADR-002-evolucao-motor-nlp.md) | Evolução do motor NLP: A1 insuficiente (evidência), priorizar A3 |
