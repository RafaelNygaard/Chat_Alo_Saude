"""Autenticação (ADR-003): sessão Flask + hash Werkzeug. Login para papéis com
credencial (admin/atendente). Servidores que solicitam atendimento não logam.

Decisão consciente: sessão em cookie assinado (SECRET_KEY), sem tabela de sessões
— suficiente para a escala do projeto (centenas de usuários, não milhares).
"""
from functools import wraps

from flask import jsonify, redirect, request, session, url_for


def _nao_autenticado():
    if request.path.startswith("/api/"):
        return jsonify({"erro": "não autenticado"}), 401
    return redirect(url_for("pages.login", next=request.path))


def _sem_permissao():
    if request.path.startswith("/api/"):
        return jsonify({"erro": "acesso restrito"}), 403
    return "Acesso restrito a administradores.", 403


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("usuario_id"):
            return _nao_autenticado()
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("usuario_id"):
            return _nao_autenticado()
        if session.get("papel") != "admin":
            return _sem_permissao()
        return f(*args, **kwargs)
    return wrapper
