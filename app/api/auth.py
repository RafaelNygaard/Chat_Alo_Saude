"""Endpoints de autenticação (ADR-003)."""
from flask import Blueprint, jsonify, request, session
from sqlalchemy import or_
from werkzeug.security import check_password_hash

from app.db import Session
from app.models import Usuario

bp = Blueprint("auth_api", __name__)


@bp.post("/login")
def login():
    d = request.get_json(force=True)
    identificador = (d.get("identificador") or "").strip()  # e-mail ou matrícula
    senha = d.get("senha") or ""
    if not identificador or not senha:
        return jsonify({"erro": "informe identificador e senha"}), 400

    u = (
        Session.query(Usuario)
        .filter(or_(Usuario.email == identificador, Usuario.matricula == identificador))
        .first()
    )
    if u is None or not u.senha_hash or not check_password_hash(u.senha_hash, senha):
        return jsonify({"erro": "credenciais inválidas"}), 401
    if u.papel not in ("admin", "atendente"):
        return jsonify({"erro": "usuário sem acesso ao painel"}), 403

    session.clear()
    session["usuario_id"] = u.id
    session["papel"] = u.papel
    session["nome"] = u.nome
    return jsonify({"usuario_id": u.id, "nome": u.nome, "papel": u.papel})


@bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@bp.get("/sessao")
def sessao():
    if session.get("usuario_id"):
        return jsonify({"usuario_id": session["usuario_id"],
                        "nome": session.get("nome"), "papel": session.get("papel")})
    return jsonify({"erro": "sem sessão"}), 401
