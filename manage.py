"""CLI administrativa (ADR-003).

    python manage.py create-admin --nome "Admin" --email admin@pmpc.sp.gov.br --senha SENHA
    python manage.py set-senha --email fulano@... --senha NOVA

Cria/atualiza usuários com credencial de login. A senha é armazenada com hash
(Werkzeug), nunca em texto puro.
"""
import argparse

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import Session
from app.models import Usuario


def _upsert(nome, email, senha, papel, matricula=None):
    app = create_app()
    with app.app_context():
        u = Session.query(Usuario).filter(Usuario.email == email).first()
        if u is None:
            u = Usuario(nome=nome, email=email, matricula=matricula, papel=papel)
            Session.add(u)
        u.nome = nome
        u.papel = papel
        if matricula:
            u.matricula = matricula
        u.senha_hash = generate_password_hash(senha)
        Session.commit()
        print(f"OK: {papel} id={u.id} email={email}")


def main():
    ap = argparse.ArgumentParser(description="Administração do Alô Saúde")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ca = sub.add_parser("create-admin", help="Cria/atualiza um administrador")
    ca.add_argument("--nome", required=True)
    ca.add_argument("--email", required=True)
    ca.add_argument("--senha", required=True)
    ca.add_argument("--matricula")

    ss = sub.add_parser("set-senha", help="Redefine a senha de um usuário")
    ss.add_argument("--email", required=True)
    ss.add_argument("--senha", required=True)

    args = ap.parse_args()
    if args.cmd == "create-admin":
        _upsert(args.nome, args.email, args.senha, "admin", args.matricula)
    elif args.cmd == "set-senha":
        app = create_app()
        with app.app_context():
            u = Session.query(Usuario).filter(Usuario.email == args.email).first()
            if u is None:
                raise SystemExit(f"usuário não encontrado: {args.email}")
            u.senha_hash = generate_password_hash(args.senha)
            Session.commit()
            print(f"OK: senha redefinida para {args.email}")


if __name__ == "__main__":
    main()
