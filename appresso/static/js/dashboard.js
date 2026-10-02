/**
 * VELUM — Dashboard Analytics & Charts Controller
 * Gestiona el consumo de métricas, los 5 KPI y la renderización de 4 gráficos con Chart.js local.
 */

let currentPeriod = 'hoy';
let currentTheme = localStorage.getItem('velum_theme') || 'dark';

let chartTransactions = null;
let chartHourlyAnomalies = null;
let chartSeverity = null;
let chartPayment = null;

// Colores según tema
function getThemeColors() {
  const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
  return {
    text: isDark ? '#f0f4f8' : '#0f172a',
    muted: isDark ? '#64748b' : '#94a3b8',
    grid: isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)',
    cardBg: isDark ? '#182234' : '#ffffff',
  };
}

// 1. Verificación de Salud
async function checkSystemHealth() {
  const badge = document.getElementById('system-health-badge');
  const label = document.getElementById('system-health-text');
  try {
    const res = await fetch('/health');
    if (res.ok) {
      const data = await res.json();
      badge.className = 'status-badge';
      label.textContent = `Sistema operativo (${data.environment})`;
    } else {
      badge.className = 'status-badge offline';
      label.textContent = 'Degradado';
    }
  } catch (err) {
    badge.className = 'status-badge offline';
    label.textContent = 'Sin conexión';
  }
}

// 2. Formateo de números
function formatCOP(num) {
  const n = parseFloat(num) || 0;
  return '$ ' + n.toLocaleString('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// 3. Cargar estadísticas y actualizar KPIs + Gráficos
async function fetchDashboardStats(periodo = currentPeriod) {
  currentPeriod = periodo;
  try {
    const res = await fetch(`/api/dashboard/stats?periodo=${periodo}`);
    if (!res.ok) throw new Error('Error al obtener estadísticas');
    const data = await res.json();

    updateKPIs(data);
    renderCharts(data);
  } catch (err) {
    console.error('Error cargando estadísticas del dashboard:', err);
  }
}

function updateKPIs(data) {
  // 1. Total Transacciones
  document.getElementById('kpi-total-txns').textContent = data.by_status.total.toLocaleString();
  
  // Tendencia badge
  const trendEl = document.getElementById('kpi-trend-badge');
  if (data.tendencia !== null && data.tendencia !== undefined) {
    const isUp = data.tendencia >= 0;
    trendEl.className = `badge-trend ${isUp ? 'up' : 'down'}`;
    trendEl.textContent = `${isUp ? '+' : ''}${data.tendencia}% vs periodo anterior`;
  } else {
    trendEl.className = 'badge-trend';
    trendEl.textContent = 'Sin histórico previo';
  }

  // 2. Anomalías detectadas
  document.getElementById('kpi-total-anomalies').textContent = data.anomalias.total.toLocaleString();

  // 3. Tasa de anomalías
  document.getElementById('kpi-anomaly-rate').textContent = `${data.anomalias.porcentaje}%`;

  // 4. Monto en riesgo
  document.getElementById('kpi-risk-amount').textContent = formatCOP(data.anomalias.monto_sospechoso);

  // 5. Usuarios recurrentes
  document.getElementById('kpi-recurring-users').textContent = data.anomalias.recurrentes.toLocaleString();
}

function renderCharts(data) {
  const colors = getThemeColors();

  const hoursLabels = data.by_hour.map(h => `${String(h.hora).padStart(2, '0')}:00`);
  const txnsByHour = data.by_hour.map(h => h.transacciones);
  const anomaliesByHour = data.by_hour.map(h => h.anomalias);

  // Gráfico 1: Línea - Transacciones vs Anomalías por Hora
  const ctxTxns = document.getElementById('chart-transactions-hourly').getContext('2d');
  if (chartTransactions) chartTransactions.destroy();
  chartTransactions = new Chart(ctxTxns, {
    type: 'line',
    data: {
      labels: hoursLabels,
      datasets: [
        {
          label: 'Total Transacciones',
          data: txnsByHour,
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59, 130, 246, 0.15)',
          fill: true,
          tension: 0.35,
          pointRadius: 3,
        },
        {
          label: 'Anomalías (Posible Fraude)',
          data: anomaliesByHour,
          borderColor: '#ef4444',
          backgroundColor: 'rgba(239, 68, 68, 0.2)',
          fill: true,
          tension: 0.35,
          pointRadius: 4,
          pointBackgroundColor: '#ef4444',
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: colors.text, font: { size: 11 } } },
      },
      scales: {
        x: { grid: { color: colors.grid }, ticks: { color: colors.muted, font: { size: 10 } } },
        y: { grid: { color: colors.grid }, ticks: { color: colors.muted, precision: 0 } },
      }
    }
  });

  // Gráfico 2: Barras - Anomalías por hora con pico resaltado
  const ctxHourly = document.getElementById('chart-hourly-anomalies').getContext('2d');
  const barColors = anomaliesByHour.map((val, idx) => {
    return (data.pico_hora !== null && idx === data.pico_hora && val > 0)
      ? '#dc2626'
      : '#f59e0b';
  });

  if (chartHourlyAnomalies) chartHourlyAnomalies.destroy();
  chartHourlyAnomalies = new Chart(ctxHourly, {
    type: 'bar',
    data: {
      labels: hoursLabels,
      datasets: [{
        label: 'Anomalías detectadas',
        data: anomaliesByHour,
        backgroundColor: barColors,
        borderRadius: 4,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            afterLabel: (ctx) => (data.pico_hora !== null && ctx.dataIndex === data.pico_hora) ? '⚡ Hora Pico Detectada' : ''
          }
        }
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: colors.muted, font: { size: 10 } } },
        y: { grid: { color: colors.grid }, ticks: { color: colors.muted, precision: 0 } },
      }
    }
  });

  // Gráfico 3: Dona - Severidad
  const ctxSeverity = document.getElementById('chart-severity').getContext('2d');
  if (chartSeverity) chartSeverity.destroy();
  chartSeverity = new Chart(ctxSeverity, {
    type: 'doughnut',
    data: {
      labels: ['Bajo', 'Medio', 'Alto', 'Crítico'],
      datasets: [{
        data: [
          data.by_severity.bajo,
          data.by_severity.medio,
          data.by_severity.alto,
          data.by_severity.critico,
        ],
        backgroundColor: ['#10b981', '#f59e0b', '#f97316', '#dc2626'],
        borderWidth: 2,
        borderColor: colors.cardBg,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { color: colors.text, boxWidth: 12 } }
      },
      cutout: '70%',
    }
  });

  // Gráfico 4: Dona - Métodos de Pago
  const ctxPayment = document.getElementById('chart-payment-method').getContext('2d');
  if (chartPayment) chartPayment.destroy();
  chartPayment = new Chart(ctxPayment, {
    type: 'doughnut',
    data: {
      labels: ['Tarjeta', 'PSE', 'Transferencia', 'Otro'],
      datasets: [{
        data: [
          data.by_payment_method.tarjeta,
          data.by_payment_method.pse,
          data.by_payment_method.transferencia,
          data.by_payment_method.otro,
        ],
        backgroundColor: ['#3b82f6', '#06b6d4', '#8b5cf6', '#64748b'],
        borderWidth: 2,
        borderColor: colors.cardBg,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { color: colors.text, boxWidth: 12 } }
      },
      cutout: '70%',
    }
  });
}

// 4. Gestión de Tema y Periodo
function initTheme() {
  document.documentElement.setAttribute('data-theme', currentTheme);
  const themeBtn = document.getElementById('btn-toggle-theme');
  if (themeBtn) {
    themeBtn.textContent = currentTheme === 'light' ? '🌙' : '☀️';
    themeBtn.addEventListener('click', () => {
      currentTheme = currentTheme === 'light' ? 'dark' : 'light';
      document.documentElement.setAttribute('data-theme', currentTheme);
      localStorage.setItem('velum_theme', currentTheme);
      themeBtn.textContent = currentTheme === 'light' ? '🌙' : '☀️';
      if (chartTransactions) fetchDashboardStats(currentPeriod);
    });
  }
}

function initPeriodSelector() {
  const buttons = document.querySelectorAll('.period-btn');
  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      buttons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const p = btn.getAttribute('data-period');
      currentPeriod = p;
      fetchDashboardStats(p);
      loadUsersHistory();
    });
  });
}

// 5. Historial y Directorio de Usuarios
let cachedUsersDirectory = [];

async function loadUsersHistory(highlightEmail = null) {
  const tbody = document.getElementById('users-directory-tbody');
  if (!tbody) return;

  try {
    const res = await fetch(`/api/dashboard/users-directory?periodo=${currentPeriod}`);
    if (!res.ok) throw new Error('Error al cargar directorio de usuarios');
    const data = await res.json();
    cachedUsersDirectory = data.users || [];
    renderUsersTable(cachedUsersDirectory, highlightEmail);
  } catch (err) {
    console.error('Error cargando historial de usuarios:', err);
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color: var(--text-muted); padding: 18px;">Error al cargar directorio de usuarios</td></tr>`;
  }
}

function renderUsersTable(users, highlightEmail = null) {
  const tbody = document.getElementById('users-directory-tbody');
  const countEl = document.getElementById('users-directory-count');
  if (!tbody) return;

  if (countEl) {
    const pLabel = currentPeriod === 'hoy' ? 'HOY' : (currentPeriod === 'semana' ? 'ÚLTIMOS 7 DÍAS' : 'ÚLTIMOS 30 DÍAS');
    countEl.innerHTML = `<strong>${users.length}</strong> usuarios monitoreados · Métricas del periodo: <span style="color:#38bdf8; font-weight:700;">${pLabel}</span>`;
  }

  if (users.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color: var(--text-muted); padding: 20px;">No se encontraron usuarios en este periodo</td></tr>`;
    return;
  }

  tbody.innerHTML = users.map(u => {
    let riskBadgeClass = 'badge-risk-bajo';
    if (u.riesgo === 'CRITICO') riskBadgeClass = 'badge-risk-critico';
    else if (u.riesgo === 'ALTO') riskBadgeClass = 'badge-risk-alto';
    else if (u.riesgo === 'MEDIO') riskBadgeClass = 'badge-risk-medio';

    const statusBadgeClass = u.estado === 'ACTIVO' ? 'badge-trend up' : 'badge-trend down';
    const isHighlighted = (highlightEmail && u.email.toLowerCase() === highlightEmail.toLowerCase());
    const rowClass = isHighlighted ? 'row-updated-flash' : '';

    return `
      <tr class="${rowClass}">
        <td style="font-family: var(--font-mono); font-weight: 700; color: var(--text-muted);">#${u.id}</td>
        <td>
          <div style="font-weight: 700; display:flex; align-items:center; gap:6px;">
            ${u.email}
            ${isHighlighted ? '<span class="badge-risk badge-risk-critico" style="font-size:9px;">ACTUALIZADO</span>' : ''}
          </div>
          <div style="font-size: 11px; color: var(--text-secondary);">${u.nombre}</div>
        </td>
        <td><span class="${statusBadgeClass}">${u.estado}</span></td>
        <td><span class="badge-risk ${riskBadgeClass}">● ${u.riesgo}</span></td>
        <td>
          <div style="font-family: var(--font-mono); font-weight: 700;">${u.total_transacciones}</div>
          <div style="font-size: 10px; color: var(--text-muted);">${u.historico_total_txns} total</div>
        </td>
        <td style="font-family: var(--font-mono); font-weight: 700; color: ${u.total_anomalias > 0 ? 'var(--status-critical)' : 'var(--text-secondary)'};">
          ${u.total_anomalias}
        </td>
        <td style="font-family: var(--font-mono); font-weight: 700;">$ ${parseFloat(u.monto_total).toLocaleString('es-CO', { minimumFractionDigits: 2 })}</td>
        <td>
          <button class="btn-inspect-window" onclick="inspectUserWindow(${u.id}, '${u.email}')">
            🔍 Ver Ventana
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

function initUserSearch() {
  const searchInput = document.getElementById('user-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      const q = e.target.value.toLowerCase().trim();
      const filtered = cachedUsersDirectory.filter(u => 
        u.email.toLowerCase().includes(q) || 
        u.nombre.toLowerCase().includes(q) ||
        u.estado.toLowerCase().includes(q) ||
        u.riesgo.toLowerCase().includes(q)
      );
      renderUsersTable(filtered);
    });
  }
}

window.inspectUserWindow = (userId, email) => {
  const targetBtn = document.querySelector(`.user-quick-btn[data-email="${email}"]`);
  if (targetBtn) {
    targetBtn.click();
  } else if (window.loadTimeline) {
    window.loadTimeline(userId, email);
  }
  const vizSection = document.querySelector('.visualizer-card');
  if (vizSection) {
    vizSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
};

// Inicialización global
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initPeriodSelector();
  initUserSearch();
  checkSystemHealth();
  fetchDashboardStats('hoy');
  loadUsersHistory();

  // Actualizar salud cada 30 segundos
  setInterval(checkSystemHealth, 30000);
});

window.refreshDashboard = () => {
  fetchDashboardStats(currentPeriod);
  loadUsersHistory();
};
window.loadUsersHistory = loadUsersHistory;
