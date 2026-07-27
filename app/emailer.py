"""Envio de e-mail (stdlib smtplib).

Sem `SMTP_HOST` configurado, o e-mail não é enviado: o conteúdo é registrado no
log do servidor (modo dev), o que permite testar o fluxo de recuperação sem
infraestrutura de e-mail. Em produção, configurar SMTP_* no .env.
"""
import smtplib
from email.message import EmailMessage

from flask import current_app


def enviar_email(destino: str, assunto: str, corpo: str) -> bool:
    """Retorna True se enviou por SMTP; False se caiu no fallback de log (dev)."""
    cfg = current_app.config
    host = cfg.get("SMTP_HOST")
    if not host:
        current_app.logger.warning(
            "[email:dev] SMTP não configurado — não enviado.\n"
            "  Para: %s\n  Assunto: %s\n  %s", destino, assunto, corpo)
        return False

    msg = EmailMessage()
    msg["From"] = cfg["SMTP_FROM"]
    msg["To"] = destino
    msg["Subject"] = assunto
    msg.set_content(corpo)
    try:
        with smtplib.SMTP(host, cfg["SMTP_PORT"], timeout=15) as s:
            if cfg.get("SMTP_TLS"):
                s.starttls()
            if cfg.get("SMTP_USER"):
                s.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
            s.send_message(msg)
        return True
    except Exception:
        current_app.logger.exception("Falha ao enviar e-mail para %s", destino)
        return False
