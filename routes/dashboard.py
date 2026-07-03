from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, flash
from functools import wraps
from models.database import query_db

dashboard_bp = Blueprint('dashboard', __name__)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def company_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'company_id' not in session:
            return redirect(url_for('companies.select'))
        return f(*args, **kwargs)
    return decorated


def module_required(module_key, write=False):
    """
    Valida acceso de usuarios invitados a un módulo del sistema.

    - El dueño de la empresa (sin user_role de invitado) siempre tiene acceso total.
    - role='admin'  -> acceso total a todo.
    - role='editor' -> puede ver y escribir en todos los módulos (no elimina cuentas/usuarios).
    - role='viewer' -> solo lectura en todos los módulos: cualquier acción de
                       escritura (write=True) se bloquea.
    - role='custom' -> el acceso se define por módulo en session['guest_modules'],
                       formato CSV "modulo:nivel,modulo:nivel" donde nivel es
                       'read' o 'write'. 'all' = acceso total tipo admin.
                       Si el módulo no aparece en la lista, no tiene acceso.

    write=True debe usarse en rutas que crean, editan o eliminan datos (POST de alta,
    edición, eliminación). write=False es para rutas de solo visualización.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            role = session.get('user_role')

            # Dueño de la empresa (no es invitado) -> acceso total
            if not role or role not in ('admin', 'editor', 'viewer', 'custom'):
                return f(*args, **kwargs)

            if role == 'admin':
                return f(*args, **kwargs)

            if role == 'editor':
                return f(*args, **kwargs)

            if role == 'viewer':
                if write:
                    flash('Usuario no tiene permiso para acceder a esta sección, consulte con su administrador.', 'error')
                    return redirect(url_for('dashboard.dashboard'))
                return f(*args, **kwargs)

            # role == 'custom'
            modules_csv = session.get('guest_modules', '')
            if modules_csv == 'all':
                return f(*args, **kwargs)

            level_by_module = {}
            for entry in modules_csv.split(','):
                entry = entry.strip()
                if not entry:
                    continue
                if ':' in entry:
                    mod, lvl = entry.split(':', 1)
                else:
                    mod, lvl = entry, 'read'
                level_by_module[mod] = lvl

            level = level_by_module.get(module_key)
            if level is None:
                flash('Usuario no tiene permiso para acceder a esta sección, consulte con su administrador.', 'error')
                return redirect(url_for('dashboard.dashboard'))

            if write and level != 'write':
                flash('Usuario no tiene permiso para acceder a esta sección, consulte con su administrador.', 'error')
                return redirect(url_for('dashboard.dashboard'))

            return f(*args, **kwargs)
        return decorated
    return decorator


@dashboard_bp.route('/')
@login_required
def index():
    if 'company_id' not in session:
        return redirect(url_for('companies.select'))
    return redirect(url_for('dashboard.dashboard'))


@dashboard_bp.route('/dashboard')
@login_required
@company_required
def dashboard():
    session['active_module'] = 'dashboard'
    company_id = session['company_id']
    period_id = session.get('period_id')

    kpis = _get_kpis(company_id, period_id)
    charts = _get_chart_data(company_id, period_id)

    return render_template('dashboard/index.html',
                           kpis=kpis, charts=charts)


def _get_kpis(company_id, period_id):
    # Personal
    emp = query_db(
        """SELECT COUNT(*) as total,
                  SUM(CASE WHEN is_active=1 THEN total_monthly_cost ELSE 0 END) as costo_mes,
                  SUM(CASE WHEN is_active=1 AND labor_type='MOD' THEN 1 ELSE 0 END) as total_mod
           FROM employees WHERE company_id=?""",
        (company_id,), one=True
    )

    # Inventario
    inv = query_db(
        """SELECT COUNT(*) as items,
                  SUM(current_stock * average_cost) as valor
           FROM inventory_items WHERE company_id=? AND is_active=1""",
        (company_id,), one=True
    )

    # Presupuesto activo
    budget = query_db(
        "SELECT total_sales, gross_profit, net_income FROM budgets WHERE company_id=? AND period_id=? LIMIT 1",
        (company_id, period_id), one=True
    )

    # Costos de calidad
    quality = query_db(
        """SELECT SUM(monthly_cost) as total,
                  SUM(CASE WHEN category IN ('falla_interna','falla_externa') THEN monthly_cost ELSE 0 END) as fallas
           FROM quality_costs WHERE company_id=? AND period_id=?""",
        (company_id, period_id), one=True
    )

    # Estructuras de costos
    structures = query_db(
        "SELECT COUNT(*) as total FROM cost_structures WHERE company_id=?",
        (company_id,), one=True
    )

    # ABC modelos
    abc = query_db(
        "SELECT COUNT(*) as total FROM abc_models WHERE company_id=? AND period_id=?",
        (company_id, period_id), one=True
    )

    ventas = budget['total_sales'] if budget and budget['total_sales'] else 0
    utilidad = budget['net_income'] if budget and budget['net_income'] else 0
    margen = (utilidad / ventas * 100) if ventas else 0
    costo_calidad = quality['total'] if quality and quality['total'] else 0
    pct_fallas = (quality['fallas'] / costo_calidad * 100) if (quality and quality['fallas'] and costo_calidad) else 0

    return {
        'ventas_proyectadas': ventas,
        'utilidad_proyectada': utilidad,
        'margen_bruto': round(margen, 1),
        'total_personal': emp['total'] if emp else 0,
        'total_mod': emp['total_mod'] if emp else 0,
        'costo_personal_mes': round(emp['costo_mes'] or 0, 2) if emp else 0,
        'items_inventario': inv['items'] if inv else 0,
        'stock_valorizado': round(inv['valor'] or 0, 2) if inv else 0,
        'costo_calidad': round(costo_calidad, 2),
        'pct_fallas': round(pct_fallas, 1),
        'total_estructuras': structures['total'] if structures else 0,
        'total_abc_modelos': abc['total'] if abc else 0,
    }


def _get_chart_data(company_id, period_id):
    # Personal por tipo
    personal_tipo = query_db(
        """SELECT labor_type, COUNT(*) as cnt, SUM(total_monthly_cost) as costo
           FROM employees WHERE company_id=? AND is_active=1
           GROUP BY labor_type""",
        (company_id,)
    )

    # Inventario top 5 por valor
    inv_top = query_db(
        """SELECT name, current_stock * average_cost as valor
           FROM inventory_items WHERE company_id=? AND is_active=1
           ORDER BY valor DESC LIMIT 5""",
        (company_id,)
    )

    # Costos de calidad por categoría
    quality_cat = query_db(
        """SELECT category, SUM(monthly_cost) as total
           FROM quality_costs WHERE company_id=? AND period_id=?
           GROUP BY category""",
        (company_id, period_id)
    )

    cat_labels = {
        'prevencion': 'Prevención',
        'evaluacion': 'Evaluación',
        'falla_interna': 'Falla Interna',
        'falla_externa': 'Falla Externa',
        'no_aplica': 'No Aplica',
    }
    labor_labels = {
        'MOD': 'Mano de Obra Directa',
        'MOI': 'Mano de Obra Indirecta',
        'admin': 'Administrativo',
        'ventas': 'Ventas',
    }

    return {
        'personal_labels': [labor_labels.get(r['labor_type'], r['labor_type']) for r in personal_tipo],
        'personal_costos': [round(r['costo'] or 0, 2) for r in personal_tipo],
        'inv_labels': [r['name'] for r in inv_top],
        'inv_valores': [round(r['valor'] or 0, 2) for r in inv_top],
        'quality_labels': [cat_labels.get(r['category'], r['category']) for r in quality_cat],
        'quality_valores': [round(r['total'] or 0, 2) for r in quality_cat],
    }


@dashboard_bp.route('/dashboard/alerts')
@login_required
@company_required
def alerts():
    """Genera alertas inteligentes basadas en los datos actuales."""
    company_id = session['company_id']
    period_id  = session.get('period_id')
    
    alerts = []
    
    # Alerta: ítems bajo stock mínimo
    bajo_minimo = query_db(
        """SELECT name, current_stock, safety_stock FROM inventory_items
           WHERE company_id=? AND is_active=1 AND safety_stock > 0
           AND current_stock < safety_stock""",
        (company_id,)
    )
    for item in bajo_minimo:
        alerts.append({
            'type': 'danger',
            'icon': 'ti-alert-circle',
            'title': f'Stock bajo: {item["name"]}',
            'msg': f'Stock actual: {item["current_stock"]} — Mínimo: {item["safety_stock"]}',
            'module': 'kardex',
        })
    
    # Alerta: costos de fallas > 40% del total calidad
    calidad = query_db(
        """SELECT SUM(monthly_cost) as total,
                  SUM(CASE WHEN category IN ("falla_interna","falla_externa") THEN monthly_cost ELSE 0 END) as fallas
           FROM quality_costs WHERE company_id=? AND period_id=?""",
        (company_id, period_id), one=True
    )
    if calidad and calidad['total'] and float(calidad['total']) > 0:
        pct_fallas = float(calidad['fallas'] or 0) / float(calidad['total']) * 100
        if pct_fallas > 40:
            alerts.append({
                'type': 'warning',
                'icon': 'ti-alert-triangle',
                'title': 'Alto costo de fallas en calidad',
                'msg': f'{pct_fallas:.1f}% del costo de calidad corresponde a fallas. Meta: <20%',
                'module': 'quality_costs',
            })
    
    # Alerta: sin período activo
    if not period_id:
        alerts.append({
            'type': 'warning',
            'icon': 'ti-calendar',
            'title': 'Sin período activo',
            'msg': 'Configura un período contable para registrar datos correctamente.',
            'module': 'companies',
        })
    
    # Alerta: sin presupuesto en período actual
    if period_id:
        budget = query_db(
            "SELECT id FROM budgets WHERE company_id=? AND period_id=? LIMIT 1",
            (company_id, period_id), one=True
        )
        if not budget:
            alerts.append({
                'type': 'info',
                'icon': 'ti-coin',
                'title': 'Sin presupuesto para este período',
                'msg': 'Crea un presupuesto operativo para proyectar ventas y costos.',
                'module': 'budgets',
            })
    
    # Alerta: sin recursos ABC registrados
    rec_count = query_db(
        "SELECT COUNT(*) as n FROM resources WHERE company_id=?",
        (company_id,), one=True
    )
    if rec_count and rec_count['n'] == 0:
        alerts.append({
            'type': 'info',
            'icon': 'ti-database',
            'title': 'Sistema ABC sin recursos',
            'msg': 'Registra recursos para poder calcular costos ABC.',
            'module': 'resources',
        })
    
    if not alerts:
        alerts.append({
            'type': 'success',
            'icon': 'ti-check',
            'title': 'Todo en orden',
            'msg': 'No se detectaron alertas para este período.',
            'module': None,
        })
    
    return jsonify({'success': True, 'alerts': alerts, 'count': len(alerts)})
