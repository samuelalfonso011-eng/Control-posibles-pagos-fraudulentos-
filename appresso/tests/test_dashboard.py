"""Pruebas para los endpoints del Dashboard de VELUM."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import zoneinfo

import pytest
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    Anomalia,
    EstadoRevision,
    EstadoTransaccion,
    EstadoUsuario,
    MetodoPago,
    NivelAnomalia,
    TipoAnomalia,
    Transaccion,
    Usuario,
)

BOGOTA_TZ = zoneinfo.ZoneInfo(settings.timezone)


def test_dashboard_stats_empty(client):
    """Consulta de estadísticas sin datos en la base de datos retorna métricas en cero."""
    resp = client.get("/api/dashboard/stats?periodo=hoy")
    assert resp.status_code == 200
    data = resp.json()

    assert data["periodo"] == "hoy"
    assert data["by_status"]["total"] == 0
    assert data["by_status"]["aprobadas"] == 0
    assert data["by_status"]["sospechosas"] == 0
    assert data["by_status"]["rechazadas"] == 0
    assert data["anomalias"]["total"] == 0
    assert data["anomalias"]["porcentaje"] == 0.0
    assert data["anomalias"]["monto_sospechoso"] == "0.00"
    assert data["anomalias"]["usuarios_afectados"] == 0
    assert data["anomalias"]["recurrentes"] == 0
    assert len(data["by_hour"]) == 24
    assert data["by_payment_method"]["tarjeta"] == 0


def test_dashboard_stats_with_data(client, db_session: Session):
    """Consulta de estadísticas con datos variados de transacciones y anomalías."""
    now_utc = datetime.now(timezone.utc)

    # 1. Crear usuarios
    u1 = Usuario(email="user1@test.com", nombre="User One", estado=EstadoUsuario.ACTIVO)
    u2 = Usuario(email="user2@test.com", nombre="User Two", estado=EstadoUsuario.ACTIVO)
    db_session.add_all([u1, u2])
    db_session.commit()

    # 2. Crear transacciones para u1
    t1 = Transaccion(
        id_txn="TX-D1",
        usuario_id=u1.id,
        valor=Decimal("100000.00"),
        fecha_txn=now_utc,
        fecha_recepcion=now_utc,
        estado=EstadoTransaccion.APROBADA,
        hash="a" * 64,
        metodo_pago="Tarjeta",
    )
    t2 = Transaccion(
        id_txn="TX-D2",
        usuario_id=u1.id,
        valor=Decimal("50000.50"),
        fecha_txn=now_utc,
        fecha_recepcion=now_utc,
        estado=EstadoTransaccion.SOSPECHOSA,
        hash="b" * 64,
        metodo_pago="PSE",
    )
    t3 = Transaccion(
        id_txn="TX-D3",
        usuario_id=u1.id,
        valor=Decimal("25000.00"),
        fecha_txn=now_utc,
        fecha_recepcion=now_utc,
        estado=EstadoTransaccion.SOSPECHOSA,
        hash="c" * 64,
        metodo_pago="Transferencia",
    )
    # Transacción para u2
    t4 = Transaccion(
        id_txn="TX-D4",
        usuario_id=u2.id,
        valor=Decimal("80000.00"),
        fecha_txn=now_utc,
        fecha_recepcion=now_utc,
        estado=EstadoTransaccion.RECHAZADA,
        hash="d" * 64,
        metodo_pago="Otro",
    )
    db_session.add_all([t1, t2, t3, t4])
    db_session.commit()

    # 3. Crear anomalías para u1 (2 anomalías para verificar usuario recurrente)
    a1 = Anomalia(
        transaccion_id=t2.id,
        tipo=TipoAnomalia.POSIBLE_FRAUDE,
        nivel=NivelAnomalia.ALTO,
        cantidad_transacciones=3,
        ventana_segundos=3,
        regla_detectada="SLIDING_WINDOW_3s_THRESHOLD_3",
        descripcion="Ráfaga sospechosa",
        estado_revision=EstadoRevision.NUEVA,
    )
    a2 = Anomalia(
        transaccion_id=t3.id,
        tipo=TipoAnomalia.POSIBLE_FRAUDE,
        nivel=NivelAnomalia.CRITICO,
        cantidad_transacciones=5,
        ventana_segundos=3,
        regla_detectada="SLIDING_WINDOW_3s_THRESHOLD_3",
        descripcion="Ráfaga crítica",
        estado_revision=EstadoRevision.ABIERTA,
    )
    db_session.add_all([a1, a2])
    db_session.commit()

    resp = client.get("/api/dashboard/stats?periodo=hoy")
    assert resp.status_code == 200
    data = resp.json()

    # Validar métricas
    assert data["by_status"]["total"] == 4
    assert data["by_status"]["aprobadas"] == 1
    assert data["by_status"]["sospechosas"] == 2
    assert data["by_status"]["rechazadas"] == 1

    assert data["anomalias"]["total"] == 2
    assert data["anomalias"]["porcentaje"] == 50.0
    # Monto sospechoso: 50000.50 + 25000.00 = 75000.50
    assert data["anomalias"]["monto_sospechoso"] == "75000.50"
    assert data["anomalias"]["usuarios_afectados"] == 1
    # u1 tiene 2 anomalías en el periodo -> es recurrente
    assert data["anomalias"]["recurrentes"] == 1

    # Severidad
    assert data["by_severity"]["alto"] == 1
    assert data["by_severity"]["critico"] == 1
    assert data["by_severity"]["bajo"] == 0

    # Revisión
    assert data["by_revision"]["nueva"] == 1
    assert data["by_revision"]["abierta"] == 1

    # Métodos de pago
    assert data["by_payment_method"]["tarjeta"] == 1
    assert data["by_payment_method"]["pse"] == 1
    assert data["by_payment_method"]["transferencia"] == 1
    assert data["by_payment_method"]["otro"] == 1


def test_dashboard_stats_periodos(client, db_session: Session):
    """Verifica que los filtros de periodo hoy, semana y mes respondan correctamente."""
    for periodo in ["hoy", "semana", "mes"]:
        resp = client.get(f"/api/dashboard/stats?periodo={periodo}")
        assert resp.status_code == 200
        assert resp.json()["periodo"] == periodo


def test_dashboard_timeline_sliding_window_success(client, db_session: Session):
    """Consulta la línea de tiempo cronológica de ventana deslizante para un usuario."""
    user = Usuario(email="timeline.user@test.com", nombre="Timeline User", estado=EstadoUsuario.ACTIVO)
    db_session.add(user)
    db_session.commit()

    t0 = datetime.now(timezone.utc)

    # 3 transacciones en 2 segundos
    txns = []
    for i in range(3):
        t = Transaccion(
            id_txn=f"TX-TIME-{i}",
            usuario_id=user.id,
            valor=Decimal("15000.00"),
            fecha_txn=t0 + timedelta(milliseconds=i * 500),
            fecha_recepcion=t0 + timedelta(milliseconds=i * 500),
            estado=EstadoTransaccion.SOSPECHOSA if i == 2 else EstadoTransaccion.APROBADA,
            hash=f"{i}" * 64,
            metodo_pago="Tarjeta",
        )
        txns.append(t)
    db_session.add_all(txns)
    db_session.commit()

    # Anomalía asociada a la tercera
    anomalia = Anomalia(
        transaccion_id=txns[2].id,
        tipo=TipoAnomalia.POSIBLE_FRAUDE,
        nivel=NivelAnomalia.ALTO,
        cantidad_transacciones=3,
        ventana_segundos=3,
        regla_detectada="SLIDING_WINDOW_3s_THRESHOLD_3",
        descripcion="Ráfaga",
        estado_revision=EstadoRevision.NUEVA,
    )
    db_session.add(anomalia)
    db_session.commit()

    resp = client.get(f"/api/dashboard/timeline-sliding-window/{user.id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["usuario_id"] == user.id
    assert data["email"] == "timeline.user@test.com"
    assert len(data["entries"]) == 3

    # Tercera transacción debe reflejar el conteo y la anomalía
    last_entry = data["entries"][-1]
    assert last_entry["idTxn"] == "TX-TIME-2"
    assert last_entry["estado"] == "SOSPECHOSA"
    assert last_entry["conteoVentana"] == 3
    assert last_entry["severidad"] == "ALTO"
    assert last_entry["reglaDetectada"] == "SLIDING_WINDOW_3s_THRESHOLD_3"


def test_dashboard_timeline_user_not_found_404(client):
    """Consulta de timeline para un usuario inexistente responde 404."""
    resp = client.get("/api/dashboard/timeline-sliding-window/999999")
    assert resp.status_code == 404
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "USER_NOT_FOUND"


def test_frontend_and_static_assets_served(client):
    """Verifica que el dashboard HTML, CSS, vendor Chart.js y scripts JS se sirvan correctamente."""
    # 1. Página principal HTML
    resp_index = client.get("/")
    assert resp_index.status_code == 200
    assert "VELUM" in resp_index.text
    assert "/static/vendor/chart.umd.js" in resp_index.text

    # 2. Endpoint de salud
    resp_health = client.get("/health")
    assert resp_health.status_code == 200
    assert resp_health.json()["status"] == "operativo"

    # 3. Archivos estáticos
    for path in [
        "/static/css/styles.css",
        "/static/vendor/chart.umd.js",
        "/static/js/dashboard.js",
        "/static/js/sliding-window.js",
        "/static/js/simulator.js",
        "/static/hash_vectors.json",
    ]:
        resp_static = client.get(path)
        assert resp_static.status_code == 200, f"Fallo al servir {path}"


def test_simulator_endpoints(client):
    """Verifica los endpoints de utilidad del simulador."""
    # Obtener vectores oficiales
    resp_vec = client.get("/api/simulator/hash-vectors")
    assert resp_vec.status_code == 200
    assert len(resp_vec.json()["vectors"]) >= 5

    # Reset
    resp_reset = client.post("/api/simulator/reset")
    assert resp_reset.status_code == 200
    assert resp_reset.json()["success"] is True
