/**
 * VELUM — Sliding Window Visualizer
 * Renderiza la línea de tiempo interactiva de la ventana deslizante [t - 3s, t],
 * destacando los límites temporales, transacciones en ventana, y marcas de detección de fraude.
 */

let activeUserEmail = 'b@b.com';
let activeUserId = null;

async function resolveUserId(email) {
  try {
    const res = await fetch('/api/simulator/users');
    if (res.ok) {
      const data = await res.json();
      const found = data.users.find(u => u.email.toLowerCase() === email.toLowerCase());
      if (found) return found.id;
    }
  } catch (err) {
    console.error('Error resolviendo usuario:', err);
  }
  return null;
}

async function loadUserTimeline(email = activeUserEmail) {
  activeUserEmail = email;
  const trackEl = document.getElementById('timeline-track');
  const userDisplayEl = document.getElementById('active-user-display');
  if (userDisplayEl) userDisplayEl.textContent = email;

  // Actualizar botones de selección rápida
  document.querySelectorAll('.user-quick-btn').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-email') === email);
  });

  const userId = await resolveUserId(email);
  if (!userId) {
    trackEl.innerHTML = `
      <div style="margin: auto; color: var(--text-muted); font-size: 13px; text-align: center; padding: 20px;">
        Sin transacciones registradas para <strong>${email}</strong>.<br>
        Usa el simulador inferior para generar tráfico o un ataque.
      </div>
    `;
    return;
  }

  activeUserId = userId;

  try {
    const res = await fetch(`/api/dashboard/timeline-sliding-window/${userId}`);
    if (!res.ok) {
      if (res.status === 404) {
        trackEl.innerHTML = `<div style="margin: auto; color: var(--text-muted);">Sin historial para este usuario.</div>`;
        return;
      }
      throw new Error('Error al cargar timeline');
    }

    const data = await res.json();
    renderTimelineNodes(data.entries, trackEl);
  } catch (err) {
    console.error('Error cargando timeline de ventana deslizante:', err);
    trackEl.innerHTML = `<div style="margin: auto; color: var(--status-rejected);">Error al obtener datos de la ventana deslizante.</div>`;
  }
}

function renderTimelineNodes(entries, container) {
  if (!entries || entries.length === 0) {
    container.innerHTML = `
      <div style="margin: auto; color: var(--text-muted); font-size: 13px; text-align: center; padding: 20px;">
        Sin transacciones para este usuario.
      </div>
    `;
    return;
  }

  // Tomamos las últimas 8 transacciones para mantener alta legibilidad académica
  const visibleEntries = entries.slice(-8);

  const tFirst = new Date(visibleEntries[0].timestamp).getTime();
  const tLast = new Date(visibleEntries[visibleEntries.length - 1].timestamp).getTime();
  let timeSpan = tLast - tFirst;
  if (timeSpan <= 0) timeSpan = 3000; // mínimo 3s span

  let html = `<div class="timeline-axis"></div>`;

  // Encontrar el último grupo de transacciones en ventana (para sombrear la ventana deslizante activa)
  const lastEntry = visibleEntries[visibleEntries.length - 1];
  const lastTime = new Date(lastEntry.timestamp).getTime();
  const windowStartTime = lastTime - 3000; // ventana de 3s

  // Calcular posición del sombreado de ventana [t - 3s, t]
  const pctStart = Math.max(0, Math.min(95, ((windowStartTime - tFirst) / timeSpan) * 80 + 10));
  const pctEnd = Math.max(5, Math.min(95, ((lastTime - tFirst) / timeSpan) * 80 + 10));
  const widthPct = Math.max(10, pctEnd - pctStart);

  html += `
    <div class="timeline-window-shade" style="left: ${pctStart}%; width: ${widthPct}%;">
      <span class="timeline-window-tag">VENTANA ACTIVA [t - 3s, t]</span>
    </div>
  `;

  // Renderizar cada nodo transaccional
  visibleEntries.forEach((entry, idx) => {
    const tCurrent = new Date(entry.timestamp).getTime();
    const posPct = ((tCurrent - tFirst) / timeSpan) * 80 + 10;
    const isSuspicious = entry.estado === 'SOSPECHOSA';
    const timeFormatted = entry.timestamp.split('T')[1].substring(0, 12);

    html += `
      <div class="timeline-node" style="left: ${posPct}%;">
        <div class="node-popup">
          <strong>${entry.idTxn}</strong>: $${entry.valor}<br>
          Estado: <strong>${entry.estado}</strong><br>
          Conteo ventana: <strong>${entry.conteoVentana}</strong>
          ${entry.severidad ? `<br>Severidad: <strong>${entry.severidad}</strong>` : ''}
          ${entry.reglaDetectada ? `<br><small>${entry.reglaDetectada}</small>` : ''}
        </div>
        <div class="node-dot ${isSuspicious ? 'suspicious' : ''}"></div>
        <div class="node-label">
          ${timeFormatted}<br>
          <span style="color: ${isSuspicious ? 'var(--status-critical)' : 'var(--text-muted)'}; font-weight: ${isSuspicious ? '700' : '400'}">
            ${entry.idTxn}
          </span>
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
}

// Inicialización de controles del timeline
function initSlidingWindowControls() {
  document.querySelectorAll('.user-quick-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const email = btn.getAttribute('data-email');
      loadUserTimeline(email);
    });
  });
}

document.addEventListener('DOMContentLoaded', () => {
  initSlidingWindowControls();
  // Cargar visualizador tras breve espera para dar tiempo a la inicialización del dashboard
  setTimeout(() => loadUserTimeline('b@b.com'), 400);
});

window.refreshSlidingWindow = () => loadUserTimeline(activeUserEmail);
