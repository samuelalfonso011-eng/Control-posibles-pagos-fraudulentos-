"""Modelos ORM de VELUM.

Tablas:
- usuarios
- transacciones
- anomalias

Relaciones: usuarios 1—N transacciones, transacciones 1—N anomalias.
Dinero almacenado como Numeric(12,2) — nunca float.
Fechas en UTC en la BD.
"""
from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ---------------------------------------------------------------------------
# Enumeraciones
# ---------------------------------------------------------------------------

class EstadoUsuario(str, enum.Enum):
    ACTIVO = "ACTIVO"
    INACTIVO = "INACTIVO"
    BLOQUEADO = "BLOQUEADO"


class EstadoTransaccion(str, enum.Enum):
    APROBADA = "APROBADA"
    SOSPECHOSA = "SOSPECHOSA"
    RECHAZADA = "RECHAZADA"


class TipoAnomalia(str, enum.Enum):
    POSIBLE_FRAUDE = "POSIBLE_FRAUDE"


class NivelAnomalia(str, enum.Enum):
    BAJO = "BAJO"
    MEDIO = "MEDIO"
    ALTO = "ALTO"
    CRITICO = "CRITICO"


class EstadoRevision(str, enum.Enum):
    NUEVA = "NUEVA"
    ABIERTA = "ABIERTA"
    REVISADA = "REVISADA"
    DESCARTADA = "DESCARTADA"


class MetodoPago(str, enum.Enum):
    TARJETA = "Tarjeta"
    PSE = "PSE"
    TRANSFERENCIA = "Transferencia"
    OTRO = "Otro"


# ---------------------------------------------------------------------------
# Tablas
# ---------------------------------------------------------------------------

class Usuario(Base):
    """Tabla de usuarios del sistema."""

    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    estado: Mapped[EstadoUsuario] = mapped_column(
        Enum(EstadoUsuario, name="estado_usuario"),
        nullable=False,
        default=EstadoUsuario.ACTIVO,
        server_default=EstadoUsuario.ACTIVO.value,
    )
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    transacciones: Mapped[list[Transaccion]] = relationship(
        "Transaccion", back_populates="usuario", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Usuario id={self.id} email={self.email} estado={self.estado}>"


class Transaccion(Base):
    """Tabla de transacciones financieras."""

    __tablename__ = "transacciones"
    __table_args__ = (
        UniqueConstraint("id_txn", name="uq_transacciones_id_txn"),
        Index("ix_transacciones_id_txn", "id_txn"),
        Index("ix_transacciones_usuario_id", "usuario_id"),
        Index("ix_transacciones_fecha_txn", "fecha_txn"),
        Index("ix_transacciones_estado", "estado"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_txn: Mapped[str] = mapped_column(String(64), nullable=False)
    usuario_id: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    fecha_txn: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fecha_recepcion: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estado: Mapped[EstadoTransaccion] = mapped_column(
        Enum(EstadoTransaccion, name="estado_transaccion"),
        nullable=False,
        default=EstadoTransaccion.APROBADA,
    )
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    metodo_pago: Mapped[str] = mapped_column(String(20), nullable=False)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    usuario: Mapped[Usuario] = relationship("Usuario", back_populates="transacciones")
    anomalias: Mapped[list[Anomalia]] = relationship(
        "Anomalia", back_populates="transaccion", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Transaccion id={self.id} id_txn={self.id_txn} estado={self.estado}>"


class Anomalia(Base):
    """Tabla de anomalías detectadas por el sistema."""

    __tablename__ = "anomalias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaccion_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("transacciones.id"), nullable=False
    )
    tipo: Mapped[TipoAnomalia] = mapped_column(
        Enum(TipoAnomalia, name="tipo_anomalia"),
        nullable=False,
        default=TipoAnomalia.POSIBLE_FRAUDE,
    )
    nivel: Mapped[NivelAnomalia] = mapped_column(
        Enum(NivelAnomalia, name="nivel_anomalia"), nullable=False
    )
    cantidad_transacciones: Mapped[int] = mapped_column(Integer, nullable=False)
    ventana_segundos: Mapped[int] = mapped_column(Integer, nullable=False)
    regla_detectada: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str] = mapped_column(String(500), nullable=False)
    estado_revision: Mapped[EstadoRevision] = mapped_column(
        Enum(EstadoRevision, name="estado_revision"),
        nullable=False,
        default=EstadoRevision.NUEVA,
        server_default=EstadoRevision.NUEVA.value,
    )
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    transaccion: Mapped[Transaccion] = relationship("Transaccion", back_populates="anomalias")

    def __repr__(self) -> str:
        return f"<Anomalia id={self.id} tipo={self.tipo} nivel={self.nivel}>"
