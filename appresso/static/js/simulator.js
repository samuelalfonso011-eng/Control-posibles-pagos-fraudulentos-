/**
 * VELUM — Transaction Simulator & WebCrypto SHA-256 Service
 * Genera tráfico de prueba, ataques en ráfaga (<3s), tráfico normal (>4s),
 * y ejecuta el autotest de integridad SHA-256 comparando WebCrypto vs Python.
 */

// 1. Cálculo canónico de SHA-256 en navegador con WebCrypto
async function computeHashJS(idTxn, user, date, value, paymentMethod) {
  const normUser = user.toLowerCase().trim().replace(/\s+/g, '');
  const numVal = parseFloat(value);
  const normValue = (isNaN(numVal) ? 0 : numVal).toFixed(2);
  const canonicalString = `${idTxn}|${normUser}|${date}|${normValue}|${paymentMethod}`;
  const encoder = new TextEncoder();
  const data = encoder.encode(canonicalString);
  const hashBuffer = await window.crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  return { canonicalString, hash: hashHex };
}

// 2. Formato de fecha para el backend (YYYY-MM-DDTHH:MM:SS.mmm en hora de Bogotá)
function getBogotaDateString(offsetMs = 0) {
  const d = new Date(Date.now() + offsetMs);
  const utc = d.getTime() + (d.getTimezoneOffset() * 60000);
  const bogotaTime = new Date(utc - (3600000 * 5));
  const year = bogotaTime.getFullYear();
  const month = String(bogotaTime.getMonth() + 1).padStart(2, '0');
  const day = String(bogotaTime.getDate()).padStart(2, '0');
  const hours = String(bogotaTime.getHours()).padStart(2, '0');
  const minutes = String(bogotaTime.getMinutes()).padStart(2, '0');
  const seconds = String(bogotaTime.getSeconds()).padStart(2, '0');
  const ms = String(bogotaTime.getMilliseconds()).padStart(3, '0');
  return `${year}-${month}-${day}T${hours}:${minutes}:${seconds}.${ms}`;
}

// 3. Logger visual para terminal de simulación
function logSimMessage(message, status = 'info') {
  const logEl = document.getElementById('sim-log-terminal');
  if (!logEl) return;
  const timeStr = new Date().toLocaleTimeString();
  const entry = document.createElement('div');
  entry.className = 'log-entry';
  entry.innerHTML = `
    <span class="log-time">[${timeStr}]</span>
    <span class="log-status ${status}">${message}</span>
  `;
  logEl.prepend(entry);
}

// 4. Enviar una transacción a la API REST
async function sendTransaction(idTxn, user, value, paymentMethod, dateStr = null) {
  const date = dateStr || getBogotaDateString();
  const { canonicalString, hash } = await computeHashJS(idTxn, user, date, value, paymentMethod);
  const payload = {
    idTxn: idTxn,
    user: user,
    date: date,
    value: parseFloat(value),
    paymentMethod: paymentMethod,
    hash: hash,
  };
  const res = await fetch('/api/transacciones', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  return { status: res.status, data, payload };
}

// ---------------------------------------------------------------------------
// VISUALIZADOR DE TOKENS EN TIEMPO REAL
// ---------------------------------------------------------------------------

function resetTokenVisualizer() {
  for (let k = 1; k <= 3; k++) {
    const card = document.getElementById(`token-card-${k}`);
    const timeEl = document.getElementById(`token-time-${k}`);
    const deltaEl = document.getElementById(`token-delta-${k}`);
    const statusEl = document.getElementById(`token-status-${k}`);
    if (card) {
      card.className = 'token-box token-waiting';
    }
    if (timeEl) timeEl.textContent = '--:--:--.---';
    if (deltaEl) deltaEl.textContent = 'Esperando...';
    if (statusEl) { statusEl.textContent = '⏳'; statusEl.className = 'token-icon'; }
  }
  const alarm = document.getElementById('token-alarm-box');
  if (alarm) alarm.style.display = 'none';
  const badge = document.getElementById('window-status-badge');
  if (badge) { badge.textContent = 'Ventana: Inactiva'; badge.className = 'window-badge window-inactive'; }
  const bar = document.getElementById('token-progress-bar');
  if (bar) { bar.style.width = '0%'; bar.className = 'progress-fill'; }
}

function activateTokenCard(index, timeStr, deltaStr, isAlarm) {
  const card = document.getElementById(`token-card-${index}`);
  const timeEl = document.getElementById(`token-time-${index}`);
  const deltaEl = document.getElementById(`token-delta-${index}`);
  const statusEl = document.getElementById(`token-status-${index}`);

  if (timeEl) timeEl.textContent = timeStr;
  if (deltaEl) deltaEl.textContent = deltaStr;

  if (isAlarm) {
    if (card) card.className = 'token-box token-alarm';
    if (statusEl) { statusEl.textContent = '🚨'; statusEl.className = 'token-icon token-icon-alarm'; }
  } else {
    if (card) card.className = 'token-box token-active';
    if (statusEl) { statusEl.textContent = '✅'; statusEl.className = 'token-icon token-icon-ok'; }
  }

  // Actualizar barra de progreso
  const bar = document.getElementById('token-progress-bar');
  const pcts = ['33%', '66%', '100%'];
  if (bar) {
    bar.style.width = pcts[index - 1];
    if (isAlarm) bar.className = 'progress-fill progress-alarm';
  }
}

function showTokenAlarm(deltaTotal, severity) {
  const alarm = document.getElementById('token-alarm-box');
  const badge = document.getElementById('window-status-badge');
  if (alarm) {
    alarm.style.display = 'flex';
    alarm.innerHTML = `
      <div class="alarm-icon">🚨</div>
      <div class="alarm-content">
        <div class="alarm-title">¡ALARMA DE FRAUDE ACTIVADA!</div>
        <div class="alarm-detail">
          3 tokens detectados en <strong>${deltaTotal.toFixed(3)}s</strong> 
          (ventana máxima: 3.000s) — Severidad: <strong>${severity || 'N/A'}</strong>
        </div>
      </div>
    `;
  }
  if (badge) {
    badge.textContent = '🔴 RÁFAGA DETECTADA';
    badge.className = 'window-badge window-alarm';
  }
}

// ---------------------------------------------------------------------------
// 5. Simular Ataque con visualizador de tokens paso a paso
// ---------------------------------------------------------------------------
async function simulateAttack() {
  const btn = document.getElementById('btn-sim-attack');
  const banner = document.getElementById('banner-anomaly-alert');
  const normalBanner = document.getElementById('banner-normal-alert');
  if (banner) banner.style.display = 'none';
  if (normalBanner) normalBanner.style.display = 'none';

  btn.disabled = true;
  btn.textContent = 'Ejecutando ataque en ráfaga...';

  resetTokenVisualizer();

  const badge = document.getElementById('window-status-badge');
  if (badge) { badge.textContent = '⚡ Monitoreando ventana de 3s...'; badge.className = 'window-badge window-active'; }

  logSimMessage('Iniciando simulación de ráfaga: 3 tokens para b@b.com en < 1.5s', 'info');

  const user = 'b@b.com';
  const tInicio = Date.now();
  let lastSeverity = null;

  try {
    for (let i = 1; i <= 3; i++) {
      const idTxn = `ATK-${tInicio}-${i}`;
      const value = (50000 + i * 10000).toFixed(2);
      const dateStr = getBogotaDateString();

      // Capturar tiempo exacto de envío
      const tEnvio = Date.now();
      const deltaMs = (tEnvio - tInicio) / 1000;
      const timePart = dateStr.split('T')[1]; // HH:MM:SS.mmm
      const isAlarm = (i === 3);

      // Mostrar el token en la pantalla
      activateTokenCard(i, timePart, `+${deltaMs.toFixed(3)}s desde inicio`, isAlarm);

      logSimMessage(
        `📡 Token ${i}/3 → ${timePart} | Δ +${deltaMs.toFixed(3)}s | ID: ${idTxn}`,
        isAlarm ? 'suspicious' : 'info'
      );

      const res = await sendTransaction(idTxn, user, value, 'Tarjeta', dateStr);

      if (res.status === 201) {
        const isAnomaly = res.data.analysis?.anomalyDetected;
        if (isAnomaly) {
          lastSeverity = res.data.analysis.severity;
          const totalDelta = (Date.now() - tInicio) / 1000;
          logSimMessage(
            `🚨 Token ${i}/3 [${res.data.transaction.status}] — ANOMALÍA DETECTADA | Severidad: ${lastSeverity} | Conteo: ${res.data.analysis.transactionCount} txns en 3s`,
            'suspicious'
          );
          showTokenAlarm(totalDelta, lastSeverity);
          if (banner) {
            banner.style.display = 'flex';
            banner.innerHTML = `
              <span>⚠️ ANOMALÍA DETECTADA — POSIBLE_FRAUDE</span>
              <span>Severidad: ${lastSeverity} (${res.data.analysis.transactionCount} txns en 3s)</span>
            `;
          }
        } else {
          logSimMessage(
            `✅ Token ${i}/3 [${res.data.transaction.status}] — En ventana | Conteo: ${i}/3`,
            'approved'
          );
        }
      } else {
        logSimMessage(`❌ Error en Token ${i}: HTTP ${res.status}`, 'rejected');
      }

      // Pausa breve entre tokens para simular ráfaga real < 1.5s total
      if (i < 3) await new Promise(r => setTimeout(r, 450));
    }
  } catch (err) {
    logSimMessage(`Error durante simulación: ${err.message}`, 'rejected');
  } finally {
    btn.disabled = false;
    btn.textContent = '⚡ Simular ataque / anomalía (b@b.com)';
    if (window.refreshDashboard) window.refreshDashboard();
    if (window.refreshSlidingWindow) window.refreshSlidingWindow();
    if (window.loadUsersHistory) window.loadUsersHistory('b@b.com');
  }
}

// ---------------------------------------------------------------------------
// 6. Simular Tráfico Normal
// ---------------------------------------------------------------------------
async function simulateNormalTraffic() {
  const btn = document.getElementById('btn-sim-normal');
  const banner = document.getElementById('banner-normal-alert');
  const anomalyBanner = document.getElementById('banner-anomaly-alert');
  if (banner) banner.style.display = 'none';
  if (anomalyBanner) anomalyBanner.style.display = 'none';

  btn.disabled = true;
  btn.textContent = 'Enviando tráfico espaciado...';
  resetTokenVisualizer();

  logSimMessage('Iniciando simulación de tráfico normal para c@c.com (> 4s entre envíos)', 'info');

  const user = 'c@c.com';
  const timestampBase = Date.now();

  try {
    for (let i = 1; i <= 2; i++) {
      const idTxn = `NORM-${timestampBase}-${i}`;
      const value = (120000 + i * 25000).toFixed(2);
      const res = await sendTransaction(idTxn, user, value, 'PSE');

      if (res.status === 201) {
        logSimMessage(
          `✅ Txn ${i}/2 [${idTxn}]: ${res.data.transaction.status} | TRÁFICO NORMAL (Fuera de ventana de ráfaga)`,
          'approved'
        );
      } else {
        logSimMessage(`Error en Txn ${i}: HTTP ${res.status}`, 'rejected');
      }

      if (i === 1) {
        logSimMessage('Esperando 4.2 segundos (supera ventana de 3s)...', 'info');
        await new Promise(r => setTimeout(r, 4200));
      }
    }

    if (banner) {
      banner.style.display = 'flex';
      banner.innerHTML = `
        <span>✅ TRÁFICO NORMAL</span>
        <span>Transacciones aprobadas sin ráfagas sospechosas</span>
      `;
    }
  } catch (err) {
    logSimMessage(`Error en simulación: ${err.message}`, 'rejected');
  } finally {
    btn.disabled = false;
    btn.textContent = '🟢 Simular tráfico normal (c@c.com)';
    if (window.refreshDashboard) window.refreshDashboard();
    if (window.refreshSlidingWindow) window.refreshSlidingWindow();
    if (window.loadUsersHistory) window.loadUsersHistory('c@c.com');
  }
}

// ---------------------------------------------------------------------------
// 7. Autotest de Hash
// ---------------------------------------------------------------------------
async function runHashAutotest() {
  const btn = document.getElementById('btn-run-autotest');
  btn.disabled = true;
  btn.textContent = 'Verificando vectores...';
  logSimMessage('Ejecutando autotest de integridad SHA-256 (WebCrypto vs tests/hash_vectors.json)...', 'info');
  try {
    const res = await fetch('/api/simulator/hash-vectors');
    if (!res.ok) throw new Error('No se pudieron cargar los vectores oficiales');
    const { vectors } = await res.json();
    let allPassed = true;
    for (let i = 0; i < vectors.length; i++) {
      const v = vectors[i];
      const inp = v.input;
      const { canonicalString, hash } = await computeHashJS(inp.idTxn, inp.user, inp.date, inp.value, inp.paymentMethod);
      const canonicalMatch = canonicalString === v.canonicalString;
      const hashMatch = hash === v.expectedHash;
      if (canonicalMatch && hashMatch) {
        logSimMessage(`✓ Vector ${i + 1} [${v.description}]: Coincidencia exacta SHA-256`, 'approved');
      } else {
        allPassed = false;
        logSimMessage(`✗ Vector ${i + 1} FALLÓ: Obtenido ${hash} != Esperado ${v.expectedHash}`, 'rejected');
      }
    }
    if (allPassed) {
      logSimMessage(`🎉 AUTOTEST COMPLETADO: 100% de los vectores (${vectors.length}/${vectors.length}) coinciden exactamente entre JS y Python.`, 'approved');
      alert(`Autotest exitoso: Todos los vectores (${vectors.length}) coinciden con SHA-256 WebCrypto.`);
    } else {
      logSimMessage('⚠️ Discrepancia detectada en los vectores de hash.', 'rejected');
    }
  } catch (err) {
    logSimMessage(`Error en autotest: ${err.message}`, 'rejected');
  } finally {
    btn.disabled = false;
    btn.textContent = '🧪 Ejecutar autotest de Hash (WebCrypto)';
  }
}

// ---------------------------------------------------------------------------
// 8. Restablecer datos
// ---------------------------------------------------------------------------
async function resetSimulation() {
  const btn = document.getElementById('btn-reset-sim');
  btn.disabled = true;
  btn.textContent = 'Restableciendo...';
  try {
    const res = await fetch('/api/simulator/reset', { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      logSimMessage('Base de datos y ventanas en memoria restablecidas con éxito.', 'approved');
      resetTokenVisualizer();
      const anomalyBanner = document.getElementById('banner-anomaly-alert');
      const normalBanner = document.getElementById('banner-normal-alert');
      if (anomalyBanner) anomalyBanner.style.display = 'none';
      if (normalBanner) normalBanner.style.display = 'none';
      if (window.refreshDashboard) window.refreshDashboard();
      if (window.refreshSlidingWindow) window.refreshSlidingWindow();
      if (window.loadUsersHistory) window.loadUsersHistory();
    } else {
      logSimMessage(`Error al restablecer: ${data.error?.message || 'Error'}`, 'rejected');
    }
  } catch (err) {
    logSimMessage(`Fallo de conexión al restablecer: ${err.message}`, 'rejected');
  } finally {
    btn.disabled = false;
    btn.textContent = '🧹 Restablecer datos de simulación';
  }
}

// Inicialización de eventos del simulador
document.addEventListener('DOMContentLoaded', () => {
  const btnAttack = document.getElementById('btn-sim-attack');
  if (btnAttack) btnAttack.addEventListener('click', simulateAttack);

  const btnNormal = document.getElementById('btn-sim-normal');
  if (btnNormal) btnNormal.addEventListener('click', simulateNormalTraffic);

  const btnAutotest = document.getElementById('btn-run-autotest');
  if (btnAutotest) btnAutotest.addEventListener('click', runHashAutotest);

  const btnReset = document.getElementById('btn-reset-sim');
  if (btnReset) btnReset.addEventListener('click', resetSimulation);

  // Estado inicial del visualizador
  resetTokenVisualizer();
});
