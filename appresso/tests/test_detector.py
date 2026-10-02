"""Pruebas unitarias para el detector de ventana deslizante (Sliding Window)."""
from __future__ import annotations

import concurrent.futures
from datetime import datetime, timedelta, timezone
import zoneinfo

import pytest

from app.config import settings
from app.detector import (
    SlidingWindowDetector,
    calculate_severity,
    get_time_slot_reference,
)

BOGOTA_TZ = zoneinfo.ZoneInfo(settings.timezone)


def test_calculate_severity_thresholds():
    """Valida los umbrales de severidad según el ratio count / reference."""
    # Referencia 10 (mañana)
    assert calculate_severity(count=3, reference=10) == "BAJO"       # 0.3 < 0.5
    assert calculate_severity(count=4, reference=10) == "BAJO"       # 0.4 < 0.5
    assert calculate_severity(count=5, reference=10) == "MEDIO"      # 0.5 >= 0.5 y < 1.0
    assert calculate_severity(count=9, reference=10) == "MEDIO"      # 0.9 < 1.0
    assert calculate_severity(count=10, reference=10) == "ALTO"      # 1.0 >= 1.0 y < 2.0
    assert calculate_severity(count=19, reference=10) == "ALTO"      # 1.9 < 2.0
    assert calculate_severity(count=20, reference=10) == "CRITICO"   # 2.0 >= 2.0

    # Referencia 3 (noche)
    assert calculate_severity(count=3, reference=3) == "ALTO"        # 1.0 >= 1.0 y < 2.0
    assert calculate_severity(count=6, reference=3) == "CRITICO"     # 2.0 >= 2.0


def test_time_slot_reference_bogota():
    """Verifica la asignación de franjas horarias en hora de Bogotá."""
    # Mañana: [05:00, 12:00) -> 10
    dt_5am = datetime(2026, 9, 23, 5, 0, 0, tzinfo=BOGOTA_TZ)
    dt_1159am = datetime(2026, 9, 23, 11, 59, 59, tzinfo=BOGOTA_TZ)
    slot, ref = get_time_slot_reference(dt_5am)
    assert slot == "mañana" and ref == 10
    slot, ref = get_time_slot_reference(dt_1159am)
    assert slot == "mañana" and ref == 10

    # Tarde: [12:00, 20:00) -> 6
    dt_12pm = datetime(2026, 9, 23, 12, 0, 0, tzinfo=BOGOTA_TZ)
    dt_1959pm = datetime(2026, 9, 23, 19, 59, 59, tzinfo=BOGOTA_TZ)
    slot, ref = get_time_slot_reference(dt_12pm)
    assert slot == "tarde" and ref == 6
    slot, ref = get_time_slot_reference(dt_1959pm)
    assert slot == "tarde" and ref == 6

    # Noche: [20:00, 05:00) -> 3
    dt_20pm = datetime(2026, 9, 23, 20, 0, 0, tzinfo=BOGOTA_TZ)
    dt_3am = datetime(2026, 9, 23, 3, 0, 0, tzinfo=BOGOTA_TZ)
    dt_459am = datetime(2026, 9, 23, 4, 59, 59, tzinfo=BOGOTA_TZ)
    slot, ref = get_time_slot_reference(dt_20pm)
    assert slot == "noche" and ref == 3
    slot, ref = get_time_slot_reference(dt_3am)
    assert slot == "noche" and ref == 3
    slot, ref = get_time_slot_reference(dt_459am)
    assert slot == "noche" and ref == 3


def test_sliding_window_one_two_three_transactions():
    """Valida que 1 y 2 transacciones no disparen anomalía, y la tercera sí."""
    clock_time = datetime(2026, 9, 23, 10, 0, 0, tzinfo=timezone.utc)
    det = SlidingWindowDetector(window_seconds=3, threshold=3, clock=lambda: clock_time)

    user = "test@user.com"

    # Transacción 1: t=0.0s
    res1 = det.process(user, clock_time)
    assert res1.anomaly_detected is False
    assert res1.transaction_count == 1

    # Transacción 2: t=1.0s
    res2 = det.process(user, clock_time + timedelta(seconds=1))
    assert res2.anomaly_detected is False
    assert res2.transaction_count == 2

    # Transacción 3: t=2.0s -> Dispara anomalía
    res3 = det.process(user, clock_time + timedelta(seconds=2))
    assert res3.anomaly_detected is True
    assert res3.transaction_count == 3
    assert res3.severity in ["BAJO", "MEDIO", "ALTO", "CRITICO"]
    assert res3.window_start == clock_time
    assert res3.window_end == clock_time + timedelta(seconds=2)


def test_sliding_window_out_of_window():
    """Transacciones separadas por más de 3 segundos no deben disparar anomalía."""
    clock_time = datetime(2026, 9, 23, 10, 0, 0, tzinfo=timezone.utc)
    det = SlidingWindowDetector(window_seconds=3, threshold=3, clock=lambda: clock_time)
    user = "normal@user.com"

    # Txn 1 en t=0s
    r1 = det.process(user, clock_time)
    assert r1.transaction_count == 1
    assert r1.anomaly_detected is False

    # Txn 2 en t=4s (t=0s ya salió de [1s, 4s])
    r2 = det.process(user, clock_time + timedelta(seconds=4))
    assert r2.transaction_count == 1
    assert r2.anomaly_detected is False

    # Txn 3 en t=8s
    r3 = det.process(user, clock_time + timedelta(seconds=8))
    assert r3.transaction_count == 1
    assert r3.anomaly_detected is False


def test_sliding_window_inclusive_boundaries():
    """Límites inclusivos: una transacción en t y otra en t - 3s están ambas en la ventana."""
    t0 = datetime(2026, 9, 23, 10, 0, 0, tzinfo=timezone.utc)
    det = SlidingWindowDetector(window_seconds=3, threshold=3, clock=lambda: t0)
    user = "boundary@user.com"

    # Transacción 1 exactamente en t0
    det.process(user, t0)
    # Transacción 2 en t0 + 1.5s
    det.process(user, t0 + timedelta(seconds=1.5))
    # Transacción 3 exactamente en t0 + 3.0s (diferencia exacta de 3.0s con t0)
    res = det.process(user, t0 + timedelta(seconds=3.0))

    assert res.transaction_count == 3
    assert res.anomaly_detected is True


def test_independent_users():
    """Las transacciones de un usuario no afectan las de otro."""
    t0 = datetime(2026, 9, 23, 10, 0, 0, tzinfo=timezone.utc)
    det = SlidingWindowDetector(window_seconds=3, threshold=3, clock=lambda: t0)

    user_a = "user_a@domain.com"
    user_b = "user_b@domain.com"

    # 2 transacciones de User A
    det.process(user_a, t0)
    det.process(user_a, t0 + timedelta(milliseconds=500))

    # 2 transacciones de User B
    det.process(user_b, t0)
    det.process(user_b, t0 + timedelta(milliseconds=500))

    # Tercera de User A -> Dispara sólo para User A
    res_a = det.process(user_a, t0 + timedelta(seconds=1))
    assert res_a.anomaly_detected is True
    assert res_a.transaction_count == 3

    # Estado de User B sigue en 2
    snapshot_b = det.get_window_snapshot(user_b)
    assert len(snapshot_b) == 2


def test_long_burst():
    """Ráfaga de 6 transacciones en 2 segundos actualiza conteo consecutivamente."""
    # 23:00 hora de Bogotá = franja noche (ref = 3)
    t0_bogota = datetime(2026, 9, 23, 23, 0, 0, tzinfo=BOGOTA_TZ)
    t0 = t0_bogota.astimezone(timezone.utc)
    det = SlidingWindowDetector(window_seconds=3, threshold=3, clock=lambda: t0)
    user = "burst@domain.com"

    results = []
    for i in range(6):
        res = det.process(user, t0 + timedelta(milliseconds=i * 300))
        results.append(res)

    assert [r.transaction_count for r in results] == [1, 2, 3, 4, 5, 6]
    assert [r.anomaly_detected for r in results] == [False, False, True, True, True, True]
    # En la noche (ref 3), con conteo >= 6 el ratio es >= 2.0 -> CRITICO
    assert results[-1].severity == "CRITICO"


def test_detector_concurrency():
    """Múltiples hilos procesando transacciones para el mismo usuario sin condiciones de carrera."""
    t0 = datetime(2026, 9, 23, 10, 0, 0, tzinfo=timezone.utc)
    det = SlidingWindowDetector(window_seconds=10, threshold=3, clock=lambda: t0)
    user = "concurrent@user.com"

    def submit_txn(i: int):
        return det.process(user, t0 + timedelta(milliseconds=i * 10))

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(submit_txn, i) for i in range(20)]
        results = [f.result() for f in futures]

    snapshot = det.get_window_snapshot(user)
    assert len(snapshot) == 20
