"""Endpoints de autenticação e recuperação de senha (ADR-003)."""
from flask import Blueprint, current_app, jsonify, request, session
from sqlalchemy import or_
from werkzeug.security import check_password_hash

from app import repositories as repo
from app.db import Session
from app.emailer import enviar_email
from app.models import Usuario

bp = Blueprint("auth_api", __name__)

SENHA_MIN = 6


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


# ----------------------------------------------------- recuperação de senha
@bp.post("/recuperar-senha")
def recuperar_senha():
    """Solicita o link de recuperação. Resposta genérica (não revela cadastro)."""
    identificador = (request.get_json(force=True).get("identificador") or "").strip()
    if not identificador:
        return jsonify({"erro": "informe e-mail ou matrícula"}), 400

    usuario = repo.usuario_por_identificador(identificador)
    if usuario and usuario.email:
        ttl = current_app.config["RECUPERACAO_TTL_MIN"]
        token = repo.criar_token_recuperacao(usuario.id, ttl)
        base = current_app.config["APP_BASE_URL"].rstrip("/")
        link = f"{base}/recuperar-senha?token={token}"
        enviar_email(
            usuario.email, "Recuperação de senha — Alô Saúde",
            f"Olá, {usuario.nome}.\n\n"
            "Recebemos um pedido para redefinir sua senha no Alô Saúde. "
            f"Acesse o link abaixo (válido por {ttl} minutos):\n\n{link}\n\n"
            "Se você não fez essa solicitação, ignore este e-mail.",
        )
    # Mesma resposta exista ou não o usuário — evita enumeração de contas.
    return jsonify({"mensagem": "Se o identificador estiver cadastrado com e-mail, "
                                "enviamos as instruções de recuperação."})


@bp.get("/recuperar-senha/validar")
def validar_token_recuperacao():
    token = (request.args.get("token") or "").strip()
    return jsonify({"valido": bool(token and repo.token_recuperacao_valido(token))})


@bp.post("/redefinir-senha")
def redefinir_senha():
    dados = request.get_json(force=True)
    token = (dados.get("token") or "").strip()
    senha = dados.get("senha") or ""
    if len(senha) < SENHA_MIN:
        return jsonify({"erro": f"a senha deve ter ao menos {SENHA_MIN} caracteres"}), 400
    if not repo.redefinir_senha_por_token(token, senha):
        return jsonify({"erro": "link inválido ou expirado — solicite um novo"}), 400
    return jsonify({"mensagem": "Senha redefinida com sucesso."})
