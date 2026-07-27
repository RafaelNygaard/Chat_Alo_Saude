"""Endpoints de autenticação e recuperação de senha (ADR-003).

Recuperação por SENHA TEMPORÁRIA: o sistema gera uma senha, marca troca
obrigatória no 1º acesso e a envia por e-mail (modelo configurável no admin).
"""
import re

from flask import Blueprint, current_app, jsonify, request, session
from sqlalchemy import or_
from werkzeug.security import check_password_hash

from app import repositories as repo
from app.db import Session
from app.emailer import enviar_email
from app.models import Usuario

bp = Blueprint("auth_api", __name__)

SENHA_MIN = 6


def _render(template: str, **vars) -> str:
    """Substitui {{chave}} (com ou sem espaços) pelas variáveis dadas."""
    return re.sub(r"\{\{\s*(\w+)\s*\}\}",
                  lambda m: str(vars.get(m.group(1), m.group(0))), template)


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

    # Senha temporária: não abre sessão; o cliente força a troca antes de entrar.
    if u.senha_temporaria:
        return jsonify({"senha_temporaria": True, "usuario_id": u.id, "nome": u.nome})

    session.clear()
    session["usuario_id"] = u.id
    session["papel"] = u.papel
    session["nome"] = u.nome
    return jsonify({"usuario_id": u.id, "nome": u.nome, "papel": u.papel,
                    "senha_temporaria": False})


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


# ----------------------------------------------------- recuperação de senha
@bp.post("/recuperar-senha")
def recuperar_senha():
    """Gera senha temporária e envia por e-mail. Resposta genérica (sem enumeração)."""
    identificador = (request.get_json(force=True).get("identificador") or "").strip()
    if not identificador:
        return jsonify({"erro": "informe e-mail ou matrícula"}), 400

    usuario = repo.usuario_por_identificador(identificador)
    if usuario and usuario.email:
        temp = repo.gerar_senha_temporaria(usuario)
        cfg = repo.obter_config_email()
        corpo = _render(cfg.corpo, username=usuario.nome, senha_temp=temp)
        enviar_email(usuario.email, cfg.assunto, corpo)
    return jsonify({"mensagem": "Se o identificador estiver cadastrado com e-mail, "
                                "enviamos uma senha temporária."})


@bp.post("/trocar-senha")
def trocar_senha():
    """Troca a senha reautenticando com a senha atual (temporária ou não)."""
    d = request.get_json(force=True)
    identificador = (d.get("identificador") or "").strip()
    senha_atual = d.get("senha_atual") or ""
    nova = d.get("nova_senha") or ""
    if len(nova) < SENHA_MIN:
        return jsonify({"erro": f"a nova senha deve ter ao menos {SENHA_MIN} caracteres"}), 400

    u = repo.usuario_por_identificador(identificador)
    if u is None or not u.senha_hash or not check_password_hash(u.senha_hash, senha_atual):
        return jsonify({"erro": "credenciais inválidas"}), 401
    if check_password_hash(u.senha_hash, nova):
        return jsonify({"erro": "a nova senha deve ser diferente da atual"}), 400

    repo.definir_senha(u, nova)
    return jsonify({"ok": True})
