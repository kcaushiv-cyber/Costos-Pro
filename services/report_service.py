"""
Servicio de Reportes Gerenciales — Costos Pro v5
Agrega datos de Fases 1-3 para generar reportes ejecutivos.
"""
from models.database import query_db


def _safe(v):
    return float(v) if v else 0.0


# ── Reporte 1: Resumen Ejecutivo ───────────────────────────────────────────

def get_executive_summary(company_id: int, period_id: int) -> dict:
    """KPIs consolidados de todos los módulos para el período activo."""

    # Personal
    personal = query_db(
        """SELECT COUNT(*) as total,
                  SUM(CASE WHEN is_active=1 THEN total_monthly_cost ELSE 0 END) as costo_mes,
                  SUM(CASE WHEN labor_type='MOD' AND is_active=1 THEN total_monthly_cost ELSE 0 END) as costo_mod,
                  SUM(CASE WHEN labor_type='MOI' AND is_active=1 THEN total_monthly_cost ELSE 0 END) as costo_moi
           FROM employees WHERE company_id=?""",
        (company_id,), one=True
    )

    # Inventario
    inventario = query_db(
        """SELECT COUNT(*) as items,
                  SUM(current_stock * average_cost) as valor,
                  SUM(CASE WHEN safety_stock > 0 AND current_stock < safety_stock THEN 1 ELSE 0 END) as bajo_minimo
           FROM inventory_items WHERE company_id=? AND is_active=1""",
        (company_id,), one=True
    )

    # ABC
    abc = query_db(
        """SELECT COUNT(*) as modelos,
                  SUM(ar.total_cost) as costo_total_abc
           FROM abc_models m
           LEFT JOIN abc_results ar ON ar.abc_model_id = m.id
           WHERE m.company_id=? AND m.period_id=?""",
        (company_id, period_id), one=True
    )

    # Presupuesto
    presupuesto = query_db(
        "SELECT total_sales, total_production_cost, gross_profit, net_income FROM budgets WHERE company_id=? AND period_id=? LIMIT 1",
        (company_id, period_id), one=True
    )

    # Calidad
    calidad = query_db(
        """SELECT SUM(monthly_cost) as total,
                  SUM(CASE WHEN category IN ('falla_interna','falla_externa') THEN monthly_cost ELSE 0 END) as fallas,
                  SUM(CASE WHEN category='prevencion' THEN monthly_cost ELSE 0 END) as prevencion
           FROM quality_costs WHERE company_id=? AND period_id=?""",
        (company_id, period_id), one=True
    )

    # Proceso
    proceso = query_db(
        "SELECT COUNT(*) as modelos FROM process_cost_models WHERE company_id=? AND period_id=? AND status='calculado'",
        (company_id, period_id), one=True
    )

    ventas = _safe(presupuesto['total_sales'] if presupuesto else 0)
    utilidad = _safe(presupuesto['gross_profit'] if presupuesto else 0)
    costo_calidad = _safe(calidad['total'] if calidad else 0)
    fallas = _safe(calidad['fallas'] if calidad else 0)

    return {
        'personal': {
            'total': personal['total'] if personal else 0,
            'costo_mes': round(_safe(personal['costo_mes'] if personal else 0), 2),
            'costo_mod': round(_safe(personal['costo_mod'] if personal else 0), 2),
            'costo_moi': round(_safe(personal['costo_moi'] if personal else 0), 2),
        },
        'inventario': {
            'total_items': inventario['items'] if inventario else 0,
            'valor': round(_safe(inventario['valor'] if inventario else 0), 2),
            'bajo_minimo': inventario['bajo_minimo'] if inventario else 0,
        },
        'abc': {
            'modelos': abc['modelos'] if abc else 0,
            'costo_total': round(_safe(abc['costo_total_abc'] if abc else 0), 2),
        },
        'presupuesto': {
            'ventas': round(ventas, 2),
            'costo': round(_safe(presupuesto['total_production_cost'] if presupuesto else 0), 2),
            'utilidad': round(utilidad, 2),
            'margen_pct': round((utilidad / ventas * 100) if ventas else 0, 1),
        },
        'calidad': {
            'total': round(costo_calidad, 2),
            'fallas': round(fallas, 2),
            'prevencion': round(_safe(calidad['prevencion'] if calidad else 0), 2),
            'pct_fallas': round((fallas / costo_calidad * 100) if costo_calidad else 0, 1),
            'pct_ventas': round((costo_calidad / ventas * 100) if ventas else 0, 2),
        },
        'proceso': {
            'modelos_calculados': proceso['modelos'] if proceso else 0,
        },
    }


# ── Reporte 2: Estructura de Costos ───────────────────────────────────────

def get_cost_structure_report(company_id: int, period_id: int) -> dict:
    """Consolidado de estructuras de costos del período."""
    structures = query_db(
        """SELECT cs.*, p.name as period_name
           FROM cost_structures cs
           LEFT JOIN periods p ON cs.period_id = p.id
           WHERE cs.company_id=?
           ORDER BY cs.created_at DESC""",
        (company_id,)
    )

    data = []
    for s in structures:
        cats = query_db(
            "SELECT * FROM cost_categories WHERE structure_id=? ORDER BY order_index",
            (s['id'],)
        )
        items_sum = query_db(
            """SELECT cc.category_type, SUM(ci.total_cost) as subtotal
               FROM cost_items ci JOIN cost_categories cc ON ci.category_id=cc.id
               WHERE cc.structure_id=? GROUP BY cc.category_type""",
            (s['id'],)
        )
        by_type = {r['category_type']: _safe(r['subtotal']) for r in items_sum}
        total = sum(by_type.values())
        data.append({
            'id': s['id'],
            'name': s['name'],
            'product': s['product_service'],
            'origin': s['origin'],
            'mp': round(by_type.get('mp', 0), 2),
            'mod': round(by_type.get('mod', 0), 2),
            'cif': round(by_type.get('cif', 0), 2),
            'gasto_admin': round(by_type.get('gasto_admin', 0), 2),
            'gasto_ventas': round(by_type.get('gasto_ventas', 0), 2),
            'total': round(total, 2),
            'sale_price': _safe(s['sale_price']),
            'margin': round((_safe(s['sale_price']) - total), 2),
        })
    return {'structures': data}


# ── Reporte 3: Análisis ABC ────────────────────────────────────────────────

def get_abc_report(company_id: int, period_id: int) -> dict:
    """Resultados ABC del período con comparación tradicional."""
    results = query_db(
        """SELECT ar.*, co.name as obj_name, co.code as obj_code,
                  co.quantity_month, m.name as model_name
           FROM abc_results ar
           JOIN cost_objects co ON ar.cost_object_id = co.id
           JOIN abc_models m ON ar.abc_model_id = m.id
           WHERE m.company_id=? AND m.period_id=?
           ORDER BY ar.total_cost DESC""",
        (company_id, period_id)
    )

    data = []
    for r in results:
        qty = _safe(r['quantity_month']) or 1
        data.append({
            'model': r['model_name'],
            'obj_code': r['obj_code'],
            'obj_name': r['obj_name'],
            'qty': qty,
            'prod_cost': round(_safe(r['production_cost']), 2),
            'total_cost': round(_safe(r['total_cost']), 2),
            'sale_price': round(_safe(r['sale_price']), 2),
            'unit_cost_abc': round(_safe(r['unit_cost_abc']), 4),
            'unit_cost_trad': round(_safe(r['unit_cost_traditional']), 4),
            'diff': round(_safe(r['unit_cost_abc']) - _safe(r['unit_cost_traditional']), 4),
            'diff_pct': round(
                ((_safe(r['unit_cost_abc']) - _safe(r['unit_cost_traditional'])) /
                 _safe(r['unit_cost_traditional']) * 100)
                if _safe(r['unit_cost_traditional']) else 0, 1
            ),
        })
    return {'results': data}


# ── Reporte 4: Personal y MOD ──────────────────────────────────────────────

def get_labor_report(company_id: int) -> dict:
    """Análisis de planilla y utilización de horas."""
    employees = query_db(
        """SELECT e.*, d.name as dept_name, p.name as position_name
           FROM employees e
           LEFT JOIN departments d ON e.department_id=d.id
           LEFT JOIN positions p ON e.position_id=p.id
           WHERE e.company_id=? AND e.is_active=1
           ORDER BY e.labor_type, e.total_monthly_cost DESC""",
        (company_id,)
    )

    by_type = {}
    for e in employees:
        t = e['labor_type']
        if t not in by_type:
            by_type[t] = {'count': 0, 'total_cost': 0.0, 'total_hours': 0.0}
        by_type[t]['count']      += 1
        by_type[t]['total_cost'] += _safe(e['total_monthly_cost'])
        by_type[t]['total_hours']+= _safe(e['available_hours_month'])

    total_cost = sum(v['total_cost'] for v in by_type.values())

    return {
        'employees': [dict(e) for e in employees],
        'by_type': by_type,
        'total_cost': round(total_cost, 2),
        'total_headcount': len(employees),
    }


# ── Reporte 5: Inventario ──────────────────────────────────────────────────

def get_inventory_report(company_id: int) -> dict:
    """Stock valorizado con alertas y movimientos recientes."""
    items = query_db(
        """SELECT ii.*, u.code as unit_code,
                  (ii.current_stock * ii.average_cost) as valor_total
           FROM inventory_items ii
           LEFT JOIN units_of_measure u ON ii.unit_id=u.id
           WHERE ii.company_id=? AND ii.is_active=1
           ORDER BY valor_total DESC""",
        (company_id,)
    )

    total_valor = sum(_safe(i['valor_total']) for i in items)
    bajo_minimo = [i for i in items if i['safety_stock'] and _safe(i['current_stock']) < _safe(i['safety_stock'])]

    # Últimos 10 movimientos
    movimientos = query_db(
        """SELECT km.*, ii.name as item_name
           FROM kardex_movements km
           JOIN inventory_items ii ON km.inventory_item_id=ii.id
           WHERE ii.company_id=?
           ORDER BY km.movement_date DESC, km.id DESC
           LIMIT 10""",
        (company_id,)
    )

    return {
        'item_list': [dict(i) for i in items],
        'total_valor': round(total_valor, 2),
        'bajo_minimo': [dict(i) for i in bajo_minimo],
        'movimientos_recientes': [dict(m) for m in movimientos],
    }


# ── Reporte 6: Calidad PAF ─────────────────────────────────────────────────

def get_quality_report(company_id: int, period_id: int) -> dict:
    """Análisis PAF completo con tendencia."""
    costs = query_db(
        """SELECT * FROM quality_costs
           WHERE company_id=? AND period_id=?
           ORDER BY category, monthly_cost DESC""",
        (company_id, period_id)
    )

    cats = {'prevencion': 0.0, 'evaluacion': 0.0, 'falla_interna': 0.0, 'falla_externa': 0.0}
    for c in costs:
        cat = c['category']
        if cat in cats:
            cats[cat] += _safe(c['monthly_cost'])

    total = sum(cats.values())
    budget = query_db(
        "SELECT total_sales FROM budgets WHERE company_id=? AND period_id=? LIMIT 1",
        (company_id, period_id), one=True
    )
    ventas = _safe(budget['total_sales'] if budget else 0)

    return {
        'costs': [dict(c) for c in costs],
        'totals': {k: round(v, 2) for k, v in cats.items()},
        'grand_total': round(total, 2),
        'conformance': round(cats['prevencion'] + cats['evaluacion'], 2),
        'nonconformance': round(cats['falla_interna'] + cats['falla_externa'], 2),
        'pct_ventas': round((total / ventas * 100) if ventas else 0, 2),
        'pct_fallas': round(((cats['falla_interna'] + cats['falla_externa']) / total * 100) if total else 0, 1),
    }
