"""Generador y emisor de peticiones de prueba para VELUM.

Uso:
  python generar_peticion.py
"""
import hashlib
import json
import urllib.request
from datetime import datetime
import zoneinfo

BOGOTA_TZ = zoneinfo.ZoneInfo("America/Bogota")

def generar_payload(id_txn: str, user: str, value: float, payment_method: str) -> dict:
    now_bogota = datetime.now(BOGOTA_TZ)
    date_str = now_bogota.strftime("%Y-%m-%dT%H:%M:%S.%f")[:23]
    
    # Cadena canónica: idTxn|user|date|value|paymentMethod
    canonical = f"{id_txn}|{user.lower().strip()}|{date_str}|{value:.2f}|{payment_method}"
    h = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    
    return {
        "idTxn": id_txn,
        "user": user,
        "date": date_str,
        "value": value,
        "paymentMethod": payment_method,
        "hash": h
    }

if __name__ == "__main__":
    payload = generar_payload(
        id_txn="TXN-DEMO-001",
        user="profesor@universidad.edu.co",
        value=150000.00,
        payment_method="Tarjeta"
    )
    print("=== PAYLOAD JSON GENERADO ===")
    print(json.dumps(payload, indent=2))
    
    with open("peticion_ejemplo.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print("\nGuardado en 'peticion_ejemplo.json'")
