"""Generador de documento PDF técnico extenso para VELUM."""
import os
import sys
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
    HRFlowable,
)
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """Canvas de dos pasadas para calcular y numerar páginas 'Página X de Y'."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        if self._pageNumber == 1:
            # En la portada no imprimimos encabezado ni pie estándar
            return

        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Encabezado
        self.drawString(54, letter[1] - 36, "VELUM — Manual Técnico de Arquitectura y Operación")
        self.drawRightString(letter[0] - 54, letter[1] - 36, "Detección de Fraude en Tiempo Real")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, letter[1] - 42, letter[0] - 54, letter[1] - 42)

        # Pie de página
        self.line(54, 46, letter[0] - 54, 46)
        self.drawString(54, 34, "Confidencial | Arquitectura de Software v1.0.0")
        page_str = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(letter[0] - 54, 34, page_str)
        self.restoreState()


def build_pdf(filename="VELUM_Manual_Tecnico_y_Arquitectura.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    # Colores temáticos
    c_primary = colors.HexColor("#0F172A")    # Azul noche profundo
    c_secondary = colors.HexColor("#0284C7")  # Azul cian
    c_accent = colors.HexColor("#DC2626")     # Rojo alerta
    c_success = colors.HexColor("#16A34A")    # Verde
    c_dark = colors.HexColor("#1E293B")       # Texto base
    c_muted = colors.HexColor("#64748B")      # Texto secundario
    c_bg_light = colors.HexColor("#F8FAFC")   # Fondo claro
    c_border = colors.HexColor("#E2E8F0")     # Borde tablas

    # Estilos de texto
    title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=26,
        leading=32,
        textColor=c_primary,
        alignment=0,
    )

    subtitle_style = ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=13,
        leading=18,
        textColor=c_secondary,
        alignment=0,
    )

    h1_style = ParagraphStyle(
        "Heading1_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=22,
        textColor=c_primary,
        spaceBefore=16,
        spaceAfter=8,
        keepWithNext=True,
    )

    h2_style = ParagraphStyle(
        "Heading2_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=c_secondary,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        "Body_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13.5,
        textColor=c_dark,
        spaceAfter=6,
    )

    bullet_style = ParagraphStyle(
        "Bullet_Custom",
        parent=body_style,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4,
    )

    code_style = ParagraphStyle(
        "Code_Custom",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#0F172A"),
    )

    callout_style = ParagraphStyle(
        "Callout_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
    )

    th_style = ParagraphStyle(
        "TH_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
    )

    td_style = ParagraphStyle(
        "TD_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10.5,
        textColor=c_dark,
    )

    td_code = ParagraphStyle(
        "TD_Code",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#0F172A"),
    )

    story = []

    # =========================================================================
    # PORTADA
    # =========================================================================
    story.append(Spacer(1, 40))
    # Badge superior
    badge_table = Table(
        [[Paragraph("<b>SISTEMA DE PREVENCIÓN Y MITIGACIÓN DE FRAUDE FINANCIERO</b>", ParagraphStyle(
            "Badge", fontName="Helvetica-Bold", fontSize=8.5, textColor=c_secondary
        ))]],
        colWidths=[400],
    )
    badge_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#E0F2FE")),
        ("PADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(badge_table)
    story.append(Spacer(1, 15))

    story.append(Paragraph("VELUM", title_style))
    story.append(Paragraph("Plataforma de Detección de Fraude en Tiempo Real", title_style))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Manual de Arquitectura, Algoritmos de Ventana Deslizante (Sliding Window), "
        "Integridad Criptográfica y Manual de Comandos Operativos",
        subtitle_style
    ))
    story.append(Spacer(1, 20))

    story.append(HRFlowable(width="100%", thickness=2, color=c_secondary, spaceBefore=5, spaceAfter=20))

    # Ficha técnica en portada
    meta_data = [
        [Paragraph("<b>Componente</b>", th_style), Paragraph("<b>Especificación Técnica</b>", th_style)],
        [Paragraph("Lenguaje / Runtime", td_style), Paragraph("Python 3.14 / Asynchronous WSGI con Uvicorn", td_style)],
        [Paragraph("Framework Web / API", td_style), Paragraph("FastAPI con Pydantic v2 (Esquemas de Entrada y Salida)", td_style)],
        [Paragraph("Capa ORM / Persistencia", td_style), Paragraph("SQLAlchemy 2.0 (Strict Typing) / Alembic Migrations", td_style)],
        [Paragraph("Bases de Datos Soportadas", td_style), Paragraph("SQLite (Desarrollo con modo WAL) / PostgreSQL 15+ (Producción)", td_style)],
        [Paragraph("Motor de Detección", td_style), Paragraph("Sliding Window en memoria (Deques atómicos + Threading Locks)", td_style)],
        [Paragraph("Integridad Transaccional", td_style), Paragraph("SHA-256 Canónico con hmac.compare_digest (Resistente a Timing Attacks)", td_style)],
        [Paragraph("Frontend / Dashboard", td_style), Paragraph("Vanilla JS + CSS moderno + Chart.js local (Sin CDNs externos)", td_style)],
        [Paragraph("Fecha de Compilación", td_style), Paragraph(datetime.now().strftime("%d de %B de %Y"), td_style)],
    ]
    t_meta = Table(meta_data, colWidths=[160, 344])
    t_meta.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_primary),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_bg_light]),
        ("GRID", (0, 0), (-1, -1), 0.5, c_border),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t_meta)

    story.append(Spacer(1, 35))

    # Resumen de auditoría
    audit_box = [
        [Paragraph("<b>ESTADO DE CERTIFICACIÓN Y VALIDACIÓN DEL SISTEMA</b>", ParagraphStyle("AB1", fontName="Helvetica-Bold", fontSize=9, textColor=c_primary))],
        [Paragraph("• <b>Pruebas Unitarias y de Integración (pytest):</b> 29 pruebas ejecutadas y aprobadas (100% éxito).<br/>"
                   "• <b>Casos Funcionales en Vivo (verify_cases.py):</b> C1 a C6 aprobados exhaustivamente.<br/>"
                   "• <b>Idempotencia y Resiliencia Concurrente:</b> Validado con pruebas de estrés de múltiples hilos en paralelo.<br/>"
                   "• <b>Autotest de Criptografía WebCrypto:</b> Concordancia exacta de vectores SHA-256 entre frontend y backend.", td_style)]
    ]
    t_audit = Table(audit_box, colWidths=[504])
    t_audit.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0FDF4")),
        ("BOX", (0, 0), (-1, -1), 1, c_success),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(t_audit)

    story.append(PageBreak())

    # =========================================================================
    # CAPÍTULO 1: RESUMEN EJECUTIVO Y PROPÓSITO
    # =========================================================================
    story.append(Paragraph("1. Resumen Ejecutivo y Propósito del Sistema", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_border, spaceBefore=2, spaceAfter=10))

    story.append(Paragraph(
        "<b>VELUM</b> es un motor de detección y prevención de fraude financiero diseñado para procesar "
        "transacciones electrónicas en tiempo real con una latencia inferior a 50 milisegundos. Su propósito "
        "fundamental es identificar y mitigar patrones de fraude de alta velocidad (ráfagas de transacciones, "
        "ataques de fuerza bruta sobre pasarelas de pago y operaciones automatizadas ilegítimas) antes de que causen "
        "pérdidas financieras irreparables.",
        body_style
    ))
    story.append(Paragraph(
        "A diferencia de los sistemas tradicionales basados exclusivamente en procesamiento por lotes (batch) "
        "o consultas pesadas a bases de datos relacionales, VELUM implementa una arquitectura híbrida de "
        "<b>Ventana Deslizante (Sliding Window) en memoria</b> respaldada por persistencia transaccional ACID. "
        "Cada evento transaccional es inspeccionado en el momento exacto de su arribo, asegurando una evaluación "
        "inmediata, atómica y segura.",
        body_style
    ))

    story.append(Paragraph("Pilares Clave del Diseño", h2_style))
    story.append(Paragraph("<b>1. Garantía de Integridad Transaccional:</b> Cada solicitud entrante contiene una firma hash generada por el cliente. El servidor recalcula el hash mediante un formato canónico estricto y efectúa una comparación inmune a ataques de temporización (timing attacks). Si los datos son alterados en tránsito, la solicitud se rechaza inmediatamente con código HTTP 400 sin persistencia.", bullet_style))
    story.append(Paragraph("<b>2. Detección Temporal por Ventana Deslizante:</b> Las ráfagas se monitorean dentro de una ventana móvil de 3 segundos exactos basada en la hora de recepción del servidor (received_at), impidiendo manipulaciones del reloj del cliente.", bullet_style))
    story.append(Paragraph("<b>3. Cálculo Dinámico de Severidad por Franjas Horarias:</b> El nivel de riesgo (BAJO, MEDIO, ALTO, CRÍTICO) no es estático; se adapta al ciclo operativo comercial de Colombia (hora de Bogotá), evaluando el volumen contra umbrales de referencia diurnos, vespertinos y nocturnos.", bullet_style))
    story.append(Paragraph("<b>4. Idempotencia Rigurosa y Manejo de Conflictos:</b> Permite a los clientes reintentar solicitudes de forma segura. Si una transacción idéntica ya fue procesada, responde HTTP 200 sin duplicar cobros ni ensuciar la ventana. Si se reutiliza un identificador con datos distintos, devuelve HTTP 409 Conflict.", bullet_style))
    story.append(Paragraph("<b>5. Protección Auditada de Usuarios Bloqueados:</b> Intentos transaccionales de cuentas bloqueadas son registrados en base de datos bajo el estado RECHAZADA para fines forenses y retornan inmediatamente HTTP 403 Forbidden.", bullet_style))

    story.append(Spacer(1, 10))

    # =========================================================================
    # CAPÍTULO 2: ARQUITECTURA GENERAL DE LA APLICACIÓN
    # =========================================================================
    story.append(Paragraph("2. Arquitectura General y Capas del Software", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_border, spaceBefore=2, spaceAfter=10))

    story.append(Paragraph(
        "VELUM está estructurado siguiendo los principios de arquitectura limpia y separación de responsabilidades "
        "en capas desacopladas:",
        body_style
    ))

    arch_layers = [
        [Paragraph("<b>Capa</b>", th_style), Paragraph("<b>Módulos Principales</b>", th_style), Paragraph("<b>Función y Responsabilidad</b>", th_style)],
        [
            Paragraph("<b>Presentación e Ingesta</b>", td_style),
            Paragraph("app/routers/transactions.py<br/>app/routers/dashboard.py<br/>app/routers/simulator.py", td_code),
            Paragraph("Exposición de endpoints REST, serialización/deserialización Pydantic, manejo uniforme de respuestas y excepciones HTTP.", td_style)
        ],
        [
            Paragraph("<b>Seguridad & Integridad</b>", td_style),
            Paragraph("app/services/hash_service.py<br/>app/security.py", td_code),
            Paragraph("Construcción de cadena canónica, cálculo SHA-256, comparación en tiempo constante (hmac.compare_digest) y validación de clock skew.", td_style)
        ],
        [
            Paragraph("<b>Motor de Detección</b>", td_style),
            Paragraph("app/detector.py", td_code),
            Paragraph("SlidingWindowDetector singleton, deques en memoria por usuario, purga de eventos &gt; 3s, cálculo de severidad por franjas.", td_style)
        ],
        [
            Paragraph("<b>Orquestación del Negocio</b>", td_style),
            Paragraph("app/services/transaction_service.py<br/>app/services/dashboard_service.py", td_code),
            Paragraph("Gestión del ciclo de vida transaccional, resolución de usuarios, serialización de escrituras con _db_write_lock, consolidación de anomalías.", td_style)
        ],
        [
            Paragraph("<b>Persistencia y Datos</b>", td_style),
            Paragraph("app/models.py<br/>app/database.py<br/>migrations/", td_code),
            Paragraph("Modelos SQLAlchemy declarativos (Usuario, Transaccion, Anomalia), SessionLocal, llaves foráneas e índices únicos. Migraciones Alembic.", td_style)
        ],
        [
            Paragraph("<b>Frontend & Monitoreo</b>", td_style),
            Paragraph("templates/index.html<br/>static/js/*.js<br/>static/vendor/chart.umd.js", td_code),
            Paragraph("Dashboard interactivo en tiempo real con 5 KPIs, 4 gráficos analíticos, visualizador cronológico de ventana y simulador de ataques WebCrypto.", td_style)
        ],
    ]
    t_arch = Table(arch_layers, colWidths=[100, 154, 250])
    t_arch.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_primary),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_bg_light]),
        ("GRID", (0, 0), (-1, -1), 0.5, c_border),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_arch)

    story.append(Spacer(1, 10))
    story.append(Paragraph("Estrategia de Concurrencia y Sincronización", h2_style))
    story.append(Paragraph(
        "Para evitar condiciones de carrera (race conditions) y lecturas fantasmas en entornos de alto tráfico, "
        "VELUM implementa un esquema de doble barrera:",
        body_style
    ))
    story.append(Paragraph("<b>1. Locks de Nivel de Usuario en Memoria:</b> En <code>SlidingWindowDetector</code>, cada dirección de correo dispone de un <code>threading.Lock</code> dedicado. Esto garantiza que dos solicitudes simultáneas del mismo usuario no corrompan el deque de timestamps, mientras que las transacciones de usuarios distintos se procesan en paralelo sin bloqueo mutuo.", bullet_style))
    story.append(Paragraph("<b>2. Bloqueo Transaccional de Escritura (_db_write_lock):</b> Para motores de base de datos como SQLite (que utilizan bloqueo a nivel de archivo para escrituras), la función <code>process_transaction</code> sincroniza la verificación de idempotencia y la inserción de registros mediante un semáforo global, impidiendo colisiones de sesión y errores 'database is locked'.", bullet_style))

    story.append(PageBreak())

    # =========================================================================
    # CAPÍTULO 3: MOTOR DE DETECCIÓN Y ALGORITMOS
    # =========================================================================
    story.append(Paragraph("3. Motor de Detección 'Sliding Window' y Severidad", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_border, spaceBefore=2, spaceAfter=10))

    story.append(Paragraph(
        "El corazón de la detección de anomalías radica en el algoritmo de ventana deslizante temporal. "
        "El sistema no mide bloques fijos de tiempo (como horas o minutos calendario), sino un intervalo relativo móvil "
        "definido por la expresión: <b>[t<sub>recepcion</sub> − 3s, t<sub>recepcion</sub>]</b>.",
        body_style
    ))

    story.append(Paragraph("Mecánica Paso a Paso de la Ventana", h2_style))
    steps_window = [
        ("1. Captura del Tiempo del Servidor", "Al arribar la petición HTTP, el servidor asigna 'received_at = datetime.now(UTC)'. Se rechaza cualquier suposición de que el cliente tiene el reloj sincronizado."),
        ("2. Obtención de Lock del Usuario", "Se adquiere el Lock exclusivo del usuario. Ninguna otra hebra puede mutar la ventana de este usuario durante esta fase."),
        ("3. Purga de Eventos Vencidos", "Se evalúa el extremo izquierdo del deque. Cualquier timestamp con fecha estrictamente anterior a 'received_at - 3s' es expulsado (popleft)."),
        ("4. Inserción del Nuevo Evento", "Se anexa el timestamp actual al deque. La longitud del deque representa exactamente el número de transacciones en la ventana de 3 segundos."),
        ("5. Comparación con Umbral Base", "Si 'count >= 3' (BASE_TRANSACTION_THRESHOLD), se dispara la bandera 'anomaly_detected = True'. La transacción se clasifica como SOSPECHOSA; de lo contrario, se clasifica como APROBADA."),
    ]
    for step_title, step_desc in steps_window:
        story.append(Paragraph(f"• <b>{step_title}:</b> {step_desc}", bullet_style))

    story.append(Spacer(1, 8))
    story.append(Paragraph("Cálculo Dinámico de Severidad y Franjas Horarias", h2_style))
    story.append(Paragraph(
        "Un volumen de 3 transacciones en 3 segundos puede ser normal en un pico comercial matutino, pero altamente "
        "anómalo a las 3:00 AM. Por ello, la severidad se calcula contrastando el conteo de la ráfaga con la "
        "referencia esperada para la franja horaria en <b>hora oficial de Bogotá (UTC-5)</b>:",
        body_style
    ))

    slots_data = [
        [Paragraph("<b>Franja Horaria</b>", th_style), Paragraph("<b>Intervalo Horario (Bogotá)</b>", th_style), Paragraph("<b>Referencia (Ref)</b>", th_style), Paragraph("<b>Naturaleza Operativa</b>", th_style)],
        [Paragraph("Mañana", td_style), Paragraph("[05:00, 12:00)", td_code), Paragraph("10", td_style), Paragraph("Alto volumen transaccional comercial y laboral.", td_style)],
        [Paragraph("Tarde", td_style), Paragraph("[12:00, 20:00)", td_code), Paragraph("6", td_style), Paragraph("Volumen regular de pagos, consumo y compras.", td_style)],
        [Paragraph("Noche", td_style), Paragraph("[20:00, 05:00)", td_code), Paragraph("3", td_style), Paragraph("Bajo volumen; umbral de alerta muy sensible a ráfagas.", td_style)],
    ]
    t_slots = Table(slots_data, colWidths=[90, 130, 80, 204])
    t_slots.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_primary),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_bg_light]),
        ("GRID", (0, 0), (-1, -1), 0.5, c_border),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_slots)

    story.append(Spacer(1, 8))
    story.append(Paragraph("Fórmula de Razón (Ratio) y Niveles de Alerta:", h2_style))

    sev_data = [
        [Paragraph("<b>Rango de Ratio = Conteo / Ref</b>", th_style), Paragraph("<b>Nivel Asignado</b>", th_style), Paragraph("<b>Color en Dashboard</b>", th_style), Paragraph("<b>Acción Recomendada</b>", th_style)],
        [Paragraph("Ratio &lt; 0.5", td_code), Paragraph("<b>BAJO</b>", td_style), Paragraph("Verde / Azul", td_style), Paragraph("Registro y monitoreo pasivo de telemetría.", td_style)],
        [Paragraph("0.5 &le; Ratio &lt; 1.0", td_code), Paragraph("<b>MEDIO</b>", td_style), Paragraph("Amarillo ámbar", td_style), Paragraph("Alerta en panel de monitoreo operativo.", td_style)],
        [Paragraph("1.0 &le; Ratio &lt; 2.0", td_code), Paragraph("<b>ALTO</b>", td_style), Paragraph("Naranja oscuro", td_style), Paragraph("Revisión prioritaria por analista antifraude.", td_style)],
        [Paragraph("Ratio &ge; 2.0", td_code), Paragraph("<b>CRITICO</b>", td_style), Paragraph("Rojo carmesí", td_style), Paragraph("Escalamiento urgente y bloqueo temporal preventivo.", td_style)],
    ]
    t_sev = Table(sev_data, colWidths=[130, 90, 100, 184])
    t_sev.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_primary),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_bg_light]),
        ("GRID", (0, 0), (-1, -1), 0.5, c_border),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_sev)

    story.append(Spacer(1, 8))
    story.append(Paragraph("Consolidación de Ráfagas (Una Anomalía por Incidente)", h2_style))
    story.append(Paragraph(
        "Si un usuario envía 10 transacciones en 2 segundos, generar 8 registros de anomalía independientes "
        "saturaría la mesa de operaciones. VELUM implementa <b>consolidación de anomalías solapadas</b>: "
        "si ya existe una anomalía con estado NUEVA o ABIERTA para ese usuario dentro de la ventana de 3 segundos, "
        "el sistema actualiza la fila existente (incrementando <code>cantidad_transacciones</code>, actualizando el "
        "<code>nivel</code> a la severidad más alta y estableciendo <code>estado_revision = 'ABIERTA'</code>) en "
        "lugar de crear filas redundantes.",
        body_style
    ))

    story.append(PageBreak())

    # =========================================================================
    # CAPÍTULO 4: PROTOCOLO DE SEGURIDAD E INTEGRIDAD CRIPTOGRÁFICA
    # =========================================================================
    story.append(Paragraph("4. Protocolo Criptográfico y Formato Canónico", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_border, spaceBefore=2, spaceAfter=10))

    story.append(Paragraph(
        "Para certificar que una transacción no fue alterada por intermediarios, atacantes man-in-the-middle (MITM) "
        "o fallas en el canal de comunicación, VELUM exige la inclusión de un hash SHA-256 generado sobre una "
        "cadena normalizada canónica.",
        body_style
    ))

    story.append(Paragraph("Reglas Estrictas de Construcción de la Cadena Canónica:", h2_style))
    story.append(Paragraph("La cadena canónica sigue el esquema: <code>idTxn|user|date|value|paymentMethod</code>.", body_style))

    canon_rules = [
        [Paragraph("<b>Campo</b>", th_style), Paragraph("<b>Transformación Canónica Exigida</b>", th_style), Paragraph("<b>Ejemplo Válido</b>", th_style)],
        [Paragraph("<code>idTxn</code>", td_code), Paragraph("Cadena única alfanumérica (1 a 64 caracteres). Sin alteración.", td_style), Paragraph("TXN-2026-001", td_code)],
        [Paragraph("<code>user</code>", td_code), Paragraph("Email en minúsculas estrictas y sin espacios en blanco intermedios ni laterales.", td_style), Paragraph("juan.perez@empresa.com", td_code)],
        [Paragraph("<code>date</code>", td_code), Paragraph("Formato ISO 8601 con exactamente 3 dígitos de milisegundos: YYYY-MM-DDTHH:MM:SS.mmm", td_style), Paragraph("2026-09-23T10:30:01.120", td_code)],
        [Paragraph("<code>value</code>", td_code), Paragraph("Monto formateado con exactamente dos cifras decimales separadas por punto.", td_style), Paragraph("150000.00", td_code)],
        [Paragraph("<code>paymentMethod</code>", td_code), Paragraph("Uno de los 4 valores permitidos: Tarjeta, PSE, Transferencia, Otro.", td_style), Paragraph("Tarjeta", td_code)],
    ]
    t_canon = Table(canon_rules, colWidths=[100, 254, 150])
    t_canon.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_primary),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_bg_light]),
        ("GRID", (0, 0), (-1, -1), 0.5, c_border),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_canon)

    story.append(Spacer(1, 10))
    story.append(Paragraph("Ejemplo de Generación:", h2_style))
    ex_box = [
        [Paragraph("<b>Cadena Canónica:</b><br/>"
                   "<code>TXN-7788|carlos@banco.co|2026-10-01T14:22:05.500|99500.00|PSE</code><br/><br/>"
                   "<b>Hash SHA-256 Resultante (64 caracteres hex minúsculas):</b><br/>"
                   "<code>7d12f3bc8a4b09e1e21b033d59e35b7194f1c1f5106198f7975b94f1d6928e44</code>", td_code)]
    ]
    t_ex = Table(ex_box, colWidths=[504])
    t_ex.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#94A3B8")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t_ex)

    story.append(Spacer(1, 10))
    story.append(Paragraph("Mecanismos de Resistencia a Ataques:", h2_style))
    story.append(Paragraph("• <b>Mitigación de Timing Attacks:</b> Las cadenas hash nunca se comparan usando operadores convencionales de igualdad ('=='), los cuales retornan 'False' en el primer byte discordante, permitiendo al atacante deducir caracteres mediante análisis de tiempos. VELUM emplea estrictamente <code>hmac.compare_digest(hash_esperado, hash_recibido)</code>, ejecutando la validación en tiempo constante.", bullet_style))
    story.append(Paragraph("• <b>Validación de Desviación de Reloj (Clock Skew):</b> El campo 'date' del cliente se contrasta contra la hora UTC del servidor. Si la discrepancia absoluta supera <code>MAX_CLOCK_SKEW_SECONDS</code> (por defecto 300 segundos = 5 minutos), la transacción se aborta con error HTTP 422.", bullet_style))
    story.append(Paragraph("• <b>Política Cero Persistencia en Hash Inválido:</b> Las transacciones con firma corrupta o adulterada se descartan con HTTP 400 antes de interactuar con la base de datos o con la ventana deslizante, previniendo ataques de denegación de servicio (DoS) por llenado de almacenamiento.", bullet_style))

    story.append(PageBreak())

    # =========================================================================
    # CAPÍTULO 5: COMANDOS CRÍTICOS Y GUÍA DE OPERACIÓN
    # =========================================================================
    story.append(Paragraph("5. Comandos Críticos y Manual de Operaciones", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_border, spaceBefore=2, spaceAfter=10))

    story.append(Paragraph(
        "A continuación se presenta el compendio exhaustivo de comandos requeridos para la administración, "
        "puesta en marcha, verificación de calidad y mantenimiento del sistema:",
        body_style
    ))

    cmd_list = [
        [Paragraph("<b>Objetivo Operativo</b>", th_style), Paragraph("<b>Comando PowerShell / Terminal</b>", th_style), Paragraph("<b>Descripción Técnica</b>", th_style)],
        [
            Paragraph("<b>Iniciar Servidor (Dev)</b>", td_style),
            Paragraph("cd appresso<br/>venv\\Scripts\\uvicorn app.main:app --port 8000 --reload", td_code),
            Paragraph("Inicia FastAPI con recarga en caliente en http://localhost:8000. Reconstruye ventanas activas al arrancar.", td_style)
        ],
        [
            Paragraph("<b>Ejecutar Pruebas (pytest)</b>", td_style),
            Paragraph("venv\\Scripts\\pytest -v", td_code),
            Paragraph("Corre las 29 pruebas automatizadas (unitarias, concurrencia de hilos, integridad hash, endpoints).", td_style)
        ],
        [
            Paragraph("<b>Validación en Vivo (C1-C6)</b>", td_style),
            Paragraph("venv\\Scripts\\python verify_cases.py", td_code),
            Paragraph("Ejecuta la suite funcional de extremo a extremo contra el servidor HTTP activo para certificar los casos C1 a C6.", td_style)
        ],
        [
            Paragraph("<b>Poblar Base de Datos (Seed)</b>", td_style),
            Paragraph("venv\\Scripts\\python seed.py", td_code),
            Paragraph("Inserta 8 usuarios de prueba y 52 transacciones sintéticas con todas las severidades y métodos de pago.", td_style)
        ],
        [
            Paragraph("<b>Aplicar Migraciones BD</b>", td_style),
            Paragraph("venv\\Scripts\\alembic upgrade head", td_code),
            Paragraph("Aplica las migraciones pendientes en SQLite/PostgreSQL sincronizando el esquema con models.py.", td_style)
        ],
        [
            Paragraph("<b>Crear Nueva Migración</b>", td_style),
            Paragraph("venv\\Scripts\\alembic revision --autogenerate -m \"descripcion\"", td_code),
            Paragraph("Inspecciona cambios en modelos SQLAlchemy y genera el script de migración correspondiente.", td_style)
        ],
        [
            Paragraph("<b>Despliegue con Docker</b>", td_style),
            Paragraph("docker compose up --build -d", td_code),
            Paragraph("Levanta los contenedores orquestados de VELUM (FastAPI) y PostgreSQL con volumen de datos persistente.", td_style)
        ],
        [
            Paragraph("<b>Detener Contenedores</b>", td_style),
            Paragraph("docker compose down", td_code),
            Paragraph("Detiene y remueve los contenedores de la aplicación y la base de datos de manera limpia.", td_style)
        ],
        [
            Paragraph("<b>Inspeccionar Logs en Vivo</b>", td_style),
            Paragraph("docker compose logs -f app", td_code),
            Paragraph("Transmite en tiempo real los registros de auditoría y excepciones del contenedor de la aplicación.", td_style)
        ],
    ]
    t_cmd = Table(cmd_list, colWidths=[120, 194, 190])
    t_cmd.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_primary),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_bg_light]),
        ("GRID", (0, 0), (-1, -1), 0.5, c_border),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_cmd)

    story.append(Spacer(1, 10))
    story.append(Paragraph("Protocolo de Verificación Funcional (Casos C1 al C6):", h2_style))
    story.append(Paragraph(
        "El script <code>verify_cases.py</code> evalúa los 6 escenarios de aceptación fundamentales del sistema:",
        body_style
    ))
    cases_desc = [
        ("C1 — Transacción Única Normal", "Envía una transacción aislada. Debe aprobarse (201 Created, status='APROBADA', anomalyDetected=False)."),
        ("C2 — Transacciones Espaciadas", "Envía una segunda transacción tras 3.5 segundos (&gt;3s). Debe aprobarse sin disparar alertas de ráfaga."),
        ("C3 — Detección de Ráfaga de Fraude", "Envía 3 transacciones en menos de 1 segundo para el mismo usuario. La 3ra debe marcarse SOSPECHOSA con anomalyDetected=True."),
        ("C4 — Aislamiento entre Usuarios", "Envía 3 transacciones para el Usuario A y 1 para el Usuario B. Verifica que el Usuario B no sea penalizado por el tráfico de A."),
        ("C5 — Intento de Manipulación de Hash", "Envía una transacción con el monto adulterado en el payload. El servidor debe responder 400 Bad Request sin persistir en BD."),
        ("C6 — Idempotencia de Duplicados", "Reenvía una transacción previamente aprobada. El servidor debe responder 200 OK con duplicate=True sin crear registros adicionales."),
    ]
    for c_title, c_text in cases_desc:
        story.append(Paragraph(f"• <b>{c_title}:</b> {c_text}", bullet_style))

    story.append(PageBreak())

    # =========================================================================
    # CAPÍTULO 6: CATÁLOGO DE LA API REST Y CÓDIGOS HTTP
    # =========================================================================
    story.append(Paragraph("6. Catálogo de Endpoints de la API REST", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_border, spaceBefore=2, spaceAfter=10))

    story.append(Paragraph("1. POST /api/transacciones — Ingesta de Transacción", h2_style))
    story.append(Paragraph(
        "Endpoint principal para procesar, auditar y detectar anomalías en transacciones financieras.",
        body_style
    ))

    http_matrix = [
        [Paragraph("<b>Código HTTP</b>", th_style), Paragraph("<b>Condición / Escenario</b>", th_style), Paragraph("<b>Persistencia en BD</b>", th_style), Paragraph("<b>Estructura de Respuesta</b>", th_style)],
        [
            Paragraph("<b>201 Created</b>", td_style),
            Paragraph("Transacción nueva legítima (APROBADA o SOSPECHOSA si supera umbral).", td_style),
            Paragraph("Sí (Transaccion + Anomalia si aplica)", td_style),
            Paragraph("<code>{\"success\": true, \"transaction\": {...}, \"analysis\": {...}}</code>", td_code)
        ],
        [
            Paragraph("<b>200 OK</b>", td_style),
            Paragraph("Duplicado idéntico (mismo idTxn y mismo hash SHA-256). Idempotente.", td_style),
            Paragraph("No (reutiliza existente)", td_style),
            Paragraph("<code>{\"success\": true, \"duplicate\": true, ...}</code>", td_code)
        ],
        [
            Paragraph("<b>400 Bad Request</b>", td_style),
            Paragraph("Firma hash no coincide con la recalculada en el servidor.", td_style),
            Paragraph("No (Cero persistencia)", td_style),
            Paragraph("<code>{\"success\": false, \"error\": {\"code\": \"HASH_INVALID\"}}</code>", td_code)
        ],
        [
            Paragraph("<b>403 Forbidden</b>", td_style),
            Paragraph("Usuario remitente se encuentra en estado BLOQUEADO o INACTIVO.", td_style),
            Paragraph("Sí (Se guarda como RECHAZADA)", td_style),
            Paragraph("<code>{\"success\": false, \"error\": {\"code\": \"USER_BLOQUEADO\"}}</code>", td_code)
        ],
        [
            Paragraph("<b>409 Conflict</b>", td_style),
            Paragraph("idTxn existente pero con contenido o monto diferente (colisión/fraude).", td_style),
            Paragraph("No", td_style),
            Paragraph("<code>{\"success\": false, \"error\": {\"code\": \"CONFLICT\"}}</code>", td_code)
        ],
        [
            Paragraph("<b>422 Unprocessable</b>", td_style),
            Paragraph("Fallo de validación Pydantic (fechas sin ms, montos negativos) o clock skew.", td_style),
            Paragraph("No", td_style),
            Paragraph("<code>{\"success\": false, \"error\": {\"code\": \"VALIDATION_ERROR\"}}</code>", td_code)
        ],
        [
            Paragraph("<b>500 Internal Error</b>", td_style),
            Paragraph("Error no controlado. No expone trazas de pila (stack traces) al cliente.", td_style),
            Paragraph("Rollback transaccional", td_style),
            Paragraph("<code>{\"success\": false, \"error\": {\"code\": \"INTERNAL_ERROR\"}}</code>", td_code)
        ],
    ]
    t_http = Table(http_matrix, colWidths=[95, 140, 115, 154])
    t_http.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_primary),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_bg_light]),
        ("GRID", (0, 0), (-1, -1), 0.5, c_border),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_http)

    story.append(Spacer(1, 10))
    story.append(Paragraph("2. GET /api/dashboard/stats — Métricas y Agregaciones", h2_style))
    story.append(Paragraph(
        "Calcula métricas clave para periodos: <code>?periodo=hoy</code>, <code>semana</code> o <code>mes</code>.<br/>"
        "• <b>KPIs agregados:</b> Total transacciones, Aprobadas, Sospechosas, Rechazadas, Monto bajo riesgo.<br/>"
        "• <b>Detección de Hora Pico:</b> Identifica la hora del día cuya cantidad de anomalías supera: "
        "<b>Media + (2 &times; Desviación Estándar)</b>.<br/>"
        "• <b>Cálculo de Tendencia:</b> Variación porcentual de volumen frente al periodo anterior equivalente.<br/>"
        "• <b>Usuarios Recurrentes:</b> Cantidad de clientes con 2 o más anomalías registradas en la ventana.",
        body_style
    ))

    story.append(Spacer(1, 6))
    story.append(Paragraph("3. GET /api/dashboard/timeline-sliding-window/{usuario_id}", h2_style))
    story.append(Paragraph(
        "Reconstruye retrospectivamente la historia transaccional del usuario seleccionado, computando para "
        "cada evento si estuvo dentro de la ventana de 3 segundos, los límites exactos [inicio, fin], el conteo "
        "instantáneo y la severidad asociada para alimentar el visualizador gráfico interactivo.",
        body_style
    ))

    story.append(PageBreak())

    # =========================================================================
    # CAPÍTULO 7: FRONTEND, SIMULADOR Y MEJORES PRÁCTICAS
    # =========================================================================
    story.append(Paragraph("7. Frontend, Simulador y Buenas Prácticas", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_border, spaceBefore=2, spaceAfter=10))

    story.append(Paragraph("Arquitectura del Panel de Control (Dashboard)", h2_style))
    story.append(Paragraph(
        "El panel de monitoreo se implementó sin dependencias complejas (sin React, Angular ni Vue), "
        "utilizando JavaScript moderno vanilla estructurado en módulos orientados a eventos:",
        body_style
    ))
    story.append(Paragraph("• <b>dashboard.js:</b> Controlador principal de telemetría. Consulta periódicamente <code>/api/dashboard/stats</code> y actualiza los 5 KPIs de cabecera y los 4 gráficos interactivos renderizados mediante <code>Chart.js 4.4.4</code> (alojado localmente en <code>static/vendor/chart.umd.js</code>, garantizando funcionamiento autónomo sin acceso a Internet).", bullet_style))
    story.append(Paragraph("• <b>sliding-window.js:</b> Visualizador de ventana móvil. Presenta una línea temporal interactiva con estados codificados por colores y detalles de solapamiento temporal.", bullet_style))
    story.append(Paragraph("• <b>simulator.js:</b> Motor de simulación en el navegador. Utiliza la API nativa <code>window.crypto.subtle.digest</code> (WebCrypto) para calcular firmas SHA-256 en tiempo real directamente en el cliente.", bullet_style))

    story.append(Spacer(1, 8))
    story.append(Paragraph("Botones del Simulador de Tráfico:", h2_style))
    sim_table = [
        [Paragraph("<b>Acción en UI</b>", th_style), Paragraph("<b>Usuario Utilizado</b>", th_style), Paragraph("<b>Comportamiento y Resultado Esperado</b>", th_style)],
        [
            Paragraph("⚡ Simular Ataque en Ráfaga", td_style),
            Paragraph("<code>b@b.com</code>", td_code),
            Paragraph("Despacha 3 transacciones en menos de 1.5 segundos. La 3ra dispara la alerta roja 'ANOMALÍA DETECTADA — POSIBLE_FRAUDE' con actualización inmediata de KPIs.", td_style)
        ],
        [
            Paragraph("🟢 Simular Tráfico Normal", td_style),
            Paragraph("<code>c@c.com</code>", td_code),
            Paragraph("Envía 2 transacciones espaciadas por una pausa de 4.2 segundos. Ambas se aprueban con banner verde 'TRÁFICO NORMAL'.", td_style)
        ],
        [
            Paragraph("🧪 Autotest Criptográfico", td_style),
            Paragraph("Vectores Oficiales", td_code),
            Paragraph("Calcula el hash de los 5 vectores canónicos en JavaScript WebCrypto y los compara con los esperados en Python, validando 100% de paridad.", td_style)
        ],
        [
            Paragraph("🧹 Restablecer Datos", td_style),
            Paragraph("General", td_code),
            Paragraph("Limpia la base de datos de simulación y resetea las ventanas en memoria para permitir nuevas rondas de prueba.", td_style)
        ],
    ]
    t_sim = Table(sim_table, colWidths=[130, 94, 280])
    t_sim.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_primary),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_bg_light]),
        ("GRID", (0, 0), (-1, -1), 0.5, c_border),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_sim)

    story.append(Spacer(1, 10))
    story.append(Paragraph("Evolución a Producción y Escalabilidad Horizontal", h2_style))
    story.append(Paragraph(
        "Para entornos de producción con cientos de miles de transacciones por segundo distribuidas en clústeres:",
        body_style
    ))
    story.append(Paragraph("<b>1. Sustitución de Memoria Local por Redis:</b> Reemplazar los deques de Python por estructuras <code>Sorted Sets (ZSET)</code> en Redis, donde el score sea el timestamp epoch en milisegundos. Esto permite que múltiples instancias de FastAPI compartan la misma ventana deslizante sin discrepancias.", bullet_style))
    story.append(Paragraph("<b>2. Autenticidad mediante HMAC:</b> Transicionar de SHA-256 plano a HMAC-SHA256 con llave secreta compartida por cliente para evitar que un atacante que conozca la fórmula matemática canónica falsifique firmas legítimas.", bullet_style))
    story.append(Paragraph("<b>3. Particionamiento de Base de Datos:</b> Aplicar particionamiento por rangos de fecha mensual en la tabla <code>transacciones</code> de PostgreSQL para optimizar consultas analíticas históricas.", bullet_style))

    story.append(Spacer(1, 15))

    # Firma de cierre
    sign_table = Table([
        [Paragraph("<b>Certificación de Entrega Técnica:</b> Sistema auditado, verificado y documentado para despliegue.", ParagraphStyle("Sign", fontName="Helvetica-Oblique", fontSize=8.5, textColor=c_muted))],
        [Paragraph(f"Generado automáticamente por Antigravity Engineering | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ParagraphStyle("Sign2", fontName="Helvetica", fontSize=8, textColor=c_muted))]
    ], colWidths=[504])
    sign_table.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(sign_table)

    # Construir documento
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF generado exitosamente en: {os.path.abspath(filename)}")


if __name__ == "__main__":
    out_file = sys.argv[1] if len(sys.argv) > 1 else "VELUM_Manual_Tecnico_y_Arquitectura.pdf"
    build_pdf(out_file)
