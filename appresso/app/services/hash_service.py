"""Servicio de hash SHA-256 para validación de integridad de transacciones.

Normalización canónica:
- user: minúsculas, sin espacios
- value: 2 decimales exactos (e.g. "50000.00")
- date: tal como la envía el cliente (ya validada con formato YYYY-MM-DDTHH:MM:SS.mmm)
- paymentMethod: tal cual
- idTxn: tal cual

Hash: SHA-256 de "idTxn|user|date|value|paymentMethod", UTF-8, hex minúsculas.

NOTA DE SEGURIDAD: SHA-256 aquí prueba integridad, no autenticidad.
Un atacante que conozca el algoritmo puede recalcular el hash.
Para autenticación real, usar HMAC con clave compartida (ver README).
"""
from __future__ import annotations

import hashlib
import json
import logging
from decimal import Decimal
from pathlib import Path

logger = logging.getLogger(__name__)

# Ruta a los vectores de prueba compartidos con el simulador JS
HASH_VECTORS_PATH = Path(__file__).resolve().parent.parent.parent / "tests" / "hash_vectors.json"


def normalize_user(user: str) -> str:
    """Normaliza el email del usuario: minúsculas y sin espacios."""
    return user.lower().strip().replace(" ", "")


def normalize_value(value: Decimal | float | str) -> str:
    """Normaliza el valor monetario a exactamente 2 decimales."""
    return f"{Decimal(str(value)):.2f}"


def build_canonical_string(
    id_txn: str,
    user: str,
    date: str,
    value: Decimal | float | str,
    payment_method: str,
) -> str:
    """Construye la cadena canónica para el hash.

    Formato: idTxn|user|date|value|paymentMethod
    """
    normalized = (
        f"{id_txn}"
        f"|{normalize_user(user)}"
        f"|{date}"
        f"|{normalize_value(value)}"
        f"|{payment_method}"
    )
    return normalized


def compute_hash(
    id_txn: str,
    user: str,
    date: str,
    value: Decimal | float | str,
    payment_method: str,
) -> str:
    """Calcula SHA-256 de la cadena canónica.

    Returns:
        Hash hexadecimal en minúsculas (64 caracteres).
    """
    canonical = build_canonical_string(id_txn, user, date, value, payment_method)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return digest


def load_test_vectors() -> list[dict]:
    """Carga los vectores de prueba desde tests/hash_vectors.json."""
    with HASH_VECTORS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)
