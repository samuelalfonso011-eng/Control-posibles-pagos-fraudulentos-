"""Módulo de seguridad: utilidades para comparación segura de hashes."""
from __future__ import annotations

import hmac


def safe_compare(a: str, b: str) -> bool:
    """Compara dos strings de forma segura ante timing attacks.

    Usa `hmac.compare_digest` tal como especifica el diseño.
    """
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
