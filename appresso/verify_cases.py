"""Script de validación funcional en vivo (Fase 9).

Ejecuta los casos C1 a C6 contra el servidor en vivo o mediante TestClient
con la base de datos real (appresso.db) y genera un reporte estructurado.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
import zoneinfo
from decimal import Decimal

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import SessionLocal
from app.models import Anomalia, EstadoTransaccion, Transaccion, Usuario
from app.services.hash_service import compute_hash

BOGOTA_TZ = zoneinfo.ZoneInfo(settings.timezone)
BASE_URL = "http://127.0.0.1:8000"


def make_payload(id_txn: str, user: str, value: float = 50000.0, payment_method: str = "Tarjeta", alter_hash: bool = False):
    now_bogota = datetime.now(BOGOTA_TZ)
    date_str = now_bogota.strftime("%Y-%m-%dT%H:%M:%S.%f")[:23]
    h = compute_hash(id_txn, user, date_str, f"{value:.2f}", payment_method)
    if alter_hash:
        h = "f" * 64
    return {
        "idTxn": id_txn,
        "user": user,
        "date": date_str,
        "value": value,
        "paymentMethod": payment_method,
        "hash": h,
    }


def run_verification():
    print("=" * 70)
    print("      VELUM - REPORTE DE VALIDACION FUNCIONAL FINAL (FASE 9)")
    print("=" * 70)

    client = httpx.Client(base_url=BASE_URL, timeout=10.0)

    # 0. Restablecer datos de simulación para un inicio limpio y determinista
    client.post("/api/simulator/reset")
    time.sleep(0.5)

    results = {}

    try:
        # C1: Transacción normal de c@c.com -> 201, APROBADA
        p1 = make_payload(f"VAL-C1-{int(time.time()*1000)}", "c@c.com", 65000.0, "Tarjeta")
        r1 = client.post("/api/transacciones", json=p1)
        d1 = r1.json()
        c1_ok = (
            r1.status_code == 201
            and d1.get("transaction", {}).get("status") == "APROBADA"
            and d1.get("analysis", {}).get("anomalyDetected") is False
        )
        results["C1"] = {
            "name": "Transacción normal aislada (c@c.com)",
            "status_code": r1.status_code,
            "status": d1.get("transaction", {}).get("status"),
            "passed": c1_ok,
            "detail": f"Status: {r1.status_code}, Anomaly: {d1.get('analysis', {}).get('anomalyDetected')}",
        }
        print(f"C1: {'[PASS]' if c1_ok else '[FAIL]'} - Status {r1.status_code} ({d1.get('transaction', {}).get('status')})")

        # C2: Segunda de c@c.com fuera de la ventana (> 3.5 segundos) -> APROBADA
        print("   -> Esperando 3.5 segundos para C2 (fuera de ventana)...")
        time.sleep(3.5)
        p2 = make_payload(f"VAL-C2-{int(time.time()*1000)}", "c@c.com", 70000.0, "PSE")
        r2 = client.post("/api/transacciones", json=p2)
        d2 = r2.json()
        c2_ok = (
            r2.status_code == 201
            and d2.get("transaction", {}).get("status") == "APROBADA"
            and d2.get("analysis", {}).get("anomalyDetected") is False
        )
        results["C2"] = {
            "name": "Segunda transacción fuera de ventana (>3s) (c@c.com)",
            "status_code": r2.status_code,
            "status": d2.get("transaction", {}).get("status"),
            "passed": c2_ok,
            "detail": f"Status: {r2.status_code}, Anomaly: {d2.get('analysis', {}).get('anomalyDetected')}",
        }
        print(f"C2: {'[PASS]' if c2_ok else '[FAIL]'} - Status {r2.status_code} ({d2.get('transaction', {}).get('status')})")

        # C3: 3 transacciones de b@b.com en menos de 3s -> POSIBLE_FRAUDE, SOSPECHOSA, fila en anomalias
        c3_txns = []
        c3_responses = []
        for i in range(3):
            p = make_payload(f"VAL-C3-{int(time.time()*1000)}-{i}", "b@b.com", 150000.0 + i * 10000, "Tarjeta")
            res = client.post("/api/transacciones", json=p)
            c3_responses.append(res)
            c3_txns.append(p["idTxn"])
            time.sleep(0.3)

        r3_last = c3_responses[-1]
        d3_last = r3_last.json()
        with SessionLocal() as db_check:
            anomaly_in_db = (
                db_check.query(Anomalia)
                .join(Transaccion)
                .filter(Transaccion.id_txn == c3_txns[-1])
                .first()
            )
            has_anomaly = anomaly_in_db is not None
            anomalia_id = anomaly_in_db.id if anomaly_in_db else None

        c3_ok = (
            r3_last.status_code == 201
            and d3_last.get("transaction", {}).get("status") == "SOSPECHOSA"
            and d3_last.get("analysis", {}).get("anomalyDetected") is True
            and d3_last.get("analysis", {}).get("type") == "POSIBLE_FRAUDE"
            and has_anomaly
        )
        results["C3"] = {
            "name": "Ráfaga de 3 transacciones en < 3s (b@b.com)",
            "status_code": r3_last.status_code,
            "status": d3_last.get("transaction", {}).get("status"),
            "passed": c3_ok,
            "detail": f"Status: {r3_last.status_code}, Anomaly: {d3_last.get('analysis', {}).get('anomalyDetected')}, Fila DB: {has_anomaly}",
        }
        print(f"C3: {'[PASS]' if c3_ok else '[FAIL]'} - Status {r3_last.status_code}, Tipo: {d3_last.get('analysis', {}).get('type')}, Anomalia ID: {anomalia_id}")

        # C4: Usuarios A y B simultáneos -> Ventanas independientes
        u_a = "user_alpha@test.com"
        u_b = "user_beta@test.com"
        time.sleep(3.5)
        # Txn 1 y 2 de A
        client.post("/api/transacciones", json=make_payload(f"VAL-C4-A1-{int(time.time()*1000)}", u_a))
        time.sleep(0.2)
        client.post("/api/transacciones", json=make_payload(f"VAL-C4-A2-{int(time.time()*1000)}", u_a))
        time.sleep(0.2)
        # Txn 1 y 2 de B
        client.post("/api/transacciones", json=make_payload(f"VAL-C4-B1-{int(time.time()*1000)}", u_b))
        time.sleep(0.2)
        r_b2 = client.post("/api/transacciones", json=make_payload(f"VAL-C4-B2-{int(time.time()*1000)}", u_b))
        time.sleep(0.2)
        # Txn 3 de A -> Dispara anomalía SOLO para A
        r_a3 = client.post("/api/transacciones", json=make_payload(f"VAL-C4-A3-{int(time.time()*1000)}", u_a))

        d_b2 = r_b2.json()
        d_a3 = r_a3.json()
        c4_ok = (
            d_b2.get("analysis", {}).get("anomalyDetected") is False
            and d_a3.get("analysis", {}).get("anomalyDetected") is True
            and d_a3.get("analysis", {}).get("transactionCount") == 3
        )
        results["C4"] = {
            "name": "Usuarios A y B simultáneos (ventanas independientes)",
            "passed": c4_ok,
            "detail": f"User A alertado: {d_a3.get('analysis', {}).get('anomalyDetected')}, User B en calma: {d_b2.get('analysis', {}).get('anomalyDetected') is False}",
        }
        print(f"C4: {'[PASS]' if c4_ok else '[FAIL]'} - Ventana User A: count={d_a3.get('analysis', {}).get('transactionCount')}, Ventana User B: anomaly={d_b2.get('analysis', {}).get('anomalyDetected')}")

        # C5: Hash alterado -> 400 Bad Request, no persiste
        tampered_id = f"VAL-C5-TAMPER-{int(time.time()*1000)}"
        p5 = make_payload(tampered_id, "test@hash.com", 10000.0, alter_hash=True)
        r5 = client.post("/api/transacciones", json=p5)
        d5 = r5.json()
        with SessionLocal() as db_check:
            persisted_in_db = db_check.query(Transaccion).filter(Transaccion.id_txn == tampered_id).first()
            is_persisted = persisted_in_db is not None

        c5_ok = (
            r5.status_code == 400
            and d5.get("error", {}).get("code") == "HASH_INVALID"
            and not is_persisted
        )
        results["C5"] = {
            "name": "Hash alterado rechazado sin persistencia",
            "status_code": r5.status_code,
            "passed": c5_ok,
            "detail": f"Status: {r5.status_code}, Error: {d5.get('error', {}).get('code')}, Persistido: {is_persisted}",
        }
        print(f"C5: {'[PASS]' if c5_ok else '[FAIL]'} - Status {r5.status_code}, Codigo: {d5.get('error', {}).get('code')}, Persistido en BD: {is_persisted}")

        # C6: Mismo idTxn dos veces -> 200 con duplicate: true, sin duplicados en BD
        dup_id = f"VAL-C6-DUP-{int(time.time()*1000)}"
        p6 = make_payload(dup_id, "dup.user@test.com", 88000.0, "PSE")
        r6_first = client.post("/api/transacciones", json=p6)
        r6_second = client.post("/api/transacciones", json=p6)
        d6_second = r6_second.json()
        with SessionLocal() as db_check:
            db_count = db_check.query(Transaccion).filter(Transaccion.id_txn == dup_id).count()

        c6_ok = (
            r6_first.status_code == 201
            and r6_second.status_code == 200
            and d6_second.get("duplicate") is True
            and db_count == 1
        )
        results["C6"] = {
            "name": "Mismo idTxn dos veces (Idempotencia)",
            "status_code": r6_second.status_code,
            "passed": c6_ok,
            "detail": f"Primera respuesta: {r6_first.status_code}, Segunda respuesta: {r6_second.status_code}, Duplicate flag: {d6_second.get('duplicate')}, Filas en BD: {db_count}",
        }
        print(f"C6: {'[PASS]' if c6_ok else '[FAIL]'} - Primera: {r6_first.status_code}, Segunda: {r6_second.status_code}, Duplicate: {d6_second.get('duplicate')}, Filas BD: {db_count}")

    finally:
        client.close()

    print("=" * 70)
    all_passed = all(r["passed"] for r in results.values())
    if all_passed:
        print("[EXITO] TODOS LOS CASOS DE VALIDACION (C1-C6) PASARON EXITOSAMENTE.")
    else:
        print("[ADVERTENCIA] ALGUNOS CASOS FALLARON.")
    print("=" * 70)
    return results


if __name__ == "__main__":
    run_verification()
