"""Servicio de transacciones: orquesta la lógica de negocio.

Flujo completo:
1. Validar clock skew
2. Recalcular y comparar hash
3. Verificar idempotencia (mismo idTxn)
4. Obtener o crear usuario
5. Verificar estado del usuario
6. Pasar por ventana deslizante
7. Persistir todo en una transacción de BD
"""
from __future__ import annotations

import logging
import threading
import zoneinfo
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.detector import detector, calculate_severity, get_time_slot_reference
from app.models import (
    Anomalia,
    EstadoRevision,
    EstadoTransaccion,
    EstadoUsuario,
    NivelAnomalia,
    Transaccion,
    TipoAnomalia,
    Usuario,
)
from app.schemas import (
    AnalysisInfo,
    TransaccionInfo,
    TransaccionRequest,
    TransaccionResponse,
)
from app.security import safe_compare
from app.services.hash_service import compute_hash

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Excepciones de dominio
# ---------------------------------------------------------------------------

class HashInvalidError(Exception):
    """El hash de la transacción no coincide con el recalculado."""


class ClockSkewError(Exception):
    """El timestamp del cliente difiere demasiado del servidor."""


class UserBlockedError(Exception):
    """El usuario está bloqueado o inactivo."""
    def __init__(self, estado: str) -> None:
        self.estado = estado
        super().__init__(f"Usuario {estado}")


class DuplicateTransactionError(Exception):
    """La transacción ya existe con el mismo contenido."""
    def __init__(self, txn: Transaccion) -> None:
        self.txn = txn
        super().__init__("Transacción duplicada idéntica")


class ConflictTransactionError(Exception):
    """La transacción ya existe con contenido diferente."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_client_date(date_str: str) -> datetime:
    """Parsea fecha del cliente asumiendo zona America/Bogota (UTC-5).

    Si date llega sin zona horaria, se asume America/Bogota.
    Retorna datetime con tzinfo UTC.
    """
    dt_naive = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f")
    bogota_offset = timedelta(hours=-5)
    dt_bogota = dt_naive.replace(tzinfo=timezone(bogota_offset))
    return dt_bogota.astimezone(timezone.utc)


def _validate_clock_skew(client_dt_utc: datetime, server_dt_utc: datetime) -> None:
    """Rechaza si la diferencia entre cliente y servidor supera MAX_CLOCK_SKEW_SECONDS."""
    diff = abs((server_dt_utc - client_dt_utc).total_seconds())
    if diff > settings.max_clock_skew_seconds:
        raise ClockSkewError(
            f"Diferencia de reloj {diff:.0f}s supera el máximo permitido "
            f"({settings.max_clock_skew_seconds}s)"
        )


def _get_or_create_user(db: Session, email: str) -> Usuario:
    """Obtiene el usuario por email o lo crea si no existe.

    Nombre por defecto: parte local del email (antes del @).
    """
    user = db.query(Usuario).filter(Usuario.email == email).first()
    if user is None:
        nombre = email.split("@")[0]
        user = Usuario(email=email, nombre=nombre, estado=EstadoUsuario.ACTIVO)
        db.add(user)
        db.flush()  # Obtener el id sin commit
        logger.info("Usuario creado: email=%s", email)
    return user


_db_write_lock = threading.Lock()


def _find_existing_anomaly(
    db: Session,
    usuario_id: int,
    received_at: datetime,
    window_seconds: int,
) -> Anomalia | None:
    """Busca una anomalía activa (NUEVA o ABIERTA) del usuario cuya ventana se solapa."""
    candidate = (
        db.query(Anomalia)
        .join(Transaccion)
        .filter(
            Transaccion.usuario_id == usuario_id,
            Anomalia.estado_revision.in_([EstadoRevision.NUEVA, EstadoRevision.ABIERTA]),
        )
        .order_by(Anomalia.id.desc())
        .first()
    )
    if candidate and candidate.transaccion:
        t_cand = candidate.transaccion.fecha_recepcion
        if t_cand.tzinfo is None:
            t_cand = t_cand.replace(tzinfo=timezone.utc)
        if received_at.tzinfo is None:
            received_at = received_at.replace(tzinfo=timezone.utc)

        diff = abs((received_at - t_cand).total_seconds())
        if diff <= window_seconds:
            return candidate
    return None


# ---------------------------------------------------------------------------
# Servicio principal
# ---------------------------------------------------------------------------

def process_transaction(
    db: Session,
    payload: TransaccionRequest,
    received_at: datetime | None = None,
) -> TransaccionResponse:
    """Procesa una transacción entrante siguiendo el flujo completo de VELUM.

    Args:
        db: Sesión de base de datos.
        payload: Datos de la transacción validados por Pydantic.
        received_at: Timestamp de recepción (UTC). Si None, usa datetime.now(UTC).

    Returns:
        TransaccionResponse con el resultado completo.

    Raises:
        HashInvalidError: Hash no coincide.
        ClockSkewError: Timestamp del cliente demasiado lejano.
        UserBlockedError: Usuario bloqueado o inactivo.
        ConflictTransactionError: Mismo idTxn con contenido diferente.
    """
    if received_at is None:
        received_at = datetime.now(timezone.utc)

    # 1. Parsear y validar fecha del cliente
    client_dt_utc = _parse_client_date(payload.date)
    _validate_clock_skew(client_dt_utc, received_at)

    # 2. Recalcular hash y comparar (o asignar si fue omitido)
    expected_hash = compute_hash(
        id_txn=payload.id_txn,
        user=str(payload.user),
        date=payload.date,
        value=payload.value,
        payment_method=payload.payment_method,
    )
    if payload.hash is not None:
        if not safe_compare(expected_hash, payload.hash):
            logger.warning("Hash inválido para idTxn=%s user=%s", payload.id_txn, payload.user)
            raise HashInvalidError(f"Hash inválido para idTxn={payload.id_txn}")
    else:
        payload.hash = expected_hash

    with _db_write_lock:
        # 3. Verificar idempotencia
        existing_txn = db.query(Transaccion).filter(
            Transaccion.id_txn == payload.id_txn
        ).first()

        if existing_txn is not None:
            # Mismo idTxn: comparar hash para determinar si es duplicado idéntico o conflicto
            if safe_compare(existing_txn.hash, payload.hash):
                logger.info("Transacción duplicada idéntica: idTxn=%s", payload.id_txn)
                raise DuplicateTransactionError(existing_txn)
            else:
                logger.warning("Conflicto de idTxn=%s con contenido distinto", payload.id_txn)
                raise ConflictTransactionError(
                    f"idTxn={payload.id_txn} ya existe con contenido diferente"
                )

        # 4. Obtener o crear usuario
        email_normalized = str(payload.user).lower().strip()
        user = _get_or_create_user(db, email_normalized)

        # 5. Verificar estado del usuario
        if user.estado in (EstadoUsuario.BLOQUEADO, EstadoUsuario.INACTIVO):
            logger.warning("Transacción rechazada: usuario=%s estado=%s", email_normalized, user.estado)
            txn = Transaccion(
                id_txn=payload.id_txn,
                usuario_id=user.id,
                valor=payload.value,
                fecha_txn=client_dt_utc,
                fecha_recepcion=received_at,
                estado=EstadoTransaccion.RECHAZADA,
                hash=payload.hash,
                metodo_pago=payload.payment_method,
            )
            db.add(txn)
            db.commit()
            raise UserBlockedError(user.estado.value)

        # 6. Pasar por el detector de ventana deslizante
        result = detector.process(email_normalized, received_at)

        # 7. Determinar estado de la transacción
        estado = EstadoTransaccion.SOSPECHOSA if result.anomaly_detected else EstadoTransaccion.APROBADA

        # 8. Persistir transacción y anomalía en una sola transacción de BD
        try:
            txn = Transaccion(
                id_txn=payload.id_txn,
                usuario_id=user.id,
                valor=payload.value,
                fecha_txn=client_dt_utc,
                fecha_recepcion=received_at,
                estado=estado,
                hash=payload.hash,
                metodo_pago=payload.payment_method,
            )
            db.add(txn)
            db.flush()
            txn_id = txn.id

            anomaly_info: dict | None = None

            if result.anomaly_detected:
                # Buscar anomalía existente solapada para actualizar
                existing_anomaly = _find_existing_anomaly(
                    db, user.id, received_at, settings.window_seconds
                )

                slot_name, reference = get_time_slot_reference(
                    received_at.astimezone(zoneinfo.ZoneInfo(settings.timezone))
                )
                severity_str = calculate_severity(result.transaction_count, reference)

                if existing_anomaly:
                    existing_anomaly.cantidad_transacciones = result.transaction_count
                    existing_anomaly.nivel = NivelAnomalia(severity_str)
                    existing_anomaly.estado_revision = EstadoRevision.ABIERTA
                    existing_anomaly.descripcion = (
                        f"Ráfaga actualizada: {result.transaction_count} transacciones "
                        f"en {settings.window_seconds}s para {email_normalized}"
                    )
                    db.flush()
                    anomaly_info = {
                        "type": TipoAnomalia.POSIBLE_FRAUDE.value,
                        "severity": severity_str,
                        "count": result.transaction_count,
                    }
                else:
                    regla = (
                        f"SLIDING_WINDOW_{settings.window_seconds}s_THRESHOLD_{settings.base_transaction_threshold}"
                    )
                    anomalia = Anomalia(
                        transaccion_id=txn.id,
                        tipo=TipoAnomalia.POSIBLE_FRAUDE,
                        nivel=NivelAnomalia(severity_str),
                        cantidad_transacciones=result.transaction_count,
                        ventana_segundos=settings.window_seconds,
                        regla_detectada=regla,
                        descripcion=(
                            f"Ráfaga detectada: {result.transaction_count} transacciones "
                            f"en {settings.window_seconds}s para {email_normalized} "
                            f"(franja: {slot_name}, severidad: {severity_str})"
                        ),
                        estado_revision=EstadoRevision.NUEVA,
                    )
                    db.add(anomalia)
                    db.flush()
                    logger.warning(
                        "Anomalía detectada: usuario=%s count=%d severity=%s",
                        email_normalized, result.transaction_count, severity_str,
                    )
                    anomaly_info = {
                        "type": TipoAnomalia.POSIBLE_FRAUDE.value,
                        "severity": severity_str,
                        "count": result.transaction_count,
                    }

            db.commit()

        except IntegrityError as exc:
            db.rollback()
            logger.error("IntegrityError al persistir transacción idTxn=%s: %s", payload.id_txn, exc)
            # Podría ser una carrera en idTxn
            existing_txn = db.query(Transaccion).filter(
                Transaccion.id_txn == payload.id_txn
            ).first()
            if existing_txn and safe_compare(existing_txn.hash, payload.hash):
                raise DuplicateTransactionError(existing_txn) from exc
            raise ConflictTransactionError(
                f"Conflicto al persistir idTxn={payload.id_txn}"
            ) from exc

    analysis = AnalysisInfo(
        anomalyDetected=result.anomaly_detected,
        type=anomaly_info["type"] if anomaly_info else None,
        severity=anomaly_info["severity"] if anomaly_info else None,
        transactionCount=result.transaction_count if result.anomaly_detected else None,
        windowSeconds=settings.window_seconds if result.anomaly_detected else None,
    )

    logger.info(
        "Transacción procesada: idTxn=%s estado=%s anomaly=%s",
        payload.id_txn, estado.value, result.anomaly_detected,
    )

    return TransaccionResponse(
        success=True,
        duplicate=False,
        transaction=TransaccionInfo(
            id=txn_id,
            idTxn=payload.id_txn,
            status=estado.value,
        ),
        analysis=analysis,
    )
