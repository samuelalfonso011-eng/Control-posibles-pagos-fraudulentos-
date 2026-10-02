# VELUM — Sistema de Detección de Fraude en Tiempo Real

Plataforma de detección temprana de fraude financiero transaccional basada en **Ventanas Deslizantes (Sliding Window)**, validación de integridad criptográfica con **SHA-256 canónico** y categorización adaptativa de severidad por franjas horarias.

---

## 1. Objetivo

Recibir transacciones financieras mediante una API REST de alto rendimiento, validar la integridad del contenido a través de un hash canónico SHA-256, asociarlas al usuario correspondiente y detectar ráfagas sospechosas (3 o más transacciones del mismo usuario en una ventana de 3 segundos). 

El sistema incluye:
- **API REST asíncrona/concurrente** construida con FastAPI y SQLAlchemy 2.x.
- **Detector de ventana deslizante (`SlidingWindowDetector`)** thread-safe con `threading.Lock` por usuario y reloj inyectable.
- **Dashboard analítico fintech** con 5 KPIs en tiempo real y 4 gráficos interactivos con **Chart.js local** (funciona 100% offline).
- **Visualizador académico de ventana deslizante** con línea de tiempo y sombreado `[t - 3s, t]`.
- **Simulador de ataque y tráfico normal** en el navegador con cálculo WebCrypto SHA-256 y autotest de vectores oficiales.

---

## 2. Arquitectura del Sistema

```
                  ┌────────────────────────────────────────┐
                  │          Cliente / Simulador           │
                  │   (HTML5 + ES6 + WebCrypto SHA-256)    │
                  └───────────────────┬────────────────────┘
                                      │ HTTP / JSON
                                      ▼
                  ┌────────────────────────────────────────┐
                  │             FastAPI Router             │
                  │ (Validación Pydantic v2 + Clock Skew)  │
                  └───────────────────┬────────────────────┘
                                      │
                                      ▼
                  ┌────────────────────────────────────────┐
                  │          Servicio de Seguridad         │
                  │ (Recálculo canónico SHA-256 + compare) │
                  └───────────────────┬────────────────────┘
                                      │
                                      ▼
                  ┌────────────────────────────────────────┐
                  │         SlidingWindowDetector          │
                  │ (Lock por usuario + Deque [t-3s, t])   │
                  └───────────────────┬────────────────────┘
                                      │
                                      ▼
                  ┌────────────────────────────────────────┐
                  │          Persistencia ORM              │
                  │   (Transacción BD + Tabla Anomalías)   │
                  └───────────────────┬────────────────────┘
                                      │
                                      ▼
                  ┌────────────────────────────────────────┐
                  │       Base de Datos (SQLite / PG)      │
                  │   usuarios | transacciones | anomalias │
                  └────────────────────────────────────────┘
```

---

## 3. Tecnologías Utilizadas

- **Lenguaje:** Python 3.11+
- **Backend:** FastAPI, Uvicorn, Pydantic v2, Pydantic-Settings
- **Persistencia & ORM:** SQLAlchemy 2.x, Alembic (migraciones)
- **Base de Datos:** SQLite (desarrollo local y pruebas) / PostgreSQL 16 (despliegue en contenedor)
- **Frontend:** HTML5 semántico, CSS3 moderno (tema Claro/Oscuro), Vanilla JavaScript ES6+, WebCrypto API
- **Visualización:** Chart.js 4.4 UMD servido localmente desde `static/vendor/chart.umd.js`
- **Testing:** Pytest, pytest-asyncio, HTTPX

---

## 4. Instalación y Puesta en Marcha

### Prerrequisitos
- Python 3.11 o superior instalado.
- Git (opcional).

### Paso 1: Clonar y configurar entorno virtual

En Windows (PowerShell):
```powershell
cd c:\Users\SAMUEL\Desktop\antifraude\appresso
python -m venv venv
venv\Scripts\activate
```

En Linux / macOS:
```bash
python3 -m venv venv
source venv/bin/activate
```

### Paso 2: Instalar dependencias

```powershell
pip install -r requirements.txt
```

### Paso 3: Configurar variables de entorno

Copia la plantilla `.env.example` a `.env`:
```powershell
Copy-Item .env.example .env
```

Variables disponibles:
```env
DATABASE_URL=sqlite:///./appresso.db
WINDOW_SECONDS=3
BASE_TRANSACTION_THRESHOLD=3
MAX_CLOCK_SKEW_SECONDS=300
TIMEZONE=America/Bogota
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:8000
```

### Paso 4: Ejecutar migraciones de base de datos

Alembic crea las 3 tablas con todas sus llaves foráneas e índices optimizados:
```powershell
alembic upgrade head
```

### Paso 5: Poblar con datos de prueba (Seeding)

```powershell
python seed.py
```

### Paso 6: Iniciar servidor de desarrollo

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

El sistema estará accesible en:
- **Panel interactivo & Simulador:** [http://localhost:8000/](http://localhost:8000/)
- **Documentación interactiva Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Documentación ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Healthcheck:** [http://localhost:8000/health](http://localhost:8000/health)

---

## 5. Ejecución de Pruebas Unitarias e Integración

La suite de pruebas automatizadas utiliza `pytest` con base de datos en memoria (`:memory:`) aislada:

```powershell
venv\Scripts\pytest -v
```

Cobertura de pruebas incluidas:
1. `tests/test_hash.py`: Validación canónica de los 5 vectores oficiales y resistencia a timing attacks.
2. `tests/test_detector.py`: Comportamiento de ventana deslizante, límites inclusivos, franjas horarias y concurrencia.
3. `tests/test_transactions.py`: Flujo REST completo (201, 200 duplicado, 400 hash inválido, 403 usuario bloqueado, 409 conflicto, 422 validación y ataques en ráfaga).
4. `tests/test_dashboard.py`: Estadísticas vacías, agregaciones, periodos, timeline y archivos estáticos.

---

## 6. Despliegue con Docker y Docker Compose

Para ejecutar en un stack de producción con PostgreSQL:

```bash
docker compose up --build -d
```

Validación de sintaxis del compose:
```bash
docker compose config
```

---

## 7. Explicación Paso a Paso del Algoritmo

### 7.1 Validación del Hash Canónico
Para garantizar la integridad estricta del mensaje en tránsito:
1. Se extraen los campos: `idTxn`, `user`, `date`, `value`, `paymentMethod`.
2. Se normalizan:
   - `user`: convertido a minúsculas y sin espacios intermedios ni extremos.
   - `value`: formateado con exactamente dos decimales (ej. `50000.00`).
   - `date`: validado en formato `YYYY-MM-DDTHH:MM:SS.mmm` (milisegundos exactos).
   - `paymentMethod`: validado en conjunto cerrado (`Tarjeta`, `PSE`, `Transferencia`, `Otro`).
3. Se concatena la cadena canónica delimitada por plecas (`|`):
   ```
   idTxn|user|date|value|paymentMethod
   ```
4. Se calcula el digest SHA-256 en minúsculas y se compara con `hmac.compare_digest` para neutralizar ataques de canal lateral por tiempo.

### 7.2 Ventana Deslizante (Sliding Window)
1. Para cada usuario se mantiene en memoria una cola de doble extremo (`collections.deque`) protegida por un cerrojo exclusivo (`threading.Lock`).
2. Al llegar una transacción en el tiempo $t$ (hora de recepción del servidor en UTC):
   - Se eliminan de la cola todos los registros anteriores a $t - \text{WINDOW\_SECONDS}$ (intervalo inclusivo $[t - 3\text{s}, t]$).
   - Se añade $t$ a la cola.
   - Se evalúa la regla base: si $\text{longitud(cola)} \ge \text{BASE\_TRANSACTION\_THRESHOLD}$ (3 transacciones), se declara **`POSIBLE_FRAUDE`** y estado de transacción **`SOSPECHOSA`**.
3. Al reiniciar el servidor, la aplicación reconstruye el estado en memoria de las ventanas leyendo las transacciones recientes de la base de datos de los últimos 3 segundos.

### 7.3 Cálculo Unificado de Severidad y Franjas Horarias
La severidad se calcula exclusivamente en `app/detector.py` mediante la función `calculate_severity(count, reference)` en hora local de Bogotá (UTC-5):

| Franja Horaria | Horario (Bogotá) | Referencia ($R$) |
|---|---|---|
| **Mañana** | $[05:00, 12:00)$ | 10 |
| **Tarde** | $[12:00, 20:00)$ | 6 |
| **Noche** | $[20:00, 05:00)$ | 3 |

El ratio se define como:
$$\text{Ratio} = \frac{\text{Conteo}}{\text{Referencia}}$$

Clasificación de Severidad:
- $\text{Ratio} < 0.5$ $\rightarrow$ **`BAJO`**
- $0.5 \le \text{Ratio} < 1.0$ $\rightarrow$ **`MEDIO`**
- $1.0 \le \text{Ratio} < 2.0$ $\rightarrow$ **`ALTO`**
- $\text{Ratio} \ge 2.0$ $\rightarrow$ **`CRITICO`**

*Ejemplo:* 3 transacciones a la 1:00 AM (noche, $R=3$) arrojan ratio $3/3 = 1.0 \rightarrow$ **`ALTO`**; mientras que 3 transacciones a las 9:00 AM (mañana, $R=10$) arrojan ratio $3/10 = 0.3 \rightarrow$ **`BAJO`**.

### 7.4 Consolidación de Anomalías por Ráfaga
Si se reciben transacciones continuas durante la misma ráfaga (por ejemplo, 4ª o 5ª transacción en la misma ventana activa), el sistema **actualiza** la anomalía existente (`cantidad_transacciones`, `nivel` y `estado_revision = ABIERTA`) en lugar de generar filas redundantes.

---

## 8. Ejemplos de Petición y Respuesta

### 8.1 Crear Transacción Exitosa (201 Created)
**Request:**
`POST /api/transacciones`
```json
{
  "idTxn": "TXN-7701",
  "user": "cliente@banco.com",
  "date": "2026-10-01T21:40:00.120",
  "value": 75000.00,
  "paymentMethod": "Tarjeta",
  "hash": "c20df545934444558eecf97beff6979201a07011d6706e2363e00fc488319665"
}
```

**Response (Tráfico Normal):**
```json
{
  "success": true,
  "duplicate": false,
  "transaction": {
    "id": 1,
    "idTxn": "TXN-7701",
    "status": "APROBADA"
  },
  "analysis": {
    "anomalyDetected": false,
    "type": null,
    "severity": null,
    "transactionCount": null,
    "windowSeconds": null
  }
}
```

**Response (Anomalía Detectada en Ráfaga):**
```json
{
  "success": true,
  "duplicate": false,
  "transaction": {
    "id": 3,
    "idTxn": "TXN-7703",
    "status": "SOSPECHOSA"
  },
  "analysis": {
    "anomalyDetected": true,
    "type": "POSIBLE_FRAUDE",
    "severity": "ALTO",
    "transactionCount": 3,
    "windowSeconds": 3
  }
}
```

### 8.2 Transacción Duplicada Idéntica (200 OK)
Si se envía el mismo `idTxn` con idéntico hash:
```json
{
  "success": true,
  "duplicate": true,
  "transaction": {
    "id": 1,
    "idTxn": "TXN-7701",
    "status": "APROBADA"
  },
  "analysis": {
    "anomalyDetected": false,
    "type": null,
    "severity": null,
    "transactionCount": null,
    "windowSeconds": null
  }
}
```

### 8.3 Error de Integridad de Hash (400 Bad Request)
```json
{
  "success": false,
  "error": {
    "code": "HASH_INVALID",
    "message": "Hash inválido para idTxn=TXN-7701"
  }
}
```

---

## 9. Tabla de Decisiones de Diseño

| Tema | Decisión Implementada | Razón Técnica / Arquitectura |
|---|---|---|
| **Formato de `idTxn`** | String 1 a 64 caracteres con índice UNIQUE. | Permite identificadores alfanuméricos bancarios (UUIDs, hashes o secuencias). |
| **Zona Horaria** | Fechas en UTC en BD; interpretación de entrada y franjas en `America/Bogota` (UTC-5). | Consistencia en persistencia e indexación temporal sin ambigüedad por horario de verano. |
| **Tiempo de la Ventana** | Hora del servidor (`received_at`, UTC). | Impide que un atacante evada la ventana manipulando timestamps en el cliente. |
| **Validación de Clock Skew** | Se rechaza con HTTP 422 si `|server - client| > MAX_CLOCK_SKEW_SECONDS` (300s). | Protege la coherencia del registro sin penalizar desincronizaciones de red menores. |
| **Integridad sin Secreto** | SHA-256 canónico documentado como prueba de integridad. | Comprueba que el paquete no sufrió corrupción en tránsito. No autentica autoría sin clave simétrica. |
| **Idempotencia y Duplicados** | Mismo `idTxn` e igual hash $\rightarrow$ HTTP 200 `duplicate: true`. Mismo `idTxn` con datos distintos $\rightarrow$ HTTP 409 Conflict. | Cumple el principio REST de idempotencia y previene ataques de suplantación de ID. |
| **Usuarios Bloqueados** | Persiste transacción con estado `RECHAZADA` y responde HTTP 403 Forbidden. | Conserva trazabilidad forense del intento sin afectar el cálculo de la ventana deslizante. |
| **Concurrencia en Endpoints** | Endpoints síncronos (`def`) en hilo dedicado con `threading.Lock` por usuario. | Máxima predictibilidad y protección contra condiciones de carrera en ráfagas simultáneas. |
| **Chart.js Local** | Servido directamente desde `static/vendor/chart.umd.js`. | La demostración funciona 100% desconectada sin requerir CDNs externas. |

---

## 10. Manejo de Zonas Horarias (UTC y Bogotá)

1. **Almacenamiento:** Todas las columnas de fecha (`fecha_txn`, `fecha_recepcion`, `fecha_creacion`, `fecha_actualizacion`) se almacenan en UTC.
2. **Evaluación de Franjas de Fraude:** Al procesar la transacción, `received_at` se proyecta a la zona `America/Bogota` (UTC-5) para determinar si corresponde a Mañana, Tarde o Noche.
3. **Frontend:** Las fechas enviadas por el navegador se formatean en hora local con 3 dígitos de milisegundos (`YYYY-MM-DDTHH:MM:SS.mmm`), requeridos por el validador estricto de Pydantic.

---

## 11. Limitaciones Identificadas

1. **Memoria por Proceso:** El estado de las ventanas deslizantes reside actualmente en la memoria RAM del proceso Uvicorn (`collections.deque`). Si se escala horizontalmente a múltiples réplicas o workers sin afinidad de sesión, una transacción de un usuario podría llegar a una instancia distinta a la anterior.
2. **Autenticación del Emisor:** El hash SHA-256 garantiza **integridad** (que los datos no fueron alterados en el trayecto), pero no **autenticidad** (cualquiera conociendo el formato canónico puede generar un hash válido).

---

## 12. Hoja de Ruta y Evolución Futura

1. **Ventanas Distribuidas con Redis:** Migrar los deques locales a estructuras de datos ordenadas en Redis (`ZADD` con score timestamp y `ZREMRANGEBYSCORE`), permitiendo escalar horizontalmente a decenas de workers FastAPI sin pérdida de estado.
2. **Autenticación con HMAC-SHA256 y API Keys:** Introducir un secreto compartido por entidad comercial para calcular un HMAC, garantizando autenticidad y no repudio.
3. **Motor de Machine Learning (Isolation Forest / Autoencoders):** Complementar la regla de ventana deslizante con un modelo de detección de anomalías contextuales (monto atípico por usuario, geolocalización o frecuencia histórica).
4. **Rate Limiting Distribuido:** Integrar límites de tasa por IP/API Key mediante tokens en memoria para mitigar ráfagas a nivel perimetral.
5. **Observabilidad:** Métricas con Prometheus y visualización de trazas distribuidas con OpenTelemetry.
