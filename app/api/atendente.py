"""Painel do atendente (ADR-001): fila, disponibilidade, assumir e responder."""
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app import repositories as repo
from app.db import Session
from app.models import AtendenteStatus, Conversa, Handoff, Usuario

bp = Blueprint("atendente", __name__)

STATUS_VALIDOS = ("disponivel", "ocupado", "ausente")


@bp.get("/atendente/fila")
def fila():
    """Conversas aguardando humano, mais antigas primeiro."""
    rows = (
        Session.query(Conversa, Handoff)
        .join(Handoff, Handoff.conversa_id == Conversa.id)
        .filter(Conversa.status == "fila", Handoff.resolvido_em.is_(None))
        .order_by(Handoff.criado_em)
        .all()
    )
    agora = datetime.now(timezone.utc)
    return jsonify([
        {"conversa_id": c.id, "protocolo": c.protocolo, "assunto": c.assunto,
         "gatilho": h.gatilho,
         "espera_min": int((agora - h.criado_em).total_seconds() // 60)
         if h.criado_em.tzinfo else
         int((datetime.utcnow() - h.criado_em).total_seconds() // 60)}
        for c, h in rows
    ])


@bp.get("/atendente/<int:atendente_id>/conversas")
def minhas_conversas(atendente_id: int):
    rows = (
        Session.query(Conversa)
        .filter_by(atendente_id=atendente_id, status="humano")
        .order_by(Conversa.criada_em.desc())
        .all()
    )
    return jsonify([
        {"id": c.id, "protocolo": c.protocolo, "assunto": c.assunto,
         "status_ui": Conversa.STATUS_UI[c.status]}
        for c in rows
    ])


@bp.post("/atendente/<int:atendente_id>/status")
def definir_status(atendente_id: int):
    status = (request.get_json(force=True).get("status") or "").strip()
    if status not in STATUS_VALIDOS:
        return jsonify({"erro": f"status deve ser um de {STATUS_VALIDOS}"}), 400
    row = Session.get(AtendenteStatus, atendente_id)
    if row is None:
        row = AtendenteStatus(atendente_id=atendente_id)
        Session.add(row)
    row.status = status
    row.atualizado_em = datetime.utcnow()
    Session.commit()
    return jsonify({"atendente_id": atendente_id, "status": status})


@bp.post("/conversas/<int:conversa_id>/assumir")
def assumir(conversa_id: int):
    atendente_id = request.get_json(force=True).get("atendente_id")
    conversa = Session.get(Conversa, conversa_id)
    atendente = Session.get(Usuario, atendente_id) if atendente_id else None
    if conversa is None or atendente is None:
        return jsonify({"erro": "conversa ou atendente não encontrado"}), 404
    if conversa.status == "encerrada":
        return jsonify({"erro": "conversa encerrada"}), 409

    repo.SqlHandoffRepository().atribuir(conversa_id, atendente_id)
    # Divisor visível na conversa (ADR): "Transferido para Agente X — hh:mm"
    hora = datetime.now().strftime("%H:%M")
    repo.gravar_mensagem(
        conversa_id, "sistema", f"Transferido para Agente {atendente.nome} — {hora}"
    )
    return jsonify({"conversa_id": conversa_id,
                    "atendente": atendente.nome,
                    "status_ui": Conversa.STATUS_UI["humano"]})


@bp.post("/conversas/<int:conversa_id>/responder")
def responder(conversa_id: int):
    dados = request.get_json(force=True)
    texto = (dados.get("texto") or "").strip()
    if not texto:
        return jsonify({"erro": "texto vazio"}), 400
    conversa = Session.get(Conversa, conversa_id)
    if conversa is None:
        return jsonify({"erro": "conversa não encontrada"}), 404
    if conversa.status != "humano":
        return jsonify({"erro": "conversa não está em atendimento humano"}), 409
    msg = repo.gravar_mensagem(conversa_id, "atendente", texto)
    return jsonify({"id": msg.id}), 201
