/* ============================================================
   COSTOS PRO — JS principal: tooltips, sidebar, helpers
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {
  _initSidebar();
  _initFlashAlerts();
  _initHelpModals();
  _initFormCalcs();
  _initConfirms();
});

/* ── Sidebar toggle ─────────────────────────────────────── */
function _initSidebar() {
  const btn = document.getElementById('sidebar-toggle');
  const sidebar = document.getElementById('main-sidebar');
  if (!btn || !sidebar) return;

  btn.addEventListener('click', () => {
    sidebar.classList.toggle('collapsed');
    localStorage.setItem('cp_sidebar', sidebar.classList.contains('collapsed') ? '1' : '0');
  });

  // Restaurar estado
  if (localStorage.getItem('cp_sidebar') === '1') {
    sidebar.classList.add('collapsed');
  }

  // Mobile overlay
  document.getElementById('sidebar-overlay')?.addEventListener('click', () => {
    sidebar.classList.remove('mobile-open');
  });
}

/* ── Flash alerts auto-dismiss ─────────────────────────── */
function _initFlashAlerts() {
  document.querySelectorAll('.alert[data-auto-dismiss]').forEach(alert => {
    const ms = parseInt(alert.dataset.autoDismiss || 4000);
    setTimeout(() => {
      alert.style.opacity = '0';
      alert.style.transition = 'opacity 0.4s';
      setTimeout(() => alert.remove(), 400);
    }, ms);
  });
  document.querySelectorAll('.alert-close').forEach(btn => {
    btn.addEventListener('click', () => btn.closest('.alert').remove());
  });
}

/* ── Help modals ────────────────────────────────────────── */
function _initHelpModals() {
  document.querySelectorAll('.help-btn[data-help]').forEach(btn => {
    btn.addEventListener('click', () => {
      const title = btn.dataset.helpTitle || 'Ayuda';
      const text  = btn.dataset.help;
      const voice = btn.dataset.helpVoice || text;
      showHelpModal(title, text, voice);
    });
  });
}

function showHelpModal(title, text, voiceText = null) {
  let modal = document.getElementById('help-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'help-modal';
    modal.className = 'modal-overlay';
    modal.innerHTML = `
      <div class="modal" style="max-width:440px">
        <div class="modal-header">
          <span class="modal-title" id="help-modal-title"></span>
          <button class="modal-close" onclick="closeHelpModal()">
            <i class="ti ti-x"></i>
          </button>
        </div>
        <div class="modal-body" id="help-modal-body"></div>
        <div class="modal-footer">
          <button class="btn btn-ghost btn-sm" onclick="closeHelpModal()">Cerrar</button>
          <button class="btn btn-secondary btn-sm" id="help-modal-voice"
                  onclick="readHelpAloud()" style="display:none">
            <i class="ti ti-volume"></i> Escuchar
          </button>
          <button class="btn btn-primary btn-sm"
                  onclick="CostosChatbox.sendQuick(document.getElementById(\'help-modal-title\').textContent)">
            <i class="ti ti-robot"></i> Preguntar a IA
          </button>
        </div>
      </div>`;
    document.body.appendChild(modal);
    modal.addEventListener('click', e => { if (e.target === modal) closeHelpModal(); });
  }
  document.getElementById('help-modal-title').textContent = title;
  document.getElementById('help-modal-body').innerHTML = `<p style="font-size:14px;line-height:1.7;color:var(--text-primary)">${text}</p>`;
  modal._voiceText = voiceText;
  const vBtn = document.getElementById('help-modal-voice');
  if (vBtn) vBtn.style.display = window.CostosProVoice ? 'inline-flex' : 'none';
  modal.classList.add('open');
  if (window.CostosProVoice?.isEnabled() && voiceText) {
    setTimeout(() => window.CostosProVoice.speak(voiceText, true), 300);
  }
}

function closeHelpModal() {
  document.getElementById('help-modal')?.classList.remove('open');
  window.CostosProVoice?.stop();
}

function readHelpAloud() {
  const modal = document.getElementById('help-modal');
  if (modal?._voiceText && window.CostosProVoice) {
    window.CostosProVoice.speak(modal._voiceText, true);
  }
}

/* ── Cálculo en tiempo real para formulario Personal ─────── */
function _initFormCalcs() {
  const calcFields = ['basic_salary', 'bonus', 'family_allowance', 'other_benefits', 'available_hours_month'];
  calcFields.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', debounce(_calcPersonalCost, 500));
  });
  const sctrCb = document.getElementById('has_sctr');
  if (sctrCb) sctrCb.addEventListener('change', _calcPersonalCost);
  const payrollCb = document.getElementById('in_payroll');
  if (payrollCb) payrollCb.addEventListener('change', _calcPersonalCost);
}

async function _calcPersonalCost() {
  const inPayroll = document.getElementById('in_payroll');
  const fields = {
    basic_salary:        parseFloat(document.getElementById('basic_salary')?.value || 0),
    bonus:               parseFloat(document.getElementById('bonus')?.value || 0),
    family_allowance:    parseFloat(document.getElementById('family_allowance')?.value || 0),
    other_benefits:      parseFloat(document.getElementById('other_benefits')?.value || 0),
    available_hours:     parseFloat(document.getElementById('available_hours_month')?.value || 192),
    has_sctr:            document.getElementById('has_sctr')?.checked || false,
    in_payroll:          inPayroll ? inPayroll.checked : true,
  };
  try {
    const res = await fetch('/personal/api/calculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(fields)
    });
    const data = await res.json();
    if (data.success) _updateCostPreview(data.costs);
  } catch (_) {}
}

function _updateCostPreview(costs) {
  const map = {
    'prev-grat':  costs.gratification_monthly,
    'prev-cts':   costs.cts_monthly,
    'prev-ess':   costs.essalud,
    'prev-sctr':  costs.sctr,
    'prev-total': costs.total_monthly_cost,
    'prev-hora':  costs.cost_per_hour,
  };
  Object.entries(map).forEach(([id, val]) => {
    const el = document.getElementById(id);
    if (el) el.textContent = formatCurrency(val);
  });
}

/* ── Confirmaciones ─────────────────────────────────────── */
function _initConfirms() {
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', e => {
      const msg = el.dataset.confirm || '¿Estás seguro?';
      if (!confirm(msg)) e.preventDefault();
    });
  });
}

/* ── Helpers globales ───────────────────────────────────── */
function formatCurrency(val) {
  return 'S/ ' + parseFloat(val || 0).toLocaleString('es-PE', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

function formatPct(val) {
  return parseFloat(val || 0).toFixed(1) + '%';
}

function debounce(fn, delay) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), delay);
  };
}

function showToast(msg, type = 'success') {
  const toast = document.createElement('div');
  const icons = { success: 'ti-check', error: 'ti-alert-circle', warning: 'ti-alert-triangle', info: 'ti-info-circle' };
  toast.className = `alert alert-${type}`;
  toast.style.cssText = 'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);z-index:9998;min-width:280px;max-width:400px;animation:fadeIn 0.3s ease';
  toast.innerHTML = `<i class="ti ${icons[type] || icons.info}"></i><span>${msg}</span>`;
  document.body.appendChild(toast);
  setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = 'opacity 0.3s'; }, 3000);
  setTimeout(() => toast.remove(), 3400);
}

function togglePassword(inputId, btn) {
  const input = document.getElementById(inputId);
  if (!input) return;
  const isText = input.type === 'text';
  input.type = isText ? 'password' : 'text';
  btn.querySelector('i').className = isText ? 'ti ti-eye' : 'ti ti-eye-off';
}

// Exportar como globales
window.showHelpModal = showHelpModal;
window.closeHelpModal = closeHelpModal;
window.readHelpAloud = readHelpAloud;
window.showToast = showToast;
window.togglePassword = togglePassword;
window.formatCurrency = formatCurrency;

/* ── "Otro" en selects ──────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  // Activar en todos los selects que tengan opción "otro" o "Otro"
  document.querySelectorAll('select').forEach(sel => {
    sel.addEventListener('change', _handleOtroSelect);
    // Verificar estado inicial
    _handleOtroSelect.call(sel);
  });
});

function _handleOtroSelect() {
  const sel = this;
  const val = sel.value.toLowerCase();
  const inputId = sel.name + '_otro_input';

  // Buscar o crear input "otro"
  let input = document.getElementById(inputId);

  if (val === 'otro' || val === 'other') {
    if (!input) {
      input = document.createElement('input');
      input.type = 'text';
      input.id = inputId;
      input.name = sel.name; // mismo name → al enviar el form usa este valor
      input.className = 'form-control mt-1';
      input.placeholder = 'Especifica...';
      input.style.marginTop = '6px';
      // Insertar después del select
      sel.parentNode.insertBefore(input, sel.nextSibling);
      // Cambiar el name del select para que no pise
      sel.dataset.originalName = sel.name;
      sel.removeAttribute('name');
      input.focus();
    } else {
      input.style.display = 'block';
      sel.dataset.originalName = sel.name;
      sel.removeAttribute('name');
    }
  } else {
    if (input) {
      input.style.display = 'none';
      // Restaurar name del select
      if (sel.dataset.originalName) {
        sel.name = sel.dataset.originalName;
        input.removeAttribute('name');
      }
    }
  }
}
