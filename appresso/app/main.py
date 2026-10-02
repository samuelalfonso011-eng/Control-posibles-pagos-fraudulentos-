"""Punto de entrada principal de la aplicación VELUM.

Configura:
- FastAPI con metadatos y documentación (/docs, /redoc)
- Middlewares: CORS, límite de tamaño de payload, manejo global de excepciones
- Montaje de archivos estáticos y plantillas Jinja2
- Reconstrucción de ventanas deslizantes al arranque desde la base de datos
- Rutas: /health, / (dashboard), transacciones, dashboard API, simulador
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import SessionLocal
from app.detector import detector
from app.models import Transaccion, Usuario
from app.routers import dashboard, simulator, transactions

# Configurar logging centralizado
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("velum")

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Asegurar directorios
STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _rebuild_sliding_windows():
    """Reconstruye las ventanas del detector desde la BD para los últimos WINDOW_SECONDS."""
    logger.info("Iniciando reconstrucción de ventanas deslizantes en memoria...")
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(seconds=settings.window_seconds)

    db = SessionLocal()
    try:
        recent_txns = (
            db.query(Transaccion)
            .join(Usuario)
            .order_by(Transaccion.id.desc())
            .limit(200)
            .all()
        )

        user_txns_map: dict[str, list[datetime]] = {}
        count_active = 0
        for txn in recent_txns:
            t = txn.fecha_recepcion
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            if t >= cutoff:
                email = txn.usuario.email.lower().strip()
                user_txns_map.setdefault(email, []).append(t)
                count_active += 1

        for email, timestamps in user_txns_map.items():
            detector.rebuild_from_history(email, timestamps)

        logger.info(
            "Reconstrucción completada: %d transacciones activas para %d usuarios",
            count_active,
            len(user_txns_map),
        )
    except Exception as exc:
        logger.error("Error reconstruyendo ventanas en memoria al arranque: %s", exc)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida de la aplicación."""
    logger.info("Iniciando VELUM Fraud Detection Platform (env=%s)...", settings.environment)
    _rebuild_sliding_windows()
    yield
    logger.info("Deteniendo VELUM Fraud Detection Platform...")


class PayloadLimitMiddleware(BaseHTTPMiddleware):
    """Middleware para limitar el tamaño del payload a 1 MB y prevenir ataques DoS."""

    MAX_PAYLOAD_SIZE = 1024 * 1024  # 1 MB

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.MAX_PAYLOAD_SIZE:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={
                    "success": False,
                    "error": {
                        "code": "PAYLOAD_TOO_LARGE",
                        "message": "El cuerpo de la solicitud supera el tamaño máximo permitido (1MB)",
                    },
                },
            )
        return await call_next(request)


app = FastAPI(
    title="VELUM — Sistema de Detección de Fraude",
    description="Motor de análisis de integridad transaccional y detección de ráfagas sospechosas con Sliding Window",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Middlewares
app.add_middleware(PayloadLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Manejador de validación de Pydantic
@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    first_error = errors[0] if errors else {}
    msg = first_error.get("msg", "Error de validación")
    loc = ".".join(str(l) for l in first_error.get("loc", []))
    field_msg = f"{loc}: {msg}" if loc else msg

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": field_msg,
            },
        },
    )


# Manejador global para HTTPExceptions
@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": str(exc.detail),
            },
        },
    )


# Manejador global genérico (sin filtrar stack traces al cliente)
@app.exception_handler(Exception)
def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Excepción no capturada en %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Ha ocurrido un error interno en el servidor",
            },
        },
    )


# Montar archivos estáticos
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# Rutas base
@app.get("/health", tags=["system"], summary="Verificación de estado del servicio")
def health_check():
    """Retorna estado operativo y métricas básicas de salud."""
    return {
        "status": "operativo",
        "service": "VELUM",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": settings.environment,
    }


@app.get("/", response_class=HTMLResponse, tags=["ui"], summary="Panel interactivo de VELUM")
def render_dashboard(request: Request):
    """Renderiza el dashboard interactivo de monitoreo y simulador."""
    return templates.TemplateResponse(request=request, name="index.html")


# Incluir routers de la API
app.include_router(transactions.router)
app.include_router(dashboard.router)
app.include_router(simulator.router)
