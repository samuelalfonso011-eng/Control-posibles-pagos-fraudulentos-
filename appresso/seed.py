"""Script para poblar la base de datos con datos sintéticos realistas.

Genera:
- Usuarios en distintos estados (ACTIVO, INACTIVO, BLOQUEADO).
- Transacciones distribuidas en distintas franjas horarias (mañana, tarde, noche en Bogotá).
- Todos los métodos de pago (Tarjeta, PSE, Transferencia, Otro).
- Todas las severidades de anomalía (BAJO, MEDIO, ALTO, CRITICO).
- Usuarios recurrentes con múltiples anomalías para los KPIs del dashboard.
- Hashes canónicos válidos calculados con compute_hash.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import zoneinfo

from app.config import settings
from app.database import SessionLocal, engine
from app.models import (
    Anomalia,
    Base,
    EstadoRevision,
    EstadoTransaccion,
    EstadoUsuario,
    NivelAnomalia,
    TipoAnomalia,
    Transaccion,
    Usuario,
)
from app.services.hash_service import compute_hash

BOGOTA_TZ = zoneinfo.ZoneInfo(settings.timezone)


def run_seed():
    print("[INFO] Iniciando poblacion de base de datos con datos de prueba...")
    db = SessionLocal()

    try:
        # 1. Crear o actualizar usuarios
        users_data = [
            ("andres.rodriguez@empresa.com", "Andrés Rodríguez", EstadoUsuario.ACTIVO),
            ("maria.fernanda@comercio.co", "María Fernanda Gómez", EstadoUsuario.ACTIVO),
            ("carlos.mendoza@fintech.io", "Carlos Mendoza", EstadoUsuario.ACTIVO),
            ("lucia.torres@tech.com", "Lucía Torres", EstadoUsuario.ACTIVO),
            ("camilo.rodriguez@securepay.co", "Camilo Rodríguez (SOC)", EstadoUsuario.BLOQUEADO),
            ("santiago.v@neomarket.lat", "Santiago Valencia", EstadoUsuario.BLOQUEADO),
            ("valeria.m@fintech.bogota", "Valeria Morales", EstadoUsuario.ACTIVO),
            ("diego.alarcon@andestech.com", "Diego Alarcón", EstadoUsuario.ACTIVO),
            ("marcela.gomez@bogotapay.co", "Marcela Gómez", EstadoUsuario.ACTIVO),
            ("felipe.duque@pagosrapidos.com", "Felipe Duque", EstadoUsuario.ACTIVO),
            ("diana.ospina@bancoco.com", "Diana Ospina", EstadoUsuario.ACTIVO),
            ("b@b.com", "Simulador Ataque", EstadoUsuario.ACTIVO),
            ("c@c.com", "Simulador Normal", EstadoUsuario.ACTIVO),
            ("inactivo.usuario@correo.com", "Usuario Inactivo", EstadoUsuario.INACTIVO),
            ("fraude.bloqueado@riesgo.com", "Usuario Bloqueado", EstadoUsuario.BLOQUEADO),
        ]

        users_map: dict[str, Usuario] = {}
        for email, nombre, estado in users_data:
            u = db.query(Usuario).filter(Usuario.email == email).first()
            if not u:
                u = Usuario(email=email, nombre=nombre, estado=estado)
                db.add(u)
                db.flush()
            else:
                u.estado = estado
                db.flush()
            users_map[email] = u

        # 2. Generar transacciones con fechas controladas
        now_bogota = datetime.now(BOGOTA_TZ)
        today_start = now_bogota.replace(hour=0, minute=0, second=0, microsecond=0)

        # Franjas horarias en Bogotá:
        # Mañana: [05:00, 12:00)
        # Tarde: [12:00, 20:00)
        # Noche: [20:00, 05:00)

        slots = [
            ("mañana", today_start.replace(hour=8, minute=30)),
            ("mañana", today_start.replace(hour=10, minute=15)),
            ("tarde", today_start.replace(hour=13, minute=45)),
            ("tarde", today_start.replace(hour=16, minute=20)),
            ("noche", today_start.replace(hour=21, minute=10)),
            ("noche", today_start.replace(hour=23, minute=5)),
        ]

        payment_methods = ["Tarjeta", "PSE", "Transferencia", "Otro"]

        created_txns = 0
        created_anomalies = 0
        run_id = int(datetime.now().timestamp())

        # Crear transacciones normales distribuidas para usuarios activos
        for i, (slot_name, base_dt_bogota) in enumerate(slots):
            for u_idx, (email, user_obj) in enumerate(users_map.items()):
                if user_obj.estado != EstadoUsuario.ACTIVO:
                    continue

                txn_time_bogota = base_dt_bogota + timedelta(minutes=u_idx * 7)
                dt_str = txn_time_bogota.strftime("%Y-%m-%dT%H:%M:%S.%f")[:23]
                txn_utc = txn_time_bogota.astimezone(timezone.utc)

                id_txn = f"TXN-SEED-{run_id}-{i}-{u_idx}-{random.randint(100, 999)}"
                val = Decimal(f"{random.randint(25000, 450000)}.{random.randint(10, 99)}")
                pm = payment_methods[(i + u_idx) % len(payment_methods)]

                h = compute_hash(id_txn, email, dt_str, val, pm)

                t = Transaccion(
                    id_txn=id_txn,
                    usuario_id=user_obj.id,
                    valor=val,
                    fecha_txn=txn_utc,
                    fecha_recepcion=txn_utc,
                    estado=EstadoTransaccion.APROBADA,
                    hash=h,
                    metodo_pago=pm,
                )
                db.add(t)
                created_txns += 1

        db.flush()

        # 3. Generar Ráfagas de Ataque y Anomalías para cubrir todas las severidades:
        # Usuario Carlos Mendoza -> Ráfaga de mañana (3 txns en 1.5s, ref 10 -> ratio 0.3 -> BAJO)
        u_carlos = users_map["carlos.mendoza@fintech.io"]
        dt_burst_morning = today_start.replace(hour=9, minute=0)
        carlos_txns = []
        for b_idx in range(3):
            t_dt = dt_burst_morning + timedelta(milliseconds=b_idx * 400)
            dt_str = t_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:23]
            t_utc = t_dt.astimezone(timezone.utc)
            id_txn = f"TXN-BURST-BAJO-{run_id}-{b_idx}"
            val = Decimal("85000.00")
            h = compute_hash(id_txn, u_carlos.email, dt_str, val, "Tarjeta")
            t = Transaccion(
                id_txn=id_txn,
                usuario_id=u_carlos.id,
                valor=val,
                fecha_txn=t_utc,
                fecha_recepcion=t_utc,
                estado=EstadoTransaccion.SOSPECHOSA if b_idx == 2 else EstadoTransaccion.APROBADA,
                hash=h,
                metodo_pago="Tarjeta",
            )
            db.add(t)
            carlos_txns.append(t)
            created_txns += 1
        db.flush()

        a_bajo = Anomalia(
            transaccion_id=carlos_txns[-1].id,
            tipo=TipoAnomalia.POSIBLE_FRAUDE,
            nivel=NivelAnomalia.BAJO,
            cantidad_transacciones=3,
            ventana_segundos=settings.window_seconds,
            regla_detectada=f"SLIDING_WINDOW_{settings.window_seconds}s_THRESHOLD_{settings.base_transaction_threshold}",
            descripcion=f"Ráfaga detectada: 3 transacciones en 3s para {u_carlos.email} (franja: mañana, severidad: BAJO)",
            estado_revision=EstadoRevision.NUEVA,
        )
        db.add(a_bajo)
        created_anomalies += 1

        # Usuario María Fernanda -> Ráfaga de tarde (3 txns en 1.5s, ref 6 -> ratio 0.5 -> MEDIO)
        u_maria = users_map["maria.fernanda@comercio.co"]
        dt_burst_afternoon = today_start.replace(hour=15, minute=30)
        maria_txns = []
        for b_idx in range(3):
            t_dt = dt_burst_afternoon + timedelta(milliseconds=b_idx * 400)
            dt_str = t_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:23]
            t_utc = t_dt.astimezone(timezone.utc)
            id_txn = f"TXN-BURST-MEDIO-{run_id}-{b_idx}"
            val = Decimal("120000.00")
            h = compute_hash(id_txn, u_maria.email, dt_str, val, "PSE")
            t = Transaccion(
                id_txn=id_txn,
                usuario_id=u_maria.id,
                valor=val,
                fecha_txn=t_utc,
                fecha_recepcion=t_utc,
                estado=EstadoTransaccion.SOSPECHOSA if b_idx == 2 else EstadoTransaccion.APROBADA,
                hash=h,
                metodo_pago="PSE",
            )
            db.add(t)
            maria_txns.append(t)
            created_txns += 1
        db.flush()

        a_medio = Anomalia(
            transaccion_id=maria_txns[-1].id,
            tipo=TipoAnomalia.POSIBLE_FRAUDE,
            nivel=NivelAnomalia.MEDIO,
            cantidad_transacciones=3,
            ventana_segundos=settings.window_seconds,
            regla_detectada=f"SLIDING_WINDOW_{settings.window_seconds}s_THRESHOLD_{settings.base_transaction_threshold}",
            descripcion=f"Ráfaga detectada: 3 transacciones en 3s para {u_maria.email} (franja: tarde, severidad: MEDIO)",
            estado_revision=EstadoRevision.ABIERTA,
        )
        db.add(a_medio)
        created_anomalies += 1

        # Usuario Andrés Rodríguez -> Ráfaga de noche (3 txns, ref 3 -> ratio 1.0 -> ALTO)
        u_andres = users_map["andres.rodriguez@empresa.com"]
        dt_burst_night = today_start.replace(hour=22, minute=15)
        andres_txns = []
        for b_idx in range(3):
            t_dt = dt_burst_night + timedelta(milliseconds=b_idx * 400)
            dt_str = t_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:23]
            t_utc = t_dt.astimezone(timezone.utc)
            id_txn = f"TXN-BURST-ALTO-{run_id}-{b_idx}"
            val = Decimal("310000.00")
            h = compute_hash(id_txn, u_andres.email, dt_str, val, "Transferencia")
            t = Transaccion(
                id_txn=id_txn,
                usuario_id=u_andres.id,
                valor=val,
                fecha_txn=t_utc,
                fecha_recepcion=t_utc,
                estado=EstadoTransaccion.SOSPECHOSA if b_idx == 2 else EstadoTransaccion.APROBADA,
                hash=h,
                metodo_pago="Transferencia",
            )
            db.add(t)
            andres_txns.append(t)
            created_txns += 1
        db.flush()

        a_alto = Anomalia(
            transaccion_id=andres_txns[-1].id,
            tipo=TipoAnomalia.POSIBLE_FRAUDE,
            nivel=NivelAnomalia.ALTO,
            cantidad_transacciones=3,
            ventana_segundos=settings.window_seconds,
            regla_detectada=f"SLIDING_WINDOW_{settings.window_seconds}s_THRESHOLD_{settings.base_transaction_threshold}",
            descripcion=f"Ráfaga detectada: 3 transacciones en 3s para {u_andres.email} (franja: noche, severidad: ALTO)",
            estado_revision=EstadoRevision.REVISADA,
        )
        db.add(a_alto)
        created_anomalies += 1

        # Segunda anomalía para Andrés Rodríguez (Ráfaga de 6 transacciones en la noche -> ratio 2.0 -> CRITICO)
        # Esto además convierte a Andrés en USUARIO RECURRENTE (2+ anomalías en el periodo)
        dt_burst_critical = today_start.replace(hour=23, minute=45)
        andres_txns_crit = []
        for b_idx in range(6):
            t_dt = dt_burst_critical + timedelta(milliseconds=b_idx * 300)
            dt_str = t_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:23]
            t_utc = t_dt.astimezone(timezone.utc)
            id_txn = f"TXN-BURST-CRIT-{run_id}-{b_idx}"
            val = Decimal("500000.00")
            h = compute_hash(id_txn, u_andres.email, dt_str, val, "Tarjeta")
            t = Transaccion(
                id_txn=id_txn,
                usuario_id=u_andres.id,
                valor=val,
                fecha_txn=t_utc,
                fecha_recepcion=t_utc,
                estado=EstadoTransaccion.SOSPECHOSA if b_idx >= 2 else EstadoTransaccion.APROBADA,
                hash=h,
                metodo_pago="Tarjeta",
            )
            db.add(t)
            andres_txns_crit.append(t)
            created_txns += 1
        db.flush()

        a_critico = Anomalia(
            transaccion_id=andres_txns_crit[-1].id,
            tipo=TipoAnomalia.POSIBLE_FRAUDE,
            nivel=NivelAnomalia.CRITICO,
            cantidad_transacciones=6,
            ventana_segundos=settings.window_seconds,
            regla_detectada=f"SLIDING_WINDOW_{settings.window_seconds}s_THRESHOLD_{settings.base_transaction_threshold}",
            descripcion=f"Ráfaga masiva: 6 transacciones en 3s para {u_andres.email} (franja: noche, severidad: CRITICO)",
            estado_revision=EstadoRevision.NUEVA,
        )
        db.add(a_critico)
        created_anomalies += 1

        # 4. Transacción rechazada para el usuario bloqueado
        u_bloqueado = users_map["fraude.bloqueado@riesgo.com"]
        dt_blocked = today_start.replace(hour=14, minute=0)
        dt_str = dt_blocked.strftime("%Y-%m-%dT%H:%M:%S.%f")[:23]
        t_blocked_utc = dt_blocked.astimezone(timezone.utc)
        id_txn_rej = f"TXN-REJ-{run_id}-{random.randint(100, 999)}"
        h_rej = compute_hash(id_txn_rej, u_bloqueado.email, dt_str, "250000.00", "Tarjeta")

        t_rej = Transaccion(
            id_txn=id_txn_rej,
            usuario_id=u_bloqueado.id,
            valor=Decimal("250000.00"),
            fecha_txn=t_blocked_utc,
            fecha_recepcion=t_blocked_utc,
            estado=EstadoTransaccion.RECHAZADA,
            hash=h_rej,
            metodo_pago="Tarjeta",
        )
        db.add(t_rej)
        created_txns += 1

        db.commit()
        print(f"[OK] Base de datos poblada con exito:")
        print(f"   - {len(users_map)} usuarios")
        print(f"   - {created_txns} transacciones")
        print(f"   - {created_anomalies} anomalias generadas cubriendo todas las severidades:")
        print(f"     [BAJO, MEDIO, ALTO, CRITICO]")
        print(f"   - 1 usuario recurrente con multiples anomalias ({u_andres.email})")

    except Exception as exc:
        db.rollback()
        print(f"[ERROR] Error durante el seeding: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
