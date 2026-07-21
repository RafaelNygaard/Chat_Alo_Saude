"""Páginas do frontend (mesma stack: HTML5 + CSS3 + JS ES6 servidos pelo Flask)."""
from flask import Blueprint, render_template

from app.auth import admin_required

bp = Blueprint("pages", __name__)


@bp.get("/")
def chat():
    return render_template("index.html")


@bp.get("/atendente")
def painel_atendente():
    return render_template("atendente.html")


@bp.get("/login")
def login():
    return render_template("login.html")


@bp.get("/admin")
@admin_required
def admin():
    return render_template("admin.html")
