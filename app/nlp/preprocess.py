"""Pré-processamento de texto (ADR-001: unicodedata + re como pré-processamento,
não como motor principal)."""
import re
import unicodedata


def normalizar(texto: str) -> str:
    """Minúsculas, sem acentos, sem pontuação, espaços colapsados."""
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def tokenizar(texto: str) -> list[str]:
    return normalizar(texto).split()
