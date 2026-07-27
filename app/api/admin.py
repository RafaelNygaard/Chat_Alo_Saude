"""API da área administrativa (ADR-003). Tudo protegido por admin_required.

Módulos: cadastros (funções, UBS, usuários), gestão do bot (intents, tópicos
críticos), atendentes (disponibilidade) e relatórios (agregações + CSV).
"""
import csv
import io
import os
import time
from datetime import datetime

from flask import Blueprint, Response, current_app, jsonify, request
from sqlalchemy import func
from werkzeug.security import generate_password_hash

from app import repositories as repo
from app.auth import admin_required
from app.db import Session
from app.models import (
    AtendenteStatus, Conversa, FaqIntent, Funcao, Handoff, PesquisaSatisfacao,
    TopicoCritico, UBS, Usuario,
)

bp = Blueprint("admin", __name__)

PAPEIS = ("servidor", "enfermeiro", "atendente", "admin")

# Upload da imagem da mensagem de encerramento (Decisão F do ADR-001: arquivo
# fora do banco, caminho na tabela; tipo e tamanho validados).
EXT_IMAGEM = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
EXT_LOGO = EXT_IMAGEM | {".svg", ".ico"}   # logo aceita também vetor/ícone
TAM_MAX_IMAGEM = 2 * 1024 * 1024  # 2 MB


# ============================================================ Cadastros: funções
@bp.get("/admin/funcoes")
@admin_required
def funcoes_listar():
    rows = Session.query(Funcao).order_by(Funcao.nome).all()
    return jsonify([{"id": f.id, "nome": f.nome, "ativo": f.ativo} for f in rows])


@bp.post("/admin/funcoes")
@admin_required
def funcoes_criar():
    nome = (request.get_json(force=True).get("nome") or "").strip()
    if not nome:
        return jsonify({"erro": "nome obrigatório"}), 400
    if Session.query(Funcao).filter_by(nome=nome).first():
        return jsonify({"erro": "função já existe"}), 409
    f = Funcao(nome=nome)
    Session.add(f)
    Session.commit()
    return jsonify({"id": f.id, "nome": f.nome, "ativo": f.ativo}), 201


@bp.put("/admin/funcoes/<int:fid>")
@admin_required
def funcoes_editar(fid):
    f = Session.get(Funcao, fid)
    if f is None:
        return jsonify({"erro": "não encontrada"}), 404
    d = request.get_json(force=True)
    if "nome" in d and d["nome"].strip():
        f.nome = d["nome"].strip()
    if "ativo" in d:
        f.ativo = bool(d["ativo"])
    Session.commit()
    return jsonify({"id": f.id, "nome": f.nome, "ativo": f.ativo})


# ================================================================ Cadastros: UBS
@bp.get("/admin/ubs")
@admin_required
def ubs_listar():
    rows = Session.query(UBS).order_by(UBS.nome).all()
    return jsonify([{"id": u.id, "nome": u.nome, "municipio": u.municipio} for u in rows])


@bp.post("/admin/ubs")
@admin_required
def ubs_criar():
    d = request.get_json(force=True)
    nome = (d.get("nome") or "").strip()
    municipio = (d.get("municipio") or "").strip()
    if not nome or not municipio:
        return jsonify({"erro": "nome e município obrigatórios"}), 400
    u = UBS(nome=nome, municipio=municipio)
    Session.add(u)
    Session.commit()
    return jsonify({"id": u.id, "nome": u.nome, "municipio": u.municipio}), 201


@bp.put("/admin/ubs/<int:uid>")
@admin_required
def ubs_editar(uid):
    u = Session.get(UBS, uid)
    if u is None:
        return jsonify({"erro": "não encontrada"}), 404
    d = request.get_json(force=True)
    if d.get("nome"):
        u.nome = d["nome"].strip()
    if d.get("municipio"):
        u.municipio = d["municipio"].strip()
    Session.commit()
    return jsonify({"id": u.id, "nome": u.nome, "municipio": u.municipio})


# =========================================================== Cadastros: usuários
def _usuario_json(u: Usuario) -> dict:
    return {"id": u.id, "nome": u.nome, "email": u.email, "matricula": u.matricula,
            "papel": u.papel, "funcao_id": u.funcao_id, "ubs_id": u.ubs_id,
            "tem_senha": bool(u.senha_hash)}


@bp.get("/admin/usuarios")
@admin_required
def usuarios_listar():
    q = Session.query(Usuario)
    papel = request.args.get("papel")
    if papel:
        q = q.filter_by(papel=papel)
    return jsonify([_usuario_json(u) for u in q.order_by(Usuario.nome).all()])


@bp.post("/admin/usuarios")
@admin_required
def usuarios_criar():
    d = request.get_json(force=True)
    nome = (d.get("nome") or "").strip()
    papel = d.get("papel")
    if not nome or papel not in PAPEIS:
        return jsonify({"erro": f"nome e papel ({PAPEIS}) obrigatórios"}), 400
    u = Usuario(nome=nome, email=(d.get("email") or "").strip() or None,
                matricula=(d.get("matricula") or "").strip() or None,
                papel=papel, funcao_id=d.get("funcao_id"), ubs_id=d.get("ubs_id"))
    if d.get("senha"):
        u.senha_hash = generate_password_hash(d["senha"])
    Session.add(u)
    Session.commit()
    return jsonify(_usuario_json(u)), 201


@bp.put("/admin/usuarios/<int:uid>")
@admin_required
def usuarios_editar(uid):
    u = Session.get(Usuario, uid)
    if u is None:
        return jsonify({"erro": "não encontrado"}), 404
    d = request.get_json(force=True)
    for campo in ("nome", "email", "matricula"):
        if campo in d:
            setattr(u, campo, (d[campo] or "").strip() or None)
    if d.get("papel") in PAPEIS:
        u.papel = d["papel"]
    if "funcao_id" in d:
        u.funcao_id = d["funcao_id"]
    if "ubs_id" in d:
        u.ubs_id = d["ubs_id"]
    if d.get("senha"):
        u.senha_hash = generate_password_hash(d["senha"])
    Session.commit()
    return jsonify(_usuario_json(u))


# ============================================================ Bot: faq_intents
def _intent_json(i: FaqIntent) -> dict:
    return {"id": i.id, "intent": i.intent, "padroes": i.padroes,
            "resposta": i.resposta, "chip_label": i.chip_label, "ativo": i.ativo}


@bp.get("/admin/intents")
@admin_required
def intents_listar():
    rows = Session.query(FaqIntent).order_by(FaqIntent.intent).all()
    return jsonify([_intent_json(i) for i in rows])


@bp.post("/admin/intents")
@admin_required
def intents_criar():
    d = request.get_json(force=True)
    intent = (d.get("intent") or "").strip()
    padroes = (d.get("padroes") or "").strip()
    resposta = (d.get("resposta") or "").strip()
    if not intent or not padroes or not resposta:
        return jsonify({"erro": "intent, padroes e resposta obrigatórios"}), 400
    if Session.query(FaqIntent).filter_by(intent=intent).first():
        return jsonify({"erro": "intent já existe"}), 409
    i = FaqIntent(intent=intent, padroes=padroes, resposta=resposta,
                  chip_label=(d.get("chip_label") or "").strip() or None,
                  ativo=bool(d.get("ativo", True)))
    Session.add(i)
    Session.commit()
    return jsonify(_intent_json(i)), 201


@bp.put("/admin/intents/<int:iid>")
@admin_required
def intents_editar(iid):
    i = Session.get(FaqIntent, iid)
    if i is None:
        return jsonify({"erro": "não encontrado"}), 404
    d = request.get_json(force=True)
    for campo in ("padroes", "resposta"):
        if d.get(campo):
            setattr(i, campo, d[campo].strip())
    if "chip_label" in d:
        i.chip_label = (d["chip_label"] or "").strip() or None
    if "ativo" in d:
        i.ativo = bool(d["ativo"])
    Session.commit()
    return jsonify(_intent_json(i))


@bp.delete("/admin/intents/<int:iid>")
@admin_required
def intents_remover(iid):
    i = Session.get(FaqIntent, iid)
    if i is None:
        return jsonify({"erro": "não encontrado"}), 404
    Session.delete(i)
    Session.commit()
    return jsonify({"ok": True})


# ======================================================== Bot: tópicos críticos
@bp.get("/admin/topicos")
@admin_required
def topicos_listar():
    rows = Session.query(TopicoCritico).order_by(TopicoCritico.termo).all()
    return jsonify([{"id": t.id, "termo": t.termo, "ativo": t.ativo} for t in rows])


@bp.post("/admin/topicos")
@admin_required
def topicos_criar():
    termo = (request.get_json(force=True).get("termo") or "").strip().lower()
    if not termo:
        return jsonify({"erro": "termo obrigatório"}), 400
    if Session.query(TopicoCritico).filter_by(termo=termo).first():
        return jsonify({"erro": "termo já existe"}), 409
    t = TopicoCritico(termo=termo)
    Session.add(t)
    Session.commit()
    return jsonify({"id": t.id, "termo": t.termo, "ativo": t.ativo}), 201


@bp.put("/admin/topicos/<int:tid>")
@admin_required
def topicos_editar(tid):
    t = Session.get(TopicoCritico, tid)
    if t is None:
        return jsonify({"erro": "não encontrado"}), 404
    d = request.get_json(force=True)
    if "ativo" in d:
        t.ativo = bool(d["ativo"])
    Session.commit()
    return jsonify({"id": t.id, "termo": t.termo, "ativo": t.ativo})


@bp.delete("/admin/topicos/<int:tid>")
@admin_required
def topicos_remover(tid):
    t = Session.get(TopicoCritico, tid)
    if t is None:
        return jsonify({"erro": "não encontrado"}), 404
    Session.delete(t)
    Session.commit()
    return jsonify({"ok": True})


# =============================================================== Atendentes
@bp.get("/admin/atendentes")
@admin_required
def atendentes_listar():
    rows = (
        Session.query(Usuario, AtendenteStatus)
        .outerjoin(AtendenteStatus, AtendenteStatus.atendente_id == Usuario.id)
        .filter(Usuario.papel == "atendente")
        .order_by(Usuario.nome)
        .all()
    )
    return jsonify([
        {"id": u.id, "nome": u.nome, "email": u.email,
         "status": (s.status if s else "ausente")}
        for u, s in rows
    ])


@bp.post("/admin/atendentes/<int:aid>/status")
@admin_required
def atendentes_status(aid):
    from datetime import datetime
    status = (request.get_json(force=True).get("status") or "").strip()
    if status not in ("disponivel", "ocupado", "ausente"):
        return jsonify({"erro": "status inválido"}), 400
    row = Session.get(AtendenteStatus, aid)
    if row is None:
        row = AtendenteStatus(atendente_id=aid)
        Session.add(row)
    row.status = status
    row.atualizado_em = datetime.utcnow()
    Session.commit()
    return jsonify({"atendente_id": aid, "status": status})


# ==================================================== Cabeçalho / identidade
@bp.get("/admin/cabecalho")
@admin_required
def cabecalho_obter():
    return jsonify(repo.config_cabecalho_json(repo.obter_config_cabecalho()))


@bp.put("/admin/cabecalho")
@admin_required
def cabecalho_salvar():
    d = request.get_json(force=True)
    cfg = repo.obter_config_cabecalho()
    for campo, chave in (("titulo", "titulo"), ("subtitulo", "subtitulo"),
                         ("orgao", "orgao"), ("cor_fundo", "cor_fundo")):
        valor = (d.get(chave) or "").strip()
        if valor:
            setattr(cfg, campo, valor)
    if "logo" in d:                       # None/"" volta ao "+" padrão
        cfg.logo_caminho = d["logo"] or None
    cfg.atualizado_em = datetime.utcnow()
    Session.commit()
    return jsonify(repo.config_cabecalho_json(cfg))


@bp.post("/admin/cabecalho/logo")
@admin_required
def cabecalho_logo():
    arquivo = request.files.get("logo")
    if arquivo is None or not arquivo.filename:
        return jsonify({"erro": "envie um arquivo de imagem"}), 400
    ext = os.path.splitext(arquivo.filename)[1].lower()
    if ext not in EXT_LOGO:
        return jsonify({"erro": f"formato não suportado ({', '.join(sorted(EXT_LOGO))})"}), 400
    dados = arquivo.read()
    if len(dados) > TAM_MAX_IMAGEM:
        return jsonify({"erro": "imagem acima de 2 MB"}), 400

    destino = os.path.join(current_app.static_folder, "uploads")
    os.makedirs(destino, exist_ok=True)
    nome = f"logo_{int(time.time())}{ext}"     # nome gerado, nunca o do usuário
    with open(os.path.join(destino, nome), "wb") as saida:
        saida.write(dados)

    cfg = repo.obter_config_cabecalho()
    cfg.logo_caminho = f"/static/uploads/{nome}"
    cfg.atualizado_em = datetime.utcnow()
    Session.commit()
    return jsonify({"logo": cfg.logo_caminho})


# ============================================== Servidor de e-mail (SMTP)
@bp.get("/admin/email")
@admin_required
def email_obter():
    return jsonify(repo.config_email_json(repo.obter_config_email()))


@bp.put("/admin/email")
@admin_required
def email_salvar():
    d = request.get_json(force=True)
    if not (d.get("assunto") or "").strip() or not (d.get("corpo") or "").strip():
        return jsonify({"erro": "assunto e corpo são obrigatórios"}), 400
    cfg = repo.salvar_config_email(
        host=d.get("host"), porta=d.get("porta"), email=d.get("email"),
        assunto=d.get("assunto"), corpo=d.get("corpo"),
        senha=d.get("senha"),   # só troca a senha se enviada
    )
    return jsonify(repo.config_email_json(cfg))


@bp.post("/admin/email/testar")
@admin_required
def email_testar():
    from app.emailer import testar_conexao
    d = request.get_json(force=True)
    host = (d.get("host") or "").strip()
    if not host:
        return jsonify({"ok": False, "mensagem": "informe o host do servidor"}), 400
    # senha digitada agora tem prioridade; senão usa a que está guardada (cifrada)
    smtp = repo.smtp_config(senha_em_claro=d.get("senha") or None) or {}
    senha = d.get("senha") or smtp.get("senha", "")
    ok, mensagem = testar_conexao(host, d.get("porta") or 587,
                                  (d.get("email") or "").strip(), senha)
    return jsonify({"ok": ok, "mensagem": mensagem})


# ============================================== Mensagem de encerramento
@bp.get("/admin/encerramento")
@admin_required
def encerramento_obter():
    return jsonify(repo.config_encerramento_json(repo.obter_config_encerramento()))


@bp.put("/admin/encerramento")
@admin_required
def encerramento_salvar():
    d = request.get_json(force=True)
    texto = (d.get("texto") or "").strip()
    if not texto:
        return jsonify({"erro": "o texto da mensagem é obrigatório"}), 400

    cfg = repo.obter_config_encerramento()
    cfg.texto = texto
    if d.get("cor_fundo"):
        cfg.cor_fundo = d["cor_fundo"]
    if d.get("cor_texto"):
        cfg.cor_texto = d["cor_texto"]
    if "imagem_como_fundo" in d:
        cfg.imagem_como_fundo = bool(d["imagem_como_fundo"])
    if "imagem" in d:                       # None/"" remove a imagem
        cfg.imagem_caminho = d["imagem"] or None
    cfg.atualizado_em = datetime.utcnow()
    Session.commit()
    return jsonify(repo.config_encerramento_json(cfg))


@bp.post("/admin/encerramento/imagem")
@admin_required
def encerramento_imagem():
    arquivo = request.files.get("imagem")
    if arquivo is None or not arquivo.filename:
        return jsonify({"erro": "envie um arquivo de imagem"}), 400
    ext = os.path.splitext(arquivo.filename)[1].lower()
    if ext not in EXT_IMAGEM:
        return jsonify({"erro": f"formato não suportado ({', '.join(sorted(EXT_IMAGEM))})"}), 400
    dados = arquivo.read()
    if len(dados) > TAM_MAX_IMAGEM:
        return jsonify({"erro": "imagem acima de 2 MB"}), 400

    destino = os.path.join(current_app.static_folder, "uploads")
    os.makedirs(destino, exist_ok=True)
    nome = f"encerramento_{int(time.time())}{ext}"   # nome gerado, não o do usuário
    with open(os.path.join(destino, nome), "wb") as saida:
        saida.write(dados)

    cfg = repo.obter_config_encerramento()
    cfg.imagem_caminho = f"/static/uploads/{nome}"
    cfg.atualizado_em = datetime.utcnow()
    Session.commit()
    return jsonify({"imagem": cfg.imagem_caminho})


# =============================================================== Relatórios
def _filtro_periodo(q):
    de, ate = request.args.get("de"), request.args.get("ate")
    if de:
        q = q.filter(Conversa.criada_em >= de)
    if ate:
        q = q.filter(Conversa.criada_em <= ate + " 23:59:59")
    return q


@bp.get("/admin/relatorios/atendimentos")
@admin_required
def rel_atendimentos():
    base = _filtro_periodo(Session.query(Conversa))
    total = base.count()

    por_status = dict(
        _filtro_periodo(Session.query(Conversa.status, func.count()))
        .group_by(Conversa.status).all()
    )
    por_ubs = dict(
        _filtro_periodo(Session.query(UBS.nome, func.count(Conversa.id)))
        .select_from(Conversa)
        .join(Usuario, Usuario.id == Conversa.usuario_id)
        .join(UBS, UBS.id == Usuario.ubs_id)
        .group_by(UBS.nome).all()
    )
    por_funcao = dict(
        _filtro_periodo(Session.query(Funcao.nome, func.count(Conversa.id)))
        .select_from(Conversa)
        .join(Usuario, Usuario.id == Conversa.usuario_id)
        .join(Funcao, Funcao.id == Usuario.funcao_id)
        .group_by(Funcao.nome).all()
    )
    hq = Session.query(Handoff.gatilho, func.count()).join(
        Conversa, Conversa.id == Handoff.conversa_id)
    de, ate = request.args.get("de"), request.args.get("ate")
    if de:
        hq = hq.filter(Conversa.criada_em >= de)
    if ate:
        hq = hq.filter(Conversa.criada_em <= ate + " 23:59:59")
    por_gatilho = dict(hq.group_by(Handoff.gatilho).all())

    # Satisfação (CSAT) das conversas do período
    media, respostas = (
        _filtro_periodo(
            Session.query(func.avg(PesquisaSatisfacao.nota),
                          func.count(PesquisaSatisfacao.id))
            .select_from(Conversa)
            .join(PesquisaSatisfacao, PesquisaSatisfacao.conversa_id == Conversa.id)
        ).one()
    )
    distribuicao = dict(
        _filtro_periodo(
            Session.query(PesquisaSatisfacao.nota, func.count())
            .select_from(Conversa)
            .join(PesquisaSatisfacao, PesquisaSatisfacao.conversa_id == Conversa.id)
        ).group_by(PesquisaSatisfacao.nota).all()
    )

    return jsonify({
        "total": total,
        "por_status": {Conversa.STATUS_UI.get(k, k): v for k, v in por_status.items()},
        "por_ubs": por_ubs,
        "por_funcao": por_funcao,
        "handoffs_por_gatilho": por_gatilho,
        "satisfacao": {
            "media": round(float(media), 2) if media is not None else None,
            "respostas": respostas,
            "distribuicao": {str(k): v for k, v in distribuicao.items()},
        },
    })


@bp.get("/admin/relatorios/atendimentos.csv")
@admin_required
def rel_atendimentos_csv():
    rows = (
        _filtro_periodo(
            Session.query(Conversa, Usuario, UBS, Funcao)
            .join(Usuario, Usuario.id == Conversa.usuario_id)
            .outerjoin(UBS, UBS.id == Usuario.ubs_id)
            .outerjoin(Funcao, Funcao.id == Usuario.funcao_id)
        )
        .order_by(Conversa.criada_em)
        .all()
    )
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["protocolo", "status", "criada_em", "servidor", "email",
                "funcao", "unidade", "assunto"])
    for c, u, ubs, funcao in rows:
        w.writerow([c.protocolo, Conversa.STATUS_UI.get(c.status, c.status),
                    c.criada_em.isoformat(), u.nome, u.email or "",
                    funcao.nome if funcao else "", ubs.nome if ubs else "",
                    c.assunto or ""])
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=atendimentos.csv"},
    )
