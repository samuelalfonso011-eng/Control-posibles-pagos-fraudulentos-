"""Pruebas para el servicio y endpoints de transacciones (POST /api/transacciones)."""
from __future__ import annotations

import concurrent.futures
from datetime import datetime, timezone
import zoneinfo

import pytest
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Anomalia, EstadoTransaccion, EstadoUsuario, Transaccion, Usuario
from app.services.hash_service import compute_hash

BOGOTA_TZ = zoneinfo.ZoneInfo(settings.timezone)


def _make_payload(
    id_txn: str = "TX-100",
    user: str = "cliente@banco.com",
    date: str | None = None,
    value: float = 50000.0,
    payment_method: str = "Tarjeta",
    alter_hash: bool = False,
) -> dict:
    """Helper para crear payloads con hash SHA-256 válido."""
    if date is None:
        # Usar la hora actual en Bogotá con milisegundos exactos
        now_bogota = datetime.now(BOGOTA_TZ)
        date = now_bogota.strftime("%Y-%m-%dT%H:%M:%S.%f")[:23]

    h = compute_hash(
        id_txn=id_txn,
        user=user,
        date=date,
        value=f"{value:.2f}",
        payment_method=payment_method,
    )
    if alter_hash:
        h = "0" * 64

    return {
        "idTxn": id_txn,
        "user": user,
        "date": date,
        "value": value,
        "paymentMethod": payment_method,
        "hash": h,
    }


def test_create_transaction_valid_201(client, db_session: Session):
    """Transacción válida y aislada responde 201 APROBADA y crea el usuario."""
    payload = _make_payload(id_txn="TX-NEW-1", user="nuevo.usuario@correo.com")
    resp = client.post("/api/transacciones", json=payload)

    assert resp.status_code == 201
    data = resp.json()
    assert data["success"] is True
    assert data["duplicate"] is False
    assert data["transaction"]["idTxn"] == "TX-NEW-1"
    assert data["transaction"]["status"] == "APROBADA"
    assert data["analysis"]["anomalyDetected"] is False

    # Verificar creación de usuario
    user = db_session.query(Usuario).filter(Usuario.email == "nuevo.usuario@correo.com").first()
    assert user is not None
    assert user.nombre == "nuevo.usuario"
    assert user.estado == EstadoUsuario.ACTIVO


def test_create_transaction_existing_user(client, db_session: Session):
    """Transacción asociada a un usuario ya existente en el sistema."""
    user = Usuario(email="existente@banco.com", nombre="Cliente Existente", estado=EstadoUsuario.ACTIVO)
    db_session.add(user)
    db_session.commit()

    payload = _make_payload(id_txn="TX-EXIST-1", user="existente@banco.com")
    resp = client.post("/api/transacciones", json=payload)

    assert resp.status_code == 201
    # Debe asociarse al mismo usuario
    tx = db_session.query(Transaccion).filter(Transaccion.id_txn == "TX-EXIST-1").first()
    assert tx.usuario_id == user.id


def test_create_transaction_invalid_payload_422(client):
    """Payload con campos faltantes o formato de fecha inválido produce 422."""
    # Falta el hash
    resp = client.post("/api/transacciones", json={"idTxn": "TX-1", "user": "a@a.com"})
    assert resp.status_code == 422
    assert resp.json()["success"] is False

    # Fecha con formato incorrecto (sin milisegundos de 3 dígitos)
    bad_payload = _make_payload()
    bad_payload["date"] = "2026-09-23T10:30:00"
    resp = client.post("/api/transacciones", json=bad_payload)
    assert resp.status_code == 422

    # Método de pago no permitido
    bad_payment = _make_payload()
    bad_payment["paymentMethod"] = "Bitcoin"
    resp = client.post("/api/transacciones", json=bad_payment)
    assert resp.status_code == 422


def test_create_transaction_invalid_hash_400(client, db_session: Session):
    """Hash alterado produce 400 y no persiste la transacción en la base de datos."""
    payload = _make_payload(id_txn="TX-TAMPERED", alter_hash=True)
    resp = client.post("/api/transacciones", json=payload)

    assert resp.status_code == 400
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "HASH_INVALID"

    # Verificar que NO se persistió
    tx = db_session.query(Transaccion).filter(Transaccion.id_txn == "TX-TAMPERED").first()
    assert tx is None


def test_create_transaction_duplicate_identical_200(client, db_session: Session):
    """Mismo idTxn y mismo contenido responde 200 con duplicate: true sin crear otra fila."""
    payload = _make_payload(id_txn="TX-DUP-1")

    # Primera vez -> 201
    r1 = client.post("/api/transacciones", json=payload)
    assert r1.status_code == 201

    # Segunda vez idéntica -> 200 duplicate
    r2 = client.post("/api/transacciones", json=payload)
    assert r2.status_code == 200
    data = r2.json()
    assert data["success"] is True
    assert data["duplicate"] is True
    assert data["transaction"]["idTxn"] == "TX-DUP-1"

    # Solo debe existir una fila en BD
    count = db_session.query(Transaccion).filter(Transaccion.id_txn == "TX-DUP-1").count()
    assert count == 1


def test_create_transaction_conflict_409(client):
    """Mismo idTxn con contenido diferente produce 409 Conflict."""
    payload1 = _make_payload(id_txn="TX-CONFLICT", value=10000.0)
    r1 = client.post("/api/transacciones", json=payload1)
    assert r1.status_code == 201

    # Mismo idTxn pero diferente valor -> produce hash distinto
    payload2 = _make_payload(id_txn="TX-CONFLICT", value=20000.0)
    r2 = client.post("/api/transacciones", json=payload2)
    assert r2.status_code == 409
    data = r2.json()
    assert data["success"] is False
    assert data["error"]["code"] == "CONFLICT"


def test_create_transaction_blocked_user_403(client, db_session: Session):
    """Usuario bloqueado persiste transacción como RECHAZADA y responde 403."""
    user = Usuario(email="bloqueado@banco.com", nombre="Bloqueado", estado=EstadoUsuario.BLOQUEADO)
    db_session.add(user)
    db_session.commit()

    payload = _make_payload(id_txn="TX-BLOCKED", user="bloqueado@banco.com")
    resp = client.post("/api/transacciones", json=payload)

    assert resp.status_code == 403
    data = resp.json()
    assert data["success"] is False
    assert "BLOQUEADO" in data["error"]["code"]

    # Debe haberse guardado en BD con estado RECHAZADA
    tx = db_session.query(Transaccion).filter(Transaccion.id_txn == "TX-BLOCKED").first()
    assert tx is not None
    assert tx.estado == EstadoTransaccion.RECHAZADA


def test_attack_simulation_creates_anomaly(client, db_session: Session):
    """Ráfaga de 3 transacciones para el mismo usuario en menos de 3s crea anomalía en BD."""
    user_email = "atacante@banco.com"

    # Txn 1 -> APROBADA
    p1 = _make_payload(id_txn="TX-ATK-1", user=user_email)
    r1 = client.post("/api/transacciones", json=p1)
    assert r1.status_code == 201
    assert r1.json()["transaction"]["status"] == "APROBADA"
    assert r1.json()["analysis"]["anomalyDetected"] is False

    # Txn 2 -> APROBADA
    p2 = _make_payload(id_txn="TX-ATK-2", user=user_email)
    r2 = client.post("/api/transacciones", json=p2)
    assert r2.status_code == 201
    assert r2.json()["transaction"]["status"] == "APROBADA"
    assert r2.json()["analysis"]["anomalyDetected"] is False

    # Txn 3 -> SOSPECHOSA + POSIBLE_FRAUDE
    p3 = _make_payload(id_txn="TX-ATK-3", user=user_email)
    r3 = client.post("/api/transacciones", json=p3)
    assert r3.status_code == 201
    data3 = r3.json()
    assert data3["transaction"]["status"] == "SOSPECHOSA"
    assert data3["analysis"]["anomalyDetected"] is True
    assert data3["analysis"]["type"] == "POSIBLE_FRAUDE"
    assert data3["analysis"]["transactionCount"] == 3

    # Verificar que existe exactamente una anomalía en la tabla anomalias
    anomalias = db_session.query(Anomalia).all()
    assert len(anomalias) == 1
    assert anomalias[0].cantidad_transacciones == 3

    # Txn 4 de la misma ráfaga -> actualiza la anomalía existente, no crea otra
    p4 = _make_payload(id_txn="TX-ATK-4", user=user_email)
    r4 = client.post("/api/transacciones", json=p4)
    assert r4.status_code == 201
    assert r4.json()["transaction"]["status"] == "SOSPECHOSA"

    db_session.expire_all()
    anomalias_after = db_session.query(Anomalia).all()
    assert len(anomalias_after) == 1
    assert anomalias_after[0].cantidad_transacciones == 4


def test_transactions_concurrency_threads(client):
    """Múltiples hilos enviando transacciones con diferentes idTxn de forma simultánea."""
    def send_txn(idx: int):
        payload = _make_payload(id_txn=f"TX-CONC-{idx}", user=f"user_{idx % 3}@test.com")
        return client.post("/api/transacciones", json=payload)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(send_txn, i) for i in range(12)]
        responses = [f.result() for f in futures]

    assert all(r.status_code in [200, 201] for r in responses)
