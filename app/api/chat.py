"""API de chat (Fetch API no frontend) + stream SSE (ADR-001, Decisão C)."""
import json
import time

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context

from app import repositories as repo
from app.models import Conversa, FaqIntent, Mensagem
from app.nlp.rules_engine import RulesEngine
from app.orchestrator.handoff import HandoffManager
from app.orchestrator.orchestrator import EstadoConversa, Orquestrador
from app.db import Session

bp = Blueprint("chat", __name__)


def _msg_json(m: Mensagem) -> dict:
    return {
        "id": m.id, "autor": m.autor, "texto": m.texto,
        "confianca": float(m.confianca_nlp) if m.confianca_nlp is not None else None,
        "criada_em": m.criada_em.isoformat(),
    }


def _montar_orquestrador() -> Orquestrador:
    cfg = current_app.config
    return Orquestrador(
        nlp=RulesEngine(repo.carregar_intents()),
        handoff=HandoffManager(
            repo.SqlHandoffRepository(),
            prazo_sem_atendente_min=cfg["HANDOFF_PRAZO_SEM_ATENDENTE_MIN"],
        ),
        topicos_criticos=repo.carregar_topicos_criticos(),
        limiar_confianca=cfg["HANDOFF_LIMIAR_CONFIANCA"],
        msgs_consecutivas=cfg["HANDOFF_MSGS_CONSECUTIVAS"],
    )


@bp.post("/chat")
def criar_conversa():
    dados = request.get_json(force=True)
    conversa = repo.criar_conversa(
        usuario_id=dados["usuario_id"], assunto=dados.get("assunto")
    )
    return jsonify(
        {"conversa_id": conversa.id, "protocolo": conversa.protocolo,
         "status": Conversa.STATUS_UI[conversa.status]}
    ), 201


@bp.post("/conversas/<int:conversa_id>/mensagens")
def enviar_mensagem(conversa_id: int):
    dados = request.get_json(force=True)
    texto = (dados.get("texto") or "").strip()
    if not texto:
        return jsonify({"erro": "texto vazio"}), 400

    conversa = Session.get(Conversa, conversa_id)
    if conversa is None:
        return jsonify({"erro": "conversa não encontrada"}), 404
    if conversa.status == "encerrada":
        return jsonify({"erro": "conversa encerrada"}), 409

    repo.gravar_mensagem(conversa_id, "usuario", texto)

    # baixa_confianca_consecutivas: contagem reconstruída do fim do histórico
    limiar = current_app.config["HANDOFF_LIMIAR_CONFIANCA"]
    consecutivas = _contar_baixa_confianca(conversa, limiar)
    estado = EstadoConversa(conversa_id=conversa.id, status=conversa.status,
                            baixa_confianca_consecutivas=consecutivas)

    resposta = _montar_orquestrador().processar(estado, texto)

    if resposta.texto:
        repo.gravar_mensagem(conversa_id, resposta.autor, resposta.texto,
                             resposta.confianca)
    # Ex.: no handoff, o aviso do bot vem primeiro e o divisor de sistema depois
    for extra in resposta.mensagens_extra:
        if extra.texto:
            repo.gravar_mensagem(conversa_id, extra.autor, extra.texto,
                                 extra.confianca)
    conversa.status = estado.status
    Session.commit()

    return jsonify(
        {"autor": resposta.autor, "texto": resposta.texto,
         "handoff": resposta.handoff, "gatilho": resposta.gatilho,
         "status": Conversa.STATUS_UI[conversa.status],
         "mensagens_extra": [{"autor": e.autor, "texto": e.texto}
                             for e in resposta.mensagens_extra if e.texto]}
    )


@bp.get("/conversas/<int:conversa_id>/mensagens")
def listar_mensagens(conversa_id: int):
    msgs = (
        Session.query(Mensagem)
        .filter_by(conversa_id=conversa_id)
        .order_by(Mensagem.criada_em)
        .all()
    )
    return jsonify([_msg_json(m) for m in msgs])


@bp.get("/conversas")
def listar_conversas():
    usuario_id = request.args.get("usuario_id", type=int)
    q = Session.query(Conversa).order_by(Conversa.criada_em.desc())
    if usuario_id:
        q = q.filter_by(usuario_id=usuario_id)
    return jsonify([
        {"id": c.id, "protocolo": c.protocolo, "assunto": c.assunto,
         "status": c.status, "status_ui": Conversa.STATUS_UI[c.status],
         "criada_em": c.criada_em.isoformat()}
        for c in q.all()
    ])


@bp.get("/chips")
def listar_chips():
    """Chips de ação rápida: intents com chip_label preenchido."""
    rows = (
        Session.query(FaqIntent)
        .filter(FaqIntent.ativo.is_(True), FaqIntent.chip_label.isnot(None))
        .all()
    )
    return jsonify([
        {"intent": r.intent, "label": r.chip_label,
         "texto": r.padroes.splitlines()[0]}
        for r in rows
    ])


def _encerrar(conversa: Conversa) -> None:
    if conversa.status != "encerrada":
        atendente_id = conversa.atendente_id
        conversa.status = "encerrada"
        Session.commit()
        repo.gravar_mensagem(conversa.id, "sistema", "Atendimento encerrado")
        # Libera o atendente e o envia ao fim da fila (distribuição balanceada)
        if atendente_id:
            repo.liberar_atendente(atendente_id)


@bp.get("/encerramento")
def config_encerramento():
    """Mensagem final configurada no admin (texto/emoji, imagem, cores)."""
    return jsonify(repo.config_encerramento_json(repo.obter_config_encerramento()))


@bp.post("/conversas/<int:conversa_id>/pesquisa")
def responder_pesquisa(conversa_id: int):
    """Registra a pesquisa de satisfação e encerra a conversa."""
    dados = request.get_json(force=True)
    try:
        nota = int(dados.get("nota"))
    except (TypeError, ValueError):
        return jsonify({"erro": "nota obrigatória (1 a 5)"}), 400
    if not 1 <= nota <= 5:
        return jsonify({"erro": "nota deve estar entre 1 e 5"}), 400

    conversa = Session.get(Conversa, conversa_id)
    if conversa is None:
        return jsonify({"erro": "conversa não encontrada"}), 404

    repo.registrar_pesquisa(conversa_id, nota, dados.get("comentario"))
    _encerrar(conversa)
    return jsonify({
        "status": Conversa.STATUS_UI["encerrada"],
        "encerramento": repo.config_encerramento_json(repo.obter_config_encerramento()),
    })


@bp.post("/conversas/<int:conversa_id>/encerrar")
def encerrar_conversa(conversa_id: int):
    """Encerra sem pesquisa (usuário optou por pular)."""
    conversa = Session.get(Conversa, conversa_id)
    if conversa is None:
        return jsonify({"erro": "conversa não encontrada"}), 404
    _encerrar(conversa)
    return jsonify({
        "status": Conversa.STATUS_UI["encerrada"],
        "encerramento": repo.config_encerramento_json(repo.obter_config_encerramento()),
    })


@bp.get("/conversas/<int:conversa_id>/stream")
def stream_mensagens(conversa_id: int):
    """SSE (Decisão C): generator nativo do Flask, unidirecional servidor->cliente.

    Cliente envia ?after=<último id recebido>; EventSource reconecta sozinho
    quando o servidor encerra o ciclo. Fallback trivial: GET /mensagens (polling).
    """
    after = request.args.get("after", default=0, type=int)
    # Numa reconexão o navegador reenvia o último id entregue; ele é mais
    # confiável que o ?after= da URL (que fica congelado no valor inicial).
    ultimo_evento = request.headers.get("Last-Event-ID", "")
    if ultimo_evento.isdigit():
        after = max(after, int(ultimo_evento))

    def gerar(ultimo_id: int):
        # ~25 s por ciclo; depois encerra e o cliente reassina com o id atual
        for _ in range(25):
            Session.expire_all()
            novas = (
                Session.query(Mensagem)
                .filter(Mensagem.conversa_id == conversa_id, Mensagem.id > ultimo_id)
                .order_by(Mensagem.id)
                .all()
            )
            for m in novas:
                ultimo_id = m.id
                # `id:` permite ao cliente retomar exatamente daqui
                yield (f"id: {m.id}\nevent: mensagem\n"
                       f"data: {json.dumps(_msg_json(m))}\n\n")
            conversa = Session.get(Conversa, conversa_id)
            if conversa:
                yield ("event: status\ndata: "
                       f'{json.dumps({"status": conversa.status, "status_ui": Conversa.STATUS_UI[conversa.status]})}\n\n')
            time.sleep(1)
        yield "event: fim_ciclo\ndata: {}\n\n"

    return Response(
        stream_with_context(gerar(after)),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _contar_baixa_confianca(conversa: Conversa, limiar: float) -> int:
    """Conta respostas de bot com confiança < limiar no fim do histórico."""
    n = 0
    for m in reversed(conversa.mensagens):
        if m.autor != "bot":
            continue
        if m.confianca_nlp is not None and float(m.confianca_nlp) < limiar:
            n += 1
        else:
            break
    return n
