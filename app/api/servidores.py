"""Identificação do servidor ao solicitar atendimento (ADR-003) + combos do popup."""
import re

from flask import Blueprint, jsonify, request

from app import repositories as repo

bp = Blueprint("servidores", __name__)

RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@bp.get("/funcoes")
def listar_funcoes():
    return jsonify(repo.listar_funcoes())


@bp.get("/ubs")
def listar_ubs():
    return jsonify(repo.listar_ubs())


SENHA_MIN = 6


@bp.post("/servidores/identificar")
def identificar():
    d = request.get_json(force=True)
    nome = (d.get("nome") or "").strip()
    email = (d.get("email") or "").strip()
    matricula = (d.get("matricula") or "").strip()
    senha = d.get("senha") or ""
    funcao_id = d.get("funcao_id")
    ubs_id = d.get("ubs_id")

    obrigatorios = {"nome": nome, "email": email, "matricula": matricula,
                    "senha": senha, "funcao_id": funcao_id, "ubs_id": ubs_id}
    faltando = [k for k, v in obrigatorios.items() if not v]
    if faltando:
        return jsonify({"erro": f"campos obrigatórios: {', '.join(faltando)}"}), 400
    if not RE_EMAIL.match(email):
        return jsonify({"erro": "e-mail inválido"}), 400
    if len(senha) < SENHA_MIN:
        return jsonify({"erro": f"a senha deve ter ao menos {SENHA_MIN} caracteres"}), 400

    u, erro = repo.identificar_servidor(nome, email, matricula,
                                        int(funcao_id), int(ubs_id), senha)
    if erro:
        return jsonify({"erro": erro}), 401
    return jsonify({"usuario_id": u.id, "nome": u.nome, "ubs_id": u.ubs_id})
