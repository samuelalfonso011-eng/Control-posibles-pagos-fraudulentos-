"""Router de utilidades para el Simulador de VELUM.

Provee endpoints para gestionar y restablecer datos de las cuentas de prueba:
- POST /api/simulator/reset
- GET /api/simulator/users
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.detector import detector
from app.models import Anomalia, Transaccion, Usuario

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simulator", tags=["simulator"])

SIMULATION_EMAILS = ["b@b.com", "c@c.com", "aa@aa.com", "test@test.com"]


@router.post(
    "/reset",
    summary="Limpiar transacciones y anomalías de los usuarios de prueba",
)
def reset_simulation_data(db: Session = Depends(get_db)):
    """Elimina transacciones y anomalías generadas para usuarios de simulación

    y vacía sus ventanas en memoria en el detector.
    """
    try:
        users = db.query(Usuario).filter(Usuario.email.in_(SIMULATION_EMAILS)).all()
        user_ids = [u.id for u in users]

        if user_ids:
            txns = db.query(Transaccion).filter(Transaccion.usuario_id.in_(user_ids)).all()
            txn_ids = [t.id for t in txns]

            if txn_ids:
                db.query(Anomalia).filter(Anomalia.transaccion_id.in_(txn_ids)).delete(synchronize_session=False)
                db.query(Transaccion).filter(Transaccion.id.in_(txn_ids)).delete(synchronize_session=False)

            db.commit()

        # Limpiar ventanas en memoria del detector
        for email in SIMULATION_EMAILS:
            detector.reset_user(email)

        return {
            "success": True,
            "message": "Datos de simulación y ventanas en memoria restablecidos con éxito",
        }
    except Exception as exc:
        db.rollback()
        logger.error("Error al reiniciar datos de simulación: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "error": {"code": "RESET_FAILED", "message": str(exc)}},
        )


@router.get(
    "/users",
    summary="Obtener IDs y detalles de los usuarios de simulación",
)
def get_simulation_users(db: Session = Depends(get_db)):
    """Retorna los IDs de b@b.com, c@c.com, etc., para vincular con la vista de ventana deslizante."""
    users = db.query(Usuario).filter(Usuario.email.in_(SIMULATION_EMAILS)).all()
    return {
        "success": True,
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "nombre": u.nombre,
                "estado": u.estado.value,
            }
            for u in users
        ],
    }


@router.get(
    "/hash-vectors",
    summary="Obtener vectores oficiales de prueba para autotest del frontend",
)
def get_hash_vectors():
    """Retorna los vectores de tests/hash_vectors.json para autoverificación con WebCrypto."""
    from app.services.hash_service import load_test_vectors
    return {
        "success": True,
        "vectors": load_test_vectors(),
    }
