"""Configuración central de la aplicación VELUM.

Lee variables de entorno y provee un objeto `settings` singleton.
No deben existir credenciales ni valores por defecto inseguros aquí.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de la aplicación cargada desde variables de entorno."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Base de datos
    database_url: str = "sqlite:///./appresso.db"

    # Detector de ventana deslizante
    window_seconds: int = 3
    base_transaction_threshold: int = 3
    max_clock_skew_seconds: int = 300

    # Zona horaria del negocio (para franjas horarias)
    timezone: str = "America/Bogota"

    # Entorno
    environment: str = "development"

    # CORS
    cors_origins: str = "http://localhost:8000"

    # Umbrales de severidad (ratios respecto a la referencia de franja)
    severity_low: float = 0.5
    severity_medium: float = 1.0
    severity_high: float = 2.0

    # Referencias de transacciones por franja (configurables)
    ref_morning: int = 10    # [05:00, 12:00)
    ref_afternoon: int = 6   # [12:00, 20:00)
    ref_night: int = 3       # [20:00, 05:00)

    @property
    def cors_origins_list(self) -> list[str]:
        """Retorna CORS_ORIGINS como lista."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
