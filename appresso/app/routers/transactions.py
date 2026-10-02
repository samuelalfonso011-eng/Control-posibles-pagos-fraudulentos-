"""Router de transacciones.

Expone POST /api/transacciones con gestión de todos los casos:
- Transacción nueva (201)
- Duplicado idéntico (200)
- Conflicto (409)
- Hash inválido (400)
- Usuario bloqueado (403)
- Error de validación (422 via Pydantic)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import EstadoTransaccion, Transaccion
from app.schemas import (
    AnalysisInfo,
    ErrorDetail,
    ErrorResponse,
    TransaccionInfo,
    TransaccionRequest,
    TransaccionResponse,
)
from app.services.transaction_service import (
    ClockSkewError,
    ConflictTransactionError,
    DuplicateTransactionError,
    HashInvalidError,
    UserBlockedError,
    process_transaction,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/transacciones", tags=["transacciones"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=TransaccionResponse,
    responses={
        200: {"model": TransaccionResponse, "description": "Duplicado idéntico"},
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"description": "Error de validación Pydantic"},
        500: {"model": ErrorResponse},
    },
    summary="Crear o validar una transacción",
)
def create_transaction(
    payload: TransaccionRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Recibe, valida y procesa una transacción financiera.

    Flujo:
    1. Pydantic valida el payload (422 si falla).
    2. Se verifica el clock skew del timestamp.
    3. Se recalcula y compara el hash SHA-256.
    4. Se verifica idempotencia por idTxn.
    5. Se obtiene/crea el usuario.
    6. Se verifica el estado del usuario.
    7. Se pasa por la ventana deslizante.
    8. Se persiste y retorna el resultado.
    """
    logger.info("Transacción recibida: idTxn=%s user=%s", payload.id_txn, payload.user)

    try:
        response = process_transaction(db, payload)
        return response

    except DuplicateTransactionError as exc:
        txn = exc.txn
        # Construir análisis vacío (no tocamos la ventana en duplicados)
        analysis = AnalysisInfo(
            anomalyDetected=False,
            type=None,
            severity=None,
            transactionCount=None,
            windowSeconds=None,
        )
        duplicate_response = TransaccionResponse(
            success=True,
            duplicate=True,
            transaction=TransaccionInfo(
                id=txn.id,
                idTxn=txn.id_txn,
                status=txn.estado.value,
            ),
            analysis=analysis,
        )
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=duplicate_response.model_dump(by_alias=True),
        )

    except HashInvalidError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "error": {"code": "HASH_INVALID", "message": str(exc)}},
        )

    except ClockSkewError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"success": False, "error": {"code": "CLOCK_SKEW", "message": str(exc)}},
        )

    except UserBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "error": {
                    "code": f"USER_{exc.estado}",
                    "message": f"Usuario {exc.estado}: transacción rechazada",
                },
            },
        )

    except ConflictTransactionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "success": False,
                "error": {"code": "CONFLICT", "message": str(exc)},
            },
        )

    except Exception as exc:
        logger.error("Error interno procesando transacción: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {"code": "INTERNAL_ERROR", "message": "Error interno del servidor"},
            },
        )
