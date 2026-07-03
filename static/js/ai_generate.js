/* ============================================================
   COSTOS PRO — Generador IA para módulos
   Uso: AIGenerator.show('resources')
   ============================================================ */

const AIGenerator = (() => {

  const ENTITY_CONFIG = {
    resources: {
      title:       'Generar Recursos con IA',
      placeholder: 'Ej: Empresa textil con 10 máquinas de coser, 3 pisos, consume aprox 2000 Kw-h/mes...',
      icon:        'ti-database', color: '#F97316',
      cols: ['Código','Nombre','Categoría','S/./mes','Inductor'],
      row:  i => [i.code, i.name, i.category, `S/ ${(+i.monthly_amount).toFixed(2)}`, i.driver_type||'—'],
    },
    activity_centers: {
      title: 'Generar Centros de Actividad con IA',
      placeholder: 'Ej: Empresa de confecciones con áreas de corte, costura, acabado y administración...',
      icon: 'ti-layout-grid', color: '#3B82F6',
      cols: ['Código','Nombre','Tipo'],
      row:  i => [i.code, i.name, i.center_type],
    },
    activities: {
      title: 'Generar Actividades con IA',
      placeholder: 'Ej: Proceso productivo con corte de tela, costura a máquina, revisión de calidad y empaque...',
      icon: 'ti-activity', color: '#22C55E',
      cols: ['Código','Nombre','Inductor','Total inductor'],
      row:  i => [i.code, i.name, i.driver_type||'—', i.driver_total||0],
    },
    cost_objects: {
      title: 'Generar Objetos de Costo con IA',
      placeholder: 'Ej: Producimos camisas, pantalones y casacas en tallas S, M, L...',
      icon: 'ti-target', color: '#8B5CF6',
      cols: ['Código','Nombre','Qty/mes'],
      row:  i => [i.code, i.name, i.quantity_month||0],
    },
    kardex: {
      title: 'Generar Inventario con IA',
      placeholder: 'Ej: Empresa textil que usa tela, hilo, botones, etiquetas y empaques...',
      icon: 'ti-box', color: '#14B8A6',
      cols: ['Código','Nombre','Categoría','Stock inicial','Costo unit.'],
      row:  i => [i.code, i.name, i.category, i.initial_stock, `S/ ${(+i.initial_cost).toFixed(2)}`],
    },
    quality: {
      title: 'Generar Costos de Calidad PAF con IA',
      placeholder: 'Ej: Empresa manufacturera con procesos de inspección, capacitaciones y reclamos...',
      icon: 'ti-shield-check', color: '#DC2626',
      cols: ['Nombre','Categoría','S/./mes','Responsable'],
      row:  i => [i.activity_name, i.category, `S/ ${(+i.monthly_cost).toFixed(2)}`, i.responsible||'—'],
    },
    employees: {
      title: 'Generar Personal con IA',
      placeholder: 'Ej: Empresa textil con operarios de corte, costura, acabado, personal administrativo y supervisor...',
      icon: 'ti-users', color: '#F97316',
      cols: ['Código','Nombre','Tipo','Sueldo básico','Horas/mes'],
      row:  i => [i.code, i.full_name, i.labor_type, `S/ ${(+i.basic_salary).toFixed(2)}`, i.available_hours_month||192],
    },
    products: {
      title: 'Generar Productos/Servicios con IA',
      placeholder: 'Ej: Empresa de confecciones que produce camisas, pantalones y casacas en tallas S, M, L, XL...',
      icon: 'ti-package', color: '#3B82F6',
      cols: ['Código','Nombre','Categoría','Precio venta','Costo estándar'],
      row:  i => [i.code, i.name, i.category, `S/ ${(+i.sale_price).toFixed(2)}`, `S/ ${(+i.standard_cost).toFixed(2)}`],
    },
    abc_full: {
      title: 'Generar Análisis ABC con IA',
      placeholder: 'Ej: Empresa de confecciones con recursos de energía, personal y depreciación. Productos: camisas y pantalones...',
      icon: 'ti-calculator', color: '#8B5CF6',
      cols: ['Actividad / Paso','Recomendación'],
      row:  i => [i.actividad || i.paso || '', i.razon || i.inductor || ''],
      isGuide: true,
    },
    process_dept: {
      title: 'Generar Departamentos de Proceso con IA',
      placeholder: 'Ej: Fábrica textil con proceso de tejido, tintado y acabado. Producción mensual de 1000 prendas...',
      icon: 'ti-git-branch', color: '#F97316',
      cols: ['Departamento','UPROD','UTT','UIFPP','Costo Mat.','Costo Conv.'],
      row:  i => [i.name, i.uprod||0, i.utt||0, i.uifpp||0,
                  `S/ ${(+(i.cost_mat_current||0)).toFixed(0)}`,
                  `S/ ${((+(i.cost_mod_current||0))+(+(i.cost_cif_current||0))).toFixed(0)}`],
    },
    budget_base: {
      title: 'Generar Presupuesto Base con IA',
      placeholder: 'Ej: Empresa textil, ventas esperadas 500 camisas/mes a S/ 85, 10 operarios MOD...',
      icon: 'ti-coin', color: '#22C55E',
      cols: ['Concepto','Tipo','Mes','Cantidad','Monto S/'],
      row:  i => [i.product_name || i.position_name || i.concept || '',
                  i.labor_type || i.cif_type || 'venta', i.month||1,
                  i.quantity || i.hours_required || '',
                  `S/ ${(+(i.unit_price||0)*(+(i.quantity||1)) || +(i.amount||0) || (+(i.hours_required||0))*(+(i.cost_per_hour||0))).toFixed(2)}`],
    },
    cost_structure: {
      title: 'Generar Estructura de Costos con IA',
      placeholder: 'Ej: Camisa algodón talla M, usa 1.5m de tela a S/ 9/m, 30 min costura, producción 500 uds/mes...',
      icon: 'ti-chart-treemap', color: '#14B8A6',
      cols: ['Categoría','Descripción','Unidad','Cantidad','Costo Unit.','Total'],
      row:  i => [i.cat||'', i.description||'', i.unit||'', i.quantity||0,
                  `S/ ${(+(i.unit_cost||0)).toFixed(2)}`,
                  `S/ ${((+(i.quantity||0))*(+(i.unit_cost||0))).toFixed(2)}`],
      isStructure: true,
    },
  };

  let currentEntity   = null;
  let currentItems    = [];
  let currentRaw      = null;
  let currentCallback = null;

  function show(entity, callback) {
    currentEntity   = entity;
    currentCallback = callback || null;
    currentItems    = [];
    currentRaw      = null;

    const cfg = ENTITY_CONFIG[entity];
    if (!cfg) { console.error('AIGenerator: entidad no soportada:', entity); return; }
    _renderModal(cfg);
  }

  function _renderModal(cfg) {
    document.getElementById('ai-gen-modal')?.remove();

    const modal = document.createElement('div');
    modal.id = 'ai-gen-modal';
    modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:9990;display:flex;align-items:center;justify-content:center;padding:20px';

    const headerCols = cfg.cols.map(col =>
      `<th style="padding:8px 10px;text-align:left;color:#fff;font-weight:600;font-size:11px">${col}</th>`
    ).join('') + '<th style="padding:8px 10px;color:#fff;font-size:11px">Notas</th>';

    modal.innerHTML = `
      <div style="max-width:680px;width:100%;max-height:85vh;overflow-y:auto;border-radius:16px;background:var(--bg-card,#fff);box-shadow:0 20px 60px rgba(0,0,0,0.25)">
        <div style="padding:20px 24px;border-bottom:1px solid var(--border,#e5e7eb);display:flex;align-items:center;justify-content:space-between">
          <div style="display:flex;align-items:center;gap:12px">
            <div style="width:40px;height:40px;background:${cfg.color}22;border-radius:10px;display:flex;align-items:center;justify-content:center;flex-shrink:0">
              <i class="ti ${cfg.icon}" style="font-size:20px;color:${cfg.color}"></i>
            </div>
            <div>
              <div style="font-size:16px;font-weight:700">${cfg.title}</div>
              <div style="font-size:12px;color:var(--text-secondary,#6b7280)">La IA generará registros con códigos y datos referenciales</div>
            </div>
          </div>
          <button onclick="document.getElementById('ai-gen-modal').remove()" style="background:none;border:none;cursor:pointer;font-size:24px;color:#9ca3af;line-height:1;padding:4px">×</button>
        </div>

        <div style="padding:20px 24px">
          <label for="ai-gen-context" style="display:block;font-size:13px;font-weight:600;margin-bottom:8px">
            Describe tu negocio / contexto <span style="color:#dc2626">*</span>
          </label>
          <textarea id="ai-gen-context"
            style="width:100%;min-height:88px;padding:10px 12px;border:1px solid var(--border,#d1d5db);border-radius:8px;font-size:13px;resize:vertical;box-sizing:border-box;font-family:inherit"
            placeholder="${cfg.placeholder}"></textarea>

          <div style="margin-top:12px">
            <button id="ai-gen-btn" onclick="AIGenerator._generate()"
              style="background:#f97316;color:#fff;border:none;padding:10px 20px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600;display:inline-flex;align-items:center;gap:8px">
              <i class="ti ti-robot"></i> Generar con IA
            </button>
          </div>

          <div id="ai-gen-progress" style="display:none;margin-top:14px">
            <div style="display:flex;justify-content:space-between;font-size:12px;color:#6b7280;margin-bottom:5px">
              <span id="ai-gen-progress-label">Conectando...</span>
              <span id="ai-gen-progress-pct">0%</span>
            </div>
            <div style="height:6px;background:#e5e7eb;border-radius:3px;overflow:hidden">
              <div id="ai-gen-progress-bar" style="height:100%;background:#f97316;border-radius:3px;width:0%;transition:width 0.4s ease"></div>
            </div>
          </div>

          <div id="ai-gen-status" style="font-size:12px;margin-top:8px"></div>
        </div>

        <div id="ai-gen-results" style="display:none;padding:0 24px 24px">
          <div style="font-size:13px;font-weight:600;margin-bottom:10px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">
            <span id="ai-gen-count"></span>
            <div style="display:flex;gap:8px">
              <button onclick="AIGenerator._regenerate()" style="background:#f3f4f6;border:1px solid #d1d5db;padding:6px 12px;border-radius:6px;cursor:pointer;font-size:12px">
                <i class="ti ti-refresh"></i> Regenerar
              </button>
              <button id="ai-gen-insert-btn" onclick="AIGenerator._insert()" style="background:#22c55e;color:#fff;border:none;padding:6px 16px;border-radius:6px;cursor:pointer;font-size:12px;font-weight:600">
                <i class="ti ti-database-import"></i> Insertar a la BD
              </button>
            </div>
          </div>
          <div style="overflow-x:auto;border-radius:8px;border:1px solid #e5e7eb">
            <table id="ai-gen-table" style="width:100%;border-collapse:collapse;font-size:12.5px">
              <thead><tr style="background:#1f2937">${headerCols}</tr></thead>
              <tbody id="ai-gen-tbody"></tbody>
            </table>
          </div>
          <div id="ai-gen-insert-status" style="margin-top:10px;font-size:12px"></div>
        </div>
      </div>
    `;

    document.body.appendChild(modal);
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
    setTimeout(() => document.getElementById('ai-gen-context')?.focus(), 150);
  }

  function _setProgress(pct, label) {
    const panel = document.getElementById('ai-gen-progress');
    const bar   = document.getElementById('ai-gen-progress-bar');
    const pctEl = document.getElementById('ai-gen-progress-pct');
    const lblEl = document.getElementById('ai-gen-progress-label');
    if (!panel) return;
    panel.style.display = 'block';
    if (bar)   bar.style.width   = pct + '%';
    if (pctEl) pctEl.textContent = pct + '%';
    if (lblEl && label) lblEl.textContent = label;
  }

  async function _generate() {
    const context = document.getElementById('ai-gen-context')?.value.trim();
    if (!context) {
      alert('Describe tu negocio o contexto primero.');
      return;
    }

    const btn    = document.getElementById('ai-gen-btn');
    const status = document.getElementById('ai-gen-status');
    if (!btn) return;

    btn.disabled = true;
    btn.innerHTML = '<i class="ti ti-loader" style="animation:spin 1s linear infinite"></i> Generando...';
    if (status) status.innerHTML = '';

    _setProgress(10, 'Conectando con la IA...');

    const steps = [
      [25, 'Analizando el contexto de tu empresa...'],
      [45, 'Generando registros con códigos y montos...'],
      [65, 'Aplicando estándares del sector...'],
      [80, 'Revisando coherencia de los datos...'],
    ];
    let si = 0;
    const ticker = setInterval(() => {
      if (si < steps.length) { _setProgress(steps[si][0], steps[si][1]); si++; }
    }, 900);

    try {
      const res  = await fetch(`/ai/generate/${currentEntity}`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ context, insert: false }),
      });
      const data = await res.json();
      clearInterval(ticker);

      if (data.success) {
        _setProgress(100, '¡Listo!');
        setTimeout(() => {
          const p = document.getElementById('ai-gen-progress');
          if (p) p.style.display = 'none';
        }, 1500);
        // abc_full, budget_base, cost_structure devuelven objeto, no array
        const isObj = data.items && !Array.isArray(data.items) && typeof data.items === 'object';
        currentRaw   = isObj ? data.items : null;
        currentItems = isObj ? [data.items] : (data.items || []);
        _showResults(data.items || []);
        const cnt = isObj ? 'Análisis generado' : `✓ ${data.count || currentItems.length} registros generados`;
        if (status) status.innerHTML = `<span style="color:#22c55e">${cnt}</span>`;
      } else {
        const p = document.getElementById('ai-gen-progress');
        if (p) p.style.display = 'none';
        if (status) status.innerHTML = `<span style="color:#dc2626">Error: ${data.error || 'Sin resultados. Agrega más contexto e intenta de nuevo.'}</span>`;
      }
    } catch (e) {
      clearInterval(ticker);
      const p = document.getElementById('ai-gen-progress');
      if (p) p.style.display = 'none';
      if (status) status.innerHTML = `<span style="color:#dc2626">Error de conexión con el servidor</span>`;
      console.error('AIGenerator error:', e);
    }

    btn.disabled = false;
    btn.innerHTML = '<i class="ti ti-robot"></i> Generar con IA';
  }

  function _showResults(items) {
    const cfg    = ENTITY_CONFIG[currentEntity];
    const tbody  = document.getElementById('ai-gen-tbody');
    const count  = document.getElementById('ai-gen-count');
    const resDiv = document.getElementById('ai-gen-results');
    if (!tbody || !resDiv) return;

    // ABC: mostrar como guía
    if (currentEntity === 'abc_full' && items && !Array.isArray(items)) {
      resDiv.style.display = 'block';
      if (count) count.textContent = 'Análisis generado';
      tbody.innerHTML = `<tr><td colspan="10" style="padding:16px;font-size:13px;line-height:1.8">
        <strong>Resumen:</strong> ${items.resumen||''}<br><br>
        <strong>Flujo de distribución:</strong> ${items.flujo||''}<br><br>
        <strong>Pasos recomendados:</strong><br>
        ${(items.pasos||[]).map((p,i)=>`${i+1}. ${p}`).join('<br>')}
        ${(items.inductores_recomendados||[]).length
          ? '<br><br><strong>Inductores sugeridos:</strong><br>' +
            (items.inductores_recomendados||[]).map(r=>`• ${r.actividad}: ${r.inductor} — ${r.razon}`).join('<br>')
          : ''}
      </td></tr>`;
      const insertBtn = document.getElementById('ai-gen-insert-btn');
      if (insertBtn) insertBtn.style.display = 'none';
      return;
    }

    // Budget: aplanar
    let flatItems = items;
    if (currentEntity === 'budget_base' && items && !Array.isArray(items)) {
      flatItems = [
        ...(items.ventas||[]).map(i => ({...i, _t:'Venta'})),
        ...(items.labor||[]).map(i => ({...i, _t:'MOD'})),
        ...(items.cif||[]).map(i => ({...i, _t:'CIF'})),
      ];
    } else if (currentEntity === 'cost_structure' && items && !Array.isArray(items)) {
      flatItems = [];
      (items.categories||[]).forEach(cat => {
        (cat.items||[]).forEach(item => flatItems.push({...item, cat: cat.name}));
      });
    }

    // En objetos compuestos (presupuesto y estructura), se muestra una vista plana,
    // pero se conserva el JSON original para insertarlo completo en la BD.
    if ((currentEntity === 'budget_base' || currentEntity === 'cost_structure') && items && !Array.isArray(items)) {
      currentRaw = items;
      currentItems = [items];
    } else {
      currentItems = flatItems;
    }
    if (count) count.textContent = `${flatItems.length} registros listos para insertar`;
    tbody.innerHTML = '';

    flatItems.forEach((item, idx) => {
      const tr = document.createElement('tr');
      tr.style.background = idx % 2 === 0 ? '#f9fafb' : '#ffffff';
      const cells = cfg.row(item);
      cells.forEach(cell => {
        const td = document.createElement('td');
        td.style.cssText = 'padding:6px 10px;border-bottom:1px solid #f3f4f6';
        td.textContent = String(cell);
        tr.appendChild(td);
      });
      const tdN = document.createElement('td');
      tdN.style.cssText = 'padding:6px 10px;border-bottom:1px solid #f3f4f6;color:#9ca3af;font-size:11px';
      tdN.textContent = item.notes || item.description || '—';
      tr.appendChild(tdN);
      tbody.appendChild(tr);
    });

    resDiv.style.display = 'block';
  }

  function _regenerate() {
    const r = document.getElementById('ai-gen-results');
    if (r) r.style.display = 'none';
    _generate();
  }

  async function _insert() {
    if (!currentItems.length) return;

    const context = document.getElementById('ai-gen-context')?.value.trim() || '';
    const btn     = document.getElementById('ai-gen-insert-btn');
    const status  = document.getElementById('ai-gen-insert-status');

    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="ti ti-loader" style="animation:spin 1s linear infinite"></i> Insertando...'; }
    _setProgress(40, 'Insertando en la base de datos...');

    try {
      const res  = await fetch(`/ai/generate/${currentEntity}`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ context, insert: true, items: currentItems }),
      });
      const data = await res.json();

      if (data.success) {
        _setProgress(100, '¡Insertado!');
        setTimeout(() => { const p=document.getElementById('ai-gen-progress'); if(p) p.style.display='none'; }, 1000);
        if (status) status.innerHTML = `<span style="color:#22c55e;font-weight:600">✓ ${data.inserted} registros insertados correctamente</span>`;
        if (window.showToast) showToast(`${data.inserted} registros insertados`, 'success');
        setTimeout(() => {
          document.getElementById('ai-gen-modal')?.remove();
          if (currentCallback) currentCallback(data);
          else if (data.redirect) window.location.href = data.redirect;
          else location.reload();
        }, 1500);
      } else {
        const p = document.getElementById('ai-gen-progress'); if(p) p.style.display='none';
        if (status) status.innerHTML = `<span style="color:#dc2626">Error: ${data.error}</span>`;
        if (btn) { btn.disabled = false; btn.innerHTML = '<i class="ti ti-database-import"></i> Insertar a la BD'; }
      }
    } catch (e) {
      const p = document.getElementById('ai-gen-progress'); if(p) p.style.display='none';
      if (status) status.innerHTML = `<span style="color:#dc2626">Error de conexión</span>`;
      if (btn) { btn.disabled = false; btn.innerHTML = '<i class="ti ti-database-import"></i> Insertar a la BD'; }
    }
  }

  return { show, _generate, _regenerate, _insert };
})();

window.AIGenerator = AIGenerator;
