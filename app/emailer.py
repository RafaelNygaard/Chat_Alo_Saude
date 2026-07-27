"""Envio de e-mail (stdlib smtplib).

A configuração de SMTP vem da tabela config_email (área administrativa); se não
houver host configurado, cai no SMTP do .env e, na ausência dele, registra o
conteúdo no log (modo dev) — o que permite testar sem infraestrutura de e-mail.
"""
import smtplib
from email.message import EmailMessage

from flask import current_app


def _smtp_efetivo() -> dict | None:
    """Config do banco; senão do .env; senão None (fallback de log)."""
    from app import repositories as repo
    cfg = repo.smtp_config()
    if cfg:
        return cfg
    c = current_app.config
    if c.get("SMTP_HOST"):
        return {"host": c["SMTP_HOST"], "port": c["SMTP_PORT"],
                "email": c.get("SMTP_USER") or c["SMTP_FROM"],
                "senha": c.get("SMTP_PASSWORD", "")}
    return None


def _enviar(smtp: dict, destino: str, assunto: str, corpo: str) -> None:
    msg = EmailMessage()
    msg["From"] = smtp["email"]
    msg["To"] = destino
    msg["Subject"] = assunto
    msg.set_content(corpo)
    with smtplib.SMTP(smtp["host"], smtp["port"], timeout=15) as s:
        s.starttls()
        if smtp.get("senha"):
            s.login(smtp["email"], smtp["senha"])
        s.send_message(msg)


def enviar_email(destino: str, assunto: str, corpo: str) -> bool:
    """True se enviou por SMTP; False se caiu no fallback de log (dev)."""
    smtp = _smtp_efetivo()
    if smtp is None:
        current_app.logger.warning(
            "[email:dev] SMTP não configurado — não enviado.\n"
            "  Para: %s\n  Assunto: %s\n  %s", destino, assunto, corpo)
        return False
    try:
        _enviar(smtp, destino, assunto, corpo)
        return True
    except Exception:
        current_app.logger.exception("Falha ao enviar e-mail para %s", destino)
        return False


def testar_conexao(host: str, porta: int, email: str, senha: str) -> tuple[bool, str]:
    """Abre a conexão SMTP e autentica, sem enviar mensagem."""
    try:
        with smtplib.SMTP(host, int(porta), timeout=15) as s:
            s.starttls()
            if senha:
                s.login(email, senha)
        return True, "Conexão e autenticação bem-sucedidas."
    except Exception as exc:  # noqa: BLE001 — reporta a causa ao admin
        return False, f"Falha: {exc}"
