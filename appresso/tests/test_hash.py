"""Pruebas unitarias para el cálculo de hash canónico y servicio de seguridad."""
from __future__ import annotations

import json
from pathlib import Path
from decimal import Decimal

import pytest

from app.security import safe_compare
from app.services.hash_service import (
    build_canonical_string,
    compute_hash,
    load_test_vectors,
    normalize_user,
    normalize_value,
)


def test_hash_vectors_against_spec():
    """Valida los vectores de prueba oficiales contra compute_hash."""
    vectors = load_test_vectors()
    assert len(vectors) >= 5, "Deben existir al menos 5 vectores de prueba"

    for vec in vectors:
        inp = vec["input"]
        expected_canonical = vec["canonicalString"]
        expected_hash = vec["expectedHash"]

        # Validar generación de cadena canónica
        actual_canonical = build_canonical_string(
            id_txn=inp["idTxn"],
            user=inp["user"],
            date=inp["date"],
            value=inp["value"],
            payment_method=inp["paymentMethod"],
        )
        assert actual_canonical == expected_canonical, (
            f"Fallo en cadena canónica para {vec['description']}: "
            f"esperado='{expected_canonical}', obtenido='{actual_canonical}'"
        )

        # Validar cálculo de hash
        actual_hash = compute_hash(
            id_txn=inp["idTxn"],
            user=inp["user"],
            date=inp["date"],
            value=inp["value"],
            payment_method=inp["paymentMethod"],
        )
        assert actual_hash == expected_hash, (
            f"Fallo en hash para {vec['description']}: "
            f"esperado='{expected_hash}', obtenido='{actual_hash}'"
        )


def test_user_normalization():
    """Verifica que el usuario se normalice a minúsculas y sin espacios."""
    assert normalize_user(" USER@Example.COM ") == "user@example.com"
    assert normalize_user("Us er @ Domain .com") == "user@domain.com"
    assert normalize_user("test@bank.co") == "test@bank.co"


def test_value_normalization():
    """Verifica que el valor monetario tenga exactamente 2 decimales."""
    assert normalize_value(50000) == "50000.00"
    assert normalize_value("50000") == "50000.00"
    assert normalize_value("50000.5") == "50000.50"
    assert normalize_value(Decimal("123.45")) == "123.45"
    assert normalize_value("10.00") == "10.00"


def test_hash_tamper_detection():
    """Cualquier alteración en los campos debe producir un hash diferente."""
    h1 = compute_hash("TX-1", "user@a.com", "2026-09-23T10:00:00.000", "100.00", "Tarjeta")
    # Modificar id
    h2 = compute_hash("TX-2", "user@a.com", "2026-09-23T10:00:00.000", "100.00", "Tarjeta")
    # Modificar fecha por 1 ms
    h3 = compute_hash("TX-1", "user@a.com", "2026-09-23T10:00:00.001", "100.00", "Tarjeta")
    # Modificar valor por 1 centavo
    h4 = compute_hash("TX-1", "user@a.com", "2026-09-23T10:00:00.000", "100.01", "Tarjeta")
    # Modificar método de pago
    h5 = compute_hash("TX-1", "user@a.com", "2026-09-23T10:00:00.000", "100.00", "PSE")

    assert len({h1, h2, h3, h4, h5}) == 5


def test_safe_compare():
    """Prueba la comparación resistente a timing attacks con hmac.compare_digest."""
    assert safe_compare("abc123def", "abc123def") is True
    assert safe_compare("abc123def", "abc123deg") is False
    assert safe_compare("abc", "abcd") is False
