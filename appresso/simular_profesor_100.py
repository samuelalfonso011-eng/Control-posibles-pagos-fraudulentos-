"""Script de evaluación oficial (100 peticiones).

Especificaciones exactas:
- idTxn: TXN-AUTO-001 hasta TXN-AUTO-100 (con 10 duplicados idénticos).
- user: 'cliente.normal@banco.com' y ráfagas de 3 para 'victima.ataque@banco.com'.
- date: Formato ISO YYYY-MM-DDTHH:MM:SS.mmm.
- value: 20000.00 a 200000.00.
- paymentMethod: Alterna entre PSE y Tarjeta.
- Sin campo hash (autocalculado por el servidor).
"""
import concurrent.futures
import json
import random
import time
import urllib.request
from datetime import datetime
import zoneinfo

BOGOTA_TZ = zoneinfo.ZoneInfo("America/Bogota")
URL = "https://liking-magnitude-cosmos.ngrok-free.dev/api/transacciones"
API_KEY = "velum-api-key-live-2026"

TOTAL_PETICIONES = 100
DUPLICADOS_COUNT = 10

def generar_plan():
    plan = []
    unique_counter = 1
    
    while len(plan) < TOTAL_PETICIONES:
        if random.random() < 0.35 and len(plan) <= TOTAL_PETICIONES - 3:
            # Ráfaga rápida de 3 para victima.ataque@banco.com (fraude <3s)
            for _ in range(3):
                txn_id = f"TXN-AUTO-{unique_counter:03d}"
                unique_counter += 1
                plan.append(("victima.ataque@banco.com", txn_id, True))
        else:
            # Transacción normal para cliente.normal@banco.com
            txn_id = f"TXN-AUTO-{unique_counter:03d}"
            unique_counter += 1
            plan.append(("cliente.normal@banco.com", txn_id, False))
            
    # Asignar 10 duplicados idénticos deliberados
    random.seed(42)
    dup_indices = sorted(random.sample(range(15, len(plan)), DUPLICADOS_COUNT))
    for idx in dup_indices:
        orig = plan[random.randint(0, idx - 4)]
        plan[idx] = (orig[0], orig[1], False)
        
    return plan

def enviar(item):
    seq, user, txn_id, is_burst = item
    now_dt = datetime.now(BOGOTA_TZ)
    date_str = now_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:23]
    val = round(random.uniform(20000.0, 200000.0), 2)
    pm = "PSE" if seq % 2 == 0 else "Tarjeta"
    
    # Payload omitiendo el campo hash tal como pide la especificación
    payload = {
        "idTxn": txn_id,
        "user": user,
        "date": date_str,
        "value": val,
        "paymentMethod": pm
    }
    
    req = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-API-Key": API_KEY,
            "ngrok-skip-browser-warning": "1",
            "User-Agent": "Profesor-Agent/1.0"
        }
    )
    
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return {
                "idTxn": txn_id,
                "http": resp.status,
                "status": body.get("transaction", {}).get("status"),
                "duplicate": body.get("duplicate", False),
                "anomaly": body.get("analysis", {}).get("anomalyDetected", False),
                "severity": body.get("analysis", {}).get("severity"),
                "elapsed": time.time() - t0
            }
    except Exception as e:
        return {"idTxn": txn_id, "http": getattr(e, "code", 0), "error": str(e), "elapsed": time.time() - t0}

if __name__ == "__main__":
    plan = generar_plan()
    print(f"Disparando {len(plan)} peticiones según la especificación del profesor...")
    items = [(i + 1, u, tid, b) for i, (u, tid, b) in enumerate(plan)]
    
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futures = []
        for it in items:
            if not it[3]:
                time.sleep(0.04)
            futures.append(ex.submit(enviar, it))
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
    tot = time.time() - t0
    c201 = sum(1 for r in results if r.get("http") == 201)
    c200 = sum(1 for r in results if r.get("http") == 200)
    anom = sum(1 for r in results if r.get("anomaly"))
    sos = sum(1 for r in results if r.get("status") == "SOSPECHOSA")
    apr = sum(1 for r in results if r.get("status") == "APROBADA")
    
    print("\n=== REPORTE 100 PETICIONES ===")
    print(f"Tiempo: {tot:.2f} s")
    print(f"HTTP 201 (Nuevas): {c201}")
    print(f"HTTP 200 (Duplicados): {c200}")
    print(f"Aprobadas: {apr}")
    print(f"Sospechosas / Fraude: {sos}")
    print(f"Anomalías: {anom}")
