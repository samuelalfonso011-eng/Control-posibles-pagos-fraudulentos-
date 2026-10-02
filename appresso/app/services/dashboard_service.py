"""Servicio de dashboard: agrega datos para los endpoints analíticos."""
from __future__ import annotations

import logging
import math
import zoneinfo
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    Anomalia,
    EstadoRevision,
    EstadoTransaccion,
    MetodoPago,
    NivelAnomalia,
    Transaccion,
    Usuario,
)
from app.schemas import (
    AnomaliaStats,
    ByRevisionStats,
    BySeverityStats,
    ByStatusStats,
    DashboardStatsResponse,
    HourlyPoint,
    PaymentMethodStats,
    TimelineEntry,
    TimelineResponse,
)

logger = logging.getLogger(__name__)

BOGOTA_TZ = zoneinfo.ZoneInfo(settings.timezone)


def _periodo_range(periodo: str) -> tuple[datetime, datetime]:
    """Retorna (inicio, fin) en UTC para el periodo dado.

    Los rangos se calculan en hora de Bogotá y se convierten a UTC.
    """
    now_bogota = datetime.now(BOGOTA_TZ)
    today_start = now_bogota.replace(hour=0, minute=0, second=0, microsecond=0)
    end_buffer = now_bogota + timedelta(minutes=5)

    if periodo == "hoy":
        start = today_start
        end = end_buffer
    elif periodo == "semana":
        start = today_start - timedelta(days=7)
        end = end_buffer
    elif periodo == "mes":
        start = today_start - timedelta(days=30)
        end = end_buffer
    else:
        start = today_start
        end = end_buffer

    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def _periodo_anterior_range(periodo: str, start: datetime, end: datetime) -> tuple[datetime, datetime]:
    """Retorna el rango del periodo anterior equivalente."""
    delta = end - start
    return start - delta, start


def get_dashboard_stats(db: Session, periodo: str) -> DashboardStatsResponse:
    """Calcula las estadísticas del dashboard para el periodo dado."""
    start, end = _periodo_range(periodo)
    prev_start, prev_end = _periodo_anterior_range(periodo, start, end)

    # Transacciones del periodo
    # SQLite almacena datetimes como cadenas naive; usamos UTC naive para el filtro SQL
    start_naive = start.replace(tzinfo=None)
    end_naive = end.replace(tzinfo=None)
    txns = (
        db.query(Transaccion)
        .filter(Transaccion.fecha_recepcion >= start_naive, Transaccion.fecha_recepcion <= end_naive)
        .all()
    )

    total = len(txns)
    aprobadas = sum(1 for t in txns if t.estado == EstadoTransaccion.APROBADA)
    sospechosas = sum(1 for t in txns if t.estado == EstadoTransaccion.SOSPECHOSA)
    rechazadas = sum(1 for t in txns if t.estado == EstadoTransaccion.RECHAZADA)

    # Monto sospechoso
    monto_sospechoso = sum(
        t.valor for t in txns if t.estado == EstadoTransaccion.SOSPECHOSA
    )

    # Anomalías del periodo (relacionadas a transacciones del periodo)
    txn_ids = [t.id for t in txns]
    anomalias_periodo = (
        db.query(Anomalia)
        .filter(Anomalia.transaccion_id.in_(txn_ids))
        .all()
        if txn_ids
        else []
    )

    total_anomalias = len(anomalias_periodo)
    pct_anomalias = round((total_anomalias / total * 100) if total > 0 else 0.0, 2)

    # Usuarios afectados (distintos usuarios con transacciones SOSPECHOSA)
    usuarios_afectados_ids = set(
        t.usuario_id for t in txns if t.estado == EstadoTransaccion.SOSPECHOSA
    )

    # Usuarios recurrentes: 2+ anomalías en el periodo
    usuario_anomalia_count: dict[int, int] = {}
    for a in anomalias_periodo:
        txn_obj = db.get(Transaccion, a.transaccion_id)
        if txn_obj:
            usuario_anomalia_count[txn_obj.usuario_id] = (
                usuario_anomalia_count.get(txn_obj.usuario_id, 0) + 1
            )
    recurrentes = sum(1 for c in usuario_anomalia_count.values() if c >= 2)

    # Por severidad
    by_severity = BySeverityStats(
        bajo=sum(1 for a in anomalias_periodo if a.nivel == NivelAnomalia.BAJO),
        medio=sum(1 for a in anomalias_periodo if a.nivel == NivelAnomalia.MEDIO),
        alto=sum(1 for a in anomalias_periodo if a.nivel == NivelAnomalia.ALTO),
        critico=sum(1 for a in anomalias_periodo if a.nivel == NivelAnomalia.CRITICO),
    )

    # Por estado de revisión
    by_revision = ByRevisionStats(
        nueva=sum(1 for a in anomalias_periodo if a.estado_revision == EstadoRevision.NUEVA),
        abierta=sum(1 for a in anomalias_periodo if a.estado_revision == EstadoRevision.ABIERTA),
        revisada=sum(1 for a in anomalias_periodo if a.estado_revision == EstadoRevision.REVISADA),
        descartada=sum(1 for a in anomalias_periodo if a.estado_revision == EstadoRevision.DESCARTADA),
    )

    # Por hora (en hora de Bogotá)
    hourly: dict[int, dict] = {h: {"transacciones": 0, "anomalias": 0} for h in range(24)}
    anomalia_txn_ids = {a.transaccion_id for a in anomalias_periodo}
    for t in txns:
        fr = t.fecha_recepcion
        if fr.tzinfo is None:
            fr = fr.replace(tzinfo=timezone.utc)
        hora_bogota = fr.astimezone(BOGOTA_TZ).hour
        hourly[hora_bogota]["transacciones"] += 1
        if t.id in anomalia_txn_ids:
            hourly[hora_bogota]["anomalias"] += 1

    by_hour = [
        HourlyPoint(hora=h, transacciones=v["transacciones"], anomalias=v["anomalias"])
        for h, v in sorted(hourly.items())
    ]

    # Pico: hora con anomalías >= media + 2*std (o la hora máxima si pocos datos)
    hora_anomalias = [v["anomalias"] for v in hourly.values()]
    pico_hora: int | None = None
    if any(x > 0 for x in hora_anomalias):
        media = sum(hora_anomalias) / 24
        varianza = sum((x - media) ** 2 for x in hora_anomalias) / 24
        std = math.sqrt(varianza)
        umbral = media + 2 * std
        pico_candidatos = [h for h, v in hourly.items() if v["anomalias"] >= umbral and v["anomalias"] > 0]
        if pico_candidatos:
            pico_hora = max(pico_candidatos, key=lambda h: hourly[h]["anomalias"])
        else:
            # Pocos datos: hora con más anomalías
            pico_hora = max(range(24), key=lambda h: hourly[h]["anomalias"])
            if hourly[pico_hora]["anomalias"] == 0:
                pico_hora = None

    # Tendencia: variación porcentual vs periodo anterior
    txns_prev = (
        db.query(Transaccion)
        .filter(
            Transaccion.fecha_recepcion >= prev_start.replace(tzinfo=None),
            Transaccion.fecha_recepcion <= prev_end.replace(tzinfo=None),
        )
        .count()
    )
    tendencia: float | None = None
    if txns_prev > 0:
        tendencia = round(((total - txns_prev) / txns_prev) * 100, 2)
    elif total > 0:
        tendencia = 100.0

    # Por método de pago
    pago_counts: dict[str, int] = {}
    for t in txns:
        pago_counts[t.metodo_pago] = pago_counts.get(t.metodo_pago, 0) + 1

    by_payment_method = PaymentMethodStats(
        tarjeta=pago_counts.get("Tarjeta", 0),
        pse=pago_counts.get("PSE", 0),
        transferencia=pago_counts.get("Transferencia", 0),
        otro=pago_counts.get("Otro", 0),
    )

    return DashboardStatsResponse(
        periodo=periodo,
        by_status=ByStatusStats(
            aprobadas=aprobadas,
            sospechosas=sospechosas,
            rechazadas=rechazadas,
            total=total,
        ),
        anomalias=AnomaliaStats(
            total=total_anomalias,
            porcentaje=pct_anomalias,
            monto_sospechoso=f"{monto_sospechoso:.2f}",
            usuarios_afectados=len(usuarios_afectados_ids),
            recurrentes=recurrentes,
        ),
        by_severity=by_severity,
        by_revision=by_revision,
        by_hour=by_hour,
        pico_hora=pico_hora,
        tendencia=tendencia,
        by_payment_method=by_payment_method,
    )


def get_timeline(db: Session, usuario_id: int) -> TimelineResponse:
    """Construye la línea de tiempo de ventana deslizante para un usuario."""
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        return None  # type: ignore[return-value]

    txns = (
        db.query(Transaccion)
        .filter(Transaccion.usuario_id == usuario_id)
        .order_by(Transaccion.fecha_recepcion)
        .all()
    )

    # Para cada transacción, calcular retrospectivamente si estuvo en ventana
    entries: list[TimelineEntry] = []
    window_seconds = settings.window_seconds

    for i, txn in enumerate(txns):
        t = txn.fecha_recepcion
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        window_start = t - timedelta(seconds=window_seconds)

        # Transacciones en la ventana hasta este punto (inclusive)
        in_window = []
        for other in txns[:i + 1]:
            other_t = other.fecha_recepcion
            if other_t.tzinfo is None:
                other_t = other_t.replace(tzinfo=timezone.utc)
            if window_start <= other_t <= t:
                in_window.append(other)
        count = len(in_window)

        # Anomalías asociadas a esta transacción
        anomalias_txn = (
            db.query(Anomalia)
            .filter(Anomalia.transaccion_id == txn.id)
            .all()
        )
        severidad = anomalias_txn[0].nivel.value if anomalias_txn else None
        regla = anomalias_txn[0].regla_detectada if anomalias_txn else None

        entries.append(
            TimelineEntry(
                timestamp=t.astimezone(BOGOTA_TZ).isoformat(),
                idTxn=txn.id_txn,
                valor=f"{txn.valor:.2f}",
                estado=txn.estado.value,
                enVentana=count > 1,
                ventanaInicio=window_start.astimezone(BOGOTA_TZ).isoformat(),
                ventanaFin=t.astimezone(BOGOTA_TZ).isoformat(),
                conteoVentana=count,
                severidad=severidad,
                reglaDetectada=regla,
            )
        )

    return TimelineResponse(
        usuario_id=usuario_id,
        email=usuario.email,
        entries=entries,
    )


def get_users_directory(db: Session, periodo: str = "todos") -> list[dict]:
    """Retorna el listado de usuarios con metricas adaptadas al periodo seleccionado."""
    usuarios = db.query(Usuario).order_by(Usuario.id).all()
    
    start_naive = None
    end_naive = None
    if periodo in ("hoy", "semana", "mes"):
        start, end = _periodo_range(periodo)
        start_naive = start.replace(tzinfo=None)
        end_naive = end.replace(tzinfo=None)

    result = []
    for u in usuarios:
        all_txns = u.transacciones
        
        # Filtrar por periodo si aplica
        if start_naive and end_naive:
            txns = [
                t for t in all_txns
                if start_naive <= (t.fecha_recepcion.replace(tzinfo=None) if t.fecha_recepcion.tzinfo else t.fecha_recepcion) <= end_naive
            ]
        else:
            txns = all_txns

        total_txns = len(txns)
        total_monto = sum(t.valor for t in txns) if txns else Decimal("0.00")
        
        # Conteo de anomalias en el periodo
        txn_ids = [t.id for t in txns]
        anomalias_count = (
            db.query(Anomalia).filter(Anomalia.transaccion_id.in_(txn_ids)).count()
            if txn_ids else 0
        )
        
        # Calcular nivel de riesgo segun actividad
        if u.estado.value == "BLOQUEADO":
            riesgo = "CRITICO"
        elif anomalias_count >= 3:
            riesgo = "CRITICO"
        elif anomalias_count >= 1:
            riesgo = "ALTO"
        elif any(t.estado.value == "SOSPECHOSA" for t in txns):
            riesgo = "MEDIO"
        else:
            riesgo = "BAJO"
            
        last_txn = max(all_txns, key=lambda t: t.fecha_recepcion) if all_txns else None
        if last_txn:
            fr = last_txn.fecha_recepcion
            if fr.tzinfo is None:
                fr = fr.replace(tzinfo=timezone.utc)
            ultima_actividad = fr.astimezone(BOGOTA_TZ).strftime("%Y-%m-%d %H:%M:%S")
        else:
            ultima_actividad = "Sin transacciones"
            
        result.append({
            "id": u.id,
            "email": u.email,
            "nombre": u.nombre,
            "estado": u.estado.value,
            "total_transacciones": total_txns,
            "total_anomalias": anomalias_count,
            "monto_total": f"{total_monto:.2f}",
            "riesgo": riesgo,
            "ultima_actividad": ultima_actividad,
            "historico_total_txns": len(all_txns),
        })
        
    # Ordenar priorizando cuentas con anomalias y actividad reciente
    result.sort(
        key=lambda x: (
            1 if x["riesgo"] == "CRITICO" else (2 if x["riesgo"] == "ALTO" else (3 if x["riesgo"] == "MEDIO" else 4)),
            -x["total_anomalias"],
            -x["total_transacciones"],
            x["ultima_actividad"]
        )
    )
    return result
