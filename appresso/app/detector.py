"""Detector de ventana deslizante (Sliding Window) para fraude en tiempo real.

Algoritmo:
1. Mantiene un deque por usuario con timestamps de transacciones recibidas.
2. Ante cada nueva transacción, purga los timestamps fuera de [t - WINDOW_SECONDS, t].
3. Si el conteo después de la purga >= BASE_TRANSACTION_THRESHOLD → POSIBLE_FRAUDE.
4. La severidad se calcula con `calculate_severity` según la franja horaria.
5. Threading: un Lock por usuario garantiza consistencia en acceso concurrente.

El detector recibe un `clock` inyectable para tests deterministas.
"""
from __future__ import annotations

import logging
import threading
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Callable, NamedTuple

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tipos y resultados
# ---------------------------------------------------------------------------

class DetectionResult(NamedTuple):
    """Resultado del análisis de una transacción."""
    anomaly_detected: bool
    transaction_count: int
    severity: str | None
    window_start: datetime | None
    window_end: datetime | None


# ---------------------------------------------------------------------------
# Cálculo de severidad
# ---------------------------------------------------------------------------

def get_time_slot_reference(dt_bogota: datetime) -> tuple[str, int]:
    """Determina la franja horaria y su referencia de transacciones.

    Franjas en hora de Bogotá (intervalos semiabiertos):
    - Mañana:  [05:00, 12:00) → referencia 10
    - Tarde:   [12:00, 20:00) → referencia 6
    - Noche:   [20:00, 05:00) → referencia 3

    Returns:
        (nombre_franja, referencia)
    """
    hour = dt_bogota.hour
    if 5 <= hour < 12:
        return "mañana", settings.ref_morning
    elif 12 <= hour < 20:
        return "tarde", settings.ref_afternoon
    else:
        return "noche", settings.ref_night


def calculate_severity(count: int, reference: int) -> str:
    """Calcula la severidad de una anomalía.

    Única fuente de verdad para el cálculo de severidad en el sistema.

    ratio = count / reference:
    - < 0.5  → BAJO
    - < 1.0  → MEDIO
    - < 2.0  → ALTO
    - >= 2.0 → CRITICO

    Args:
        count: Número de transacciones en la ventana.
        reference: Referencia de la franja horaria.

    Returns:
        Nivel de severidad como string.
    """
    ratio = count / reference
    if ratio < settings.severity_low:
        return "BAJO"
    elif ratio < settings.severity_medium:
        return "MEDIO"
    elif ratio < settings.severity_high:
        return "ALTO"
    else:
        return "CRITICO"


# ---------------------------------------------------------------------------
# Detector de ventana deslizante
# ---------------------------------------------------------------------------

class SlidingWindowDetector:
    """Detecta ráfagas sospechosas usando una ventana deslizante por usuario.

    Thread-safe: un Lock por usuario, creado bajo un Lock global para evitar
    condiciones de carrera en la creación de locks nuevos.

    Attributes:
        window_seconds: Tamaño de la ventana en segundos.
        threshold: Número mínimo de transacciones para disparar una alerta.
        clock: Función que retorna la hora actual (inyectable para tests).
    """

    def __init__(
        self,
        window_seconds: int | None = None,
        threshold: int | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.window_seconds = window_seconds or settings.window_seconds
        self.threshold = threshold or settings.base_transaction_threshold
        self.clock: Callable[[], datetime] = clock or (lambda: datetime.now(timezone.utc))

        # Deques de timestamps por usuario: {user_email: deque[datetime]}
        self._windows: dict[str, deque[datetime]] = {}
        # Lock por usuario
        self._user_locks: dict[str, threading.Lock] = {}
        # Lock global para crear locks de usuario
        self._global_lock = threading.Lock()

    def _get_user_lock(self, user: str) -> threading.Lock:
        """Obtiene o crea el Lock para un usuario dado."""
        if user not in self._user_locks:
            with self._global_lock:
                if user not in self._user_locks:
                    self._user_locks[user] = threading.Lock()
                    self._windows[user] = deque()
        return self._user_locks[user]

    def _purge_old(self, user: str, now: datetime) -> None:
        """Elimina timestamps fuera de la ventana [now - window_seconds, now].

        Límites inclusivos: se mantienen los timestamps t donde
        now - window_seconds <= t <= now.
        """
        window_start = now - timedelta(seconds=self.window_seconds)
        dq = self._windows[user]
        while dq and dq[0] < window_start:
            dq.popleft()

    def process(self, user: str, received_at: datetime) -> DetectionResult:
        """Procesa una transacción y retorna el resultado de detección.

        Args:
            user: Email normalizado del usuario.
            received_at: Timestamp de recepción en UTC (hora del servidor).

        Returns:
            DetectionResult con anomaly_detected, count, severity y ventana.
        """
        lock = self._get_user_lock(user)

        with lock:
            self._purge_old(user, received_at)
            self._windows[user].append(received_at)
            count = len(self._windows[user])
            window_start = self._windows[user][0] if self._windows[user] else received_at

        anomaly_detected = count >= self.threshold

        if not anomaly_detected:
            return DetectionResult(
                anomaly_detected=False,
                transaction_count=count,
                severity=None,
                window_start=None,
                window_end=None,
            )

        # Calcular severidad según franja horaria (en hora de Bogotá)
        try:
            import zoneinfo
            bogota_tz = zoneinfo.ZoneInfo(settings.timezone)
        except Exception:
            from datetime import timezone as tz
            bogota_tz = tz(timedelta(hours=-5))

        dt_bogota = received_at.astimezone(bogota_tz)
        _, reference = get_time_slot_reference(dt_bogota)
        severity = calculate_severity(count, reference)

        logger.warning(
            "Anomalía detectada: usuario=%s count=%d severity=%s",
            user, count, severity,
        )

        return DetectionResult(
            anomaly_detected=True,
            transaction_count=count,
            severity=severity,
            window_start=window_start,
            window_end=received_at,
        )

    def rebuild_from_history(self, user: str, timestamps: list[datetime]) -> None:
        """Reconstruye la ventana de un usuario desde el historial de BD.

        Se llama al arrancar la aplicación para restaurar el estado en memoria.
        Solo se cargan timestamps dentro de la ventana actual.
        """
        lock = self._get_user_lock(user)
        now = self.clock()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        window_start = now - timedelta(seconds=self.window_seconds)

        norm_ts = []
        for ts in timestamps:
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            norm_ts.append(ts)

        with lock:
            self._windows[user] = deque(
                ts for ts in sorted(norm_ts) if ts >= window_start
            )

    def get_window_snapshot(self, user: str) -> list[datetime]:
        """Retorna copia inmutable de los timestamps en la ventana del usuario."""
        lock = self._get_user_lock(user)
        with lock:
            return list(self._windows.get(user, deque()))

    def reset_user(self, user: str) -> None:
        """Limpia la ventana de un usuario (útil para tests)."""
        lock = self._get_user_lock(user)
        with lock:
            if user in self._windows:
                self._windows[user].clear()


# Instancia global del detector (singleton)
detector = SlidingWindowDetector()
