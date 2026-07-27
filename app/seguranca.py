"""Criptografia simétrica para segredos guardados no banco (ex.: senha do SMTP).

Usa Fernet com chave derivada da SECRET_KEY da aplicação. Se a SECRET_KEY mudar,
os segredos existentes deixam de ser decifráveis (basta reconfigurá-los).
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


def _fernet() -> Fernet:
    chave = current_app.config["SECRET_KEY"].encode()
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(chave).digest()))


def cifrar(texto: str) -> str:
    return _fernet().encrypt(texto.encode()).decode()


def decifrar(cifrado: str | None) -> str:
    if not cifrado:
        return ""
    try:
        return _fernet().decrypt(cifrado.encode()).decode()
    except (InvalidToken, ValueError):
        return ""
