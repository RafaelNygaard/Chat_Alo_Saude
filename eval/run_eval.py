"""Harness de avaliação do motor A1 (RulesEngine) — "treino" do bot de regras.

Mede a acurácia top-1 do matching por trigramas contra o conjunto rotulado
(eval/casos.py) e faz o *sweep* do limiar de confiança usado no handoff
(Decisão B). Serve para curar padrões e escolher HANDOFF_LIMIAR_CONFIANCA.

Uso:
    python -m eval.run_eval            # carrega intents do banco (DATABASE_URL)
    python -m eval.run_eval --sql db/seed_intents.sql   # sem banco, lê do arquivo

Não altera o banco; é somente leitura.
"""
import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Console do Windows costuma ser cp1252; garante saída UTF-8 (acentos e símbolos).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from app.nlp.rules_engine import IntentDef, RulesEngine  # noqa: E402
from eval.casos import CASOS  # noqa: E402

LIMIAR_PROD = float(os.environ.get("HANDOFF_LIMIAR_CONFIANCA", "0.30"))


def _intents_do_banco() -> list[IntentDef]:
    from app import create_app
    from app import repositories as repo

    app = create_app()
    with app.app_context():
        return repo.carregar_intents()


def _intents_do_sql(caminho: Path) -> list[IntentDef]:
    """Parser mínimo dos INSERTs de faq_intents em seed_intents.sql/schema.sql.

    Extrai tuplas (intent, padroes, resposta, ...) delimitadas por E'...'/'...'.
    Suficiente para rodar o harness sem Postgres; não é um parser SQL completo.
    """
    texto = caminho.read_text(encoding="utf-8")
    campo = r"(?:E?'((?:[^']|'')*)')"          # 'string' ou E'string' (com '' escapado)
    tupla = re.compile(
        r"\(\s*" + campo + r"\s*,\s*" + campo + r"\s*,\s*" + campo,
        re.DOTALL,
    )
    intents: list[IntentDef] = []
    for m in tupla.finditer(texto):
        intent, padroes, resposta = (g.replace("''", "'") for g in m.groups())
        padroes = padroes.replace("\\n", "\n")   # E'...\n...' literal -> quebras
        intents.append(IntentDef(
            intent=intent,
            padroes=[p for p in padroes.splitlines() if p.strip()],
            resposta=resposta,
        ))
    return intents


def avaliar(engine: RulesEngine) -> None:
    resultados = []  # (texto, esperado, previsto, confianca)
    for texto, esperado in CASOS:
        ent = engine.entender(texto)
        resultados.append((texto, esperado, ent.intent, ent.confianca))

    in_scope = [r for r in resultados if r[1] is not None]
    negativos = [r for r in resultados if r[1] is None]

    acertos = [r for r in in_scope if r[2] == r[1]]
    print("=" * 72)
    print(f"Intents carregados no motor: {len(engine._intents)}")
    print(f"Casos de teste: {len(resultados)}  (in-scope={len(in_scope)}, negativos={len(negativos)})")
    print("-" * 72)
    print(f"Acurácia top-1 (in-scope): {len(acertos)}/{len(in_scope)} "
          f"= {len(acertos) / len(in_scope):.1%}")
    conf_ok = [r[3] for r in acertos]
    if conf_ok:
        print(f"Confiança média nos acertos: {sum(conf_ok) / len(conf_ok):.3f} "
              f"(min={min(conf_ok):.3f}, max={max(conf_ok):.3f})")

    print("\nErros de classificação (in-scope):")
    erros = [r for r in in_scope if r[2] != r[1]]
    if not erros:
        print("  (nenhum)")
    for texto, esperado, previsto, conf in erros:
        print(f"  [{conf:.3f}] esperado={esperado:<28} previsto={previsto}")
        print(f"          «{texto}»")

    # ---- Sweep do limiar de confiança (Decisão B) ----
    print("\n" + "-" * 72)
    print("Sweep do limiar de confiança (aceitar resposta do bot se confiança >= limiar):")
    print(f"{'limiar':>7} | {'cobertura':>9} | {'precisão':>8} | {'falsos+neg':>10} | recomendação")
    melhor = None
    for i in range(2, 13):
        limiar = i / 20  # 0.10 .. 0.60
        aceitos = [r for r in in_scope if r[3] >= limiar]
        aceitos_ok = [r for r in aceitos if r[2] == r[1]]
        cobertura = len(aceitos) / len(in_scope)
        precisao = (len(aceitos_ok) / len(aceitos)) if aceitos else 1.0
        # negativos aceitos = bot responde quando deveria escalar (ruim)
        falsos_neg = sum(1 for r in negativos if r[3] >= limiar)
        # F-like: prioriza precisão alta mantendo cobertura razoável, penaliza falsos+
        score = precisao * cobertura - 0.1 * falsos_neg
        marca = ""
        if melhor is None or score > melhor[1]:
            melhor = (limiar, score)
        print(f"{limiar:>7.2f} | {cobertura:>8.0%} | {precisao:>7.0%} | "
              f"{falsos_neg:>10} | score={score:.3f}")
    print("-" * 72)
    print(f"Limiar sugerido pelo score: {melhor[0]:.2f}")

    # ---- Ponto de operação no limiar de produção (visão de segurança) ----
    print("\n" + "-" * 72)
    print(f"Ponto de operação em HANDOFF_LIMIAR_CONFIANCA = {LIMIAR_PROD:.2f}")
    certos = [r for r in in_scope if r[3] >= LIMIAR_PROD and r[2] == r[1]]
    errados = [r for r in in_scope if r[3] >= LIMIAR_PROD and r[2] != r[1]]
    escalados = [r for r in in_scope if r[3] < LIMIAR_PROD]
    n = len(in_scope)
    print(f"  In-scope ({n}):")
    print(f"    [OK]      resposta correta : {len(certos):>2}  ({len(certos)/n:.0%})")
    print(f"    [ERRADA]  resposta errada  : {len(errados):>2}  ({len(errados)/n:.0%})   <- risco: bot responde errado")
    print(f"    [HANDOFF] escala p/ humano : {len(escalados):>2}  ({len(escalados)/n:.0%})   <- nao sabe, transfere (seguro)")
    if errados:
        print("    Respostas erradas acima do limiar:")
        for texto, esperado, previsto, conf in errados:
            print(f"      [{conf:.3f}] esperado={esperado} previsto={previsto} :: «{texto}»")
    falsos = [r for r in negativos if r[3] >= LIMIAR_PROD]
    m = len(negativos)
    print(f"  Fora de escopo ({m}):")
    print(f"    [OK]      handoff correto  : {m - len(falsos):>2}  ({(m-len(falsos))/m:.0%})")
    print(f"    [FALSO+]  bot responde     : {len(falsos):>2}  ({len(falsos)/m:.0%})   <- falso positivo")
    if falsos:
        for texto, _esp, previsto, conf in falsos:
            print(f"      [{conf:.3f}] previsto={previsto} :: «{texto}»")
    print("=" * 72)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sql", type=Path, help="Carrega intents de um arquivo .sql em vez do banco")
    args = ap.parse_args()

    if args.sql:
        intents = _intents_do_sql(args.sql)
        print(f"[fonte: {args.sql}]")
    else:
        try:
            intents = _intents_do_banco()
            print("[fonte: banco de dados]")
        except Exception as exc:
            print(f"[banco indisponível: {exc}]\n[fallback: db/seed_intents.sql]")
            intents = _intents_do_sql(ROOT / "db" / "seed_intents.sql")

    avaliar(RulesEngine(intents))


if __name__ == "__main__":
    main()
