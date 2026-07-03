from flask import Blueprint, render_template, session, jsonify
from models.database import query_db
from routes.dashboard import login_required, company_required, module_required
from services.claude_service import send_message
import json

breakeven_bp = Blueprint('breakeven', __name__)


def _safe(v):
    return float(v) if v else 0.0


def _latest_model_id(company_id: int, period_id: int) -> int:
    """Último modelo ABC calculado/aprobado del período."""
    row = query_db(
        """SELECT id
           FROM abc_models
           WHERE company_id=? AND period_id=? AND status IN ('calculado', 'aprobado')
           ORDER BY COALESCE(calculated_at, created_at) DESC, id DESC
           LIMIT 1""",
        (company_id, period_id), one=True
    )
    return int(row['id']) if row else 0


def _fixed_costs(company_id: int, period_id: int) -> dict:
    """Costos fijos mensuales usados en la recta de costos totales."""
    # Personal admin + MOI + ventas
    personal_fijo = query_db(
        """SELECT SUM(total_monthly_cost) as total FROM employees
           WHERE company_id=? AND is_active=1 AND labor_type IN ('admin','MOI','ventas')""",
        (company_id,), one=True
    )
    costo_personal_fijo = _safe(personal_fijo['total'] if personal_fijo else 0)

    # Recursos de comportamiento fijo mensual
    recursos_fijos = query_db(
        """SELECT SUM(monthly_amount) as total FROM resources
           WHERE company_id=? AND (period_id=? OR period_id IS NULL)
           AND category IN ('depreciacion','seguros','servicios','mantenimiento','alquiler','otros')""",
        (company_id, period_id), one=True
    )
    costo_recursos_fijos = _safe(recursos_fijos['total'] if recursos_fijos else 0)

    # CIF fijos del presupuesto
    cif_fijo = query_db(
        """SELECT SUM(amount) as total FROM budget_cif bc
           JOIN budgets b ON bc.budget_id = b.id
           WHERE b.company_id=? AND b.period_id=? AND bc.cif_type='fijo'""",
        (company_id, period_id), one=True
    )
    costo_cif_fijo = _safe(cif_fijo['total'] if cif_fijo else 0)

    # Servicio de deuda mensual: si el presupuesto lo guarda anual, se mensualiza.
    deuda = query_db(
        """SELECT SUM(bds.fee) as total FROM budget_debt_service bds
           JOIN budgets b ON bds.budget_id = b.id
           WHERE b.company_id=? AND b.period_id=?""",
        (company_id, period_id), one=True
    )
    costo_deuda = _safe(deuda['total'] if deuda else 0) / 12

    total = costo_personal_fijo + costo_recursos_fijos + costo_cif_fijo + costo_deuda
    return {
        'personal_admin_moi': costo_personal_fijo,
        'recursos_fijos': costo_recursos_fijos,
        'cif_fijo': costo_cif_fijo,
        'deuda': costo_deuda,
        'total': total,
    }


def _object_rows_for_breakeven(company_id: int, period_id: int, model_id: int):
    """Objetos con precio de venta unitario y costo unitario ABC vigente."""
    return query_db(
        """SELECT co.id, co.code, co.name, co.quantity_month,
                  COALESCE(ar.unit_cost_abc, co.unit_cost_abc, 0) as unit_cost_abc,
                  ar.total_cost as abc_total_cost,
                  ar.sale_price as abc_total_sale_price,
                  ps.sale_price as catalog_price
           FROM cost_objects co
           LEFT JOIN products_services ps ON co.product_id = ps.id
           LEFT JOIN abc_results ar
                  ON ar.cost_object_id = co.id
                 AND ar.abc_model_id = ?
           WHERE co.company_id=? AND (co.period_id=? OR co.period_id IS NULL)
           ORDER BY co.name""",
        (model_id, company_id, period_id)
    ) or []


def _legacy_variable_costs(company_id: int, period_id: int) -> dict:
    """Respaldo cuando todavía no hay ABC calculado."""
    personal_variable = query_db(
        """SELECT SUM(total_monthly_cost) as total FROM employees
           WHERE company_id=? AND is_active=1 AND labor_type='MOD'""",
        (company_id,), one=True
    )
    costo_mod = _safe(personal_variable['total'] if personal_variable else 0)

    mp = query_db(
        """SELECT SUM(current_stock * average_cost) as valor
           FROM inventory_items
           WHERE company_id=? AND is_active=1 AND category='insumo'""",
        (company_id,), one=True
    )
    costo_mp_mensual = _safe(mp['valor'] if mp and mp['valor'] else 0)

    cif_var = query_db(
        """SELECT SUM(amount) as total FROM budget_cif bc
           JOIN budgets b ON bc.budget_id = b.id
           WHERE b.company_id=? AND b.period_id=? AND bc.cif_type='variable'""",
        (company_id, period_id), one=True
    )
    costo_cif_variable = _safe(cif_var['total'] if cif_var else 0)
    total = costo_mod + costo_mp_mensual + costo_cif_variable
    return {
        'mod': costo_mod,
        'materia_prima': costo_mp_mensual,
        'cif_variable': costo_cif_variable,
        'abc_total': 0.0,
        'total': total,
        'source': 'legacy',
    }


def calculate_breakeven(company_id: int, period_id: int) -> dict:
    """
    Punto de equilibrio correcto:

        Ingresos(x)       = Precio de venta unitario × x
        Costos totales(x) = Costos fijos + Costo variable unitario × x

    Cuando existe ABC calculado, el costo variable unitario se toma del costo
    unitario ABC de los objetos de costo. El precio de venta unitario se toma
    del producto vinculado a cada objeto.
    """
    costos_fijos = _fixed_costs(company_id, period_id)
    total_costos_fijos = costos_fijos['total']

    latest_model_id = _latest_model_id(company_id, period_id)
    object_rows = _object_rows_for_breakeven(company_id, period_id, latest_model_id)

    total_units = 0.0
    total_sales_value = 0.0
    total_abc_variable_cost = 0.0
    objects_with_abc = 0
    objects_with_price = 0

    for row in object_rows:
        qty = _safe(row['quantity_month'])
        unit_abc = _safe(row['unit_cost_abc'])
        price = _safe(row['catalog_price'])

        # Si no hay precio en catálogo, usar precio ABC total / cantidad como respaldo.
        if price <= 0 and qty > 0:
            price = _safe(row['abc_total_sale_price']) / qty

        total_units += qty
        total_sales_value += price * qty

        if unit_abc > 0:
            total_abc_variable_cost += unit_abc * qty
            objects_with_abc += 1
        if price > 0:
            objects_with_price += 1

    abc_calculado = latest_model_id > 0 and objects_with_abc > 0

    legacy_vars = _legacy_variable_costs(company_id, period_id)

    if total_units <= 0:
        # Respaldo por presupuestos si no se cargaron objetos de costo.
        prod = query_db(
            """SELECT SUM(bp.required_production) as total
               FROM budget_production bp
               JOIN budgets b ON bp.budget_id=b.id
               WHERE b.company_id=? AND b.period_id=?""",
            (company_id, period_id), one=True
        )
        total_units = _safe(prod['total'] if prod else 0)

    if total_sales_value <= 0:
        ventas = query_db(
            """SELECT SUM(bs.total_sales) as total
               FROM budget_sales bs
               JOIN budgets b ON bs.budget_id=b.id
               WHERE b.company_id=? AND b.period_id=?""",
            (company_id, period_id), one=True
        )
        total_sales_value = _safe(ventas['total'] if ventas else 0)

    unidades_base = total_units if total_units > 0 else 1.0
    precio_unitario = total_sales_value / unidades_base if unidades_base else 0.0

    if abc_calculado:
        total_costos_variables = total_abc_variable_cost
        cvu = total_abc_variable_cost / unidades_base if unidades_base else 0.0
        variable_source = 'ABC'
    else:
        total_costos_variables = legacy_vars['total']
        cvu = total_costos_variables / unidades_base if unidades_base else 0.0
        variable_source = 'datos registrados'

    mcv = precio_unitario - cvu
    mcv_pct = (mcv / precio_unitario * 100) if precio_unitario else 0.0

    if mcv > 0:
        pe_unidades = total_costos_fijos / mcv
        pe_soles = pe_unidades * precio_unitario
    else:
        pe_unidades = 0.0
        pe_soles = 0.0

    margen_seguridad = total_units - pe_unidades
    margen_seg_pct = (margen_seguridad / total_units * 100) if total_units else 0.0

    return {
        'costos_fijos': {
            'personal_admin_moi': round(costos_fijos['personal_admin_moi'], 2),
            'recursos_fijos': round(costos_fijos['recursos_fijos'], 2),
            'cif_fijo': round(costos_fijos['cif_fijo'], 2),
            'deuda': round(costos_fijos['deuda'], 2),
            'total': round(total_costos_fijos, 2),
        },
        'costos_variables': {
            'mod': round(legacy_vars['mod'], 2),
            'materia_prima': round(legacy_vars['materia_prima'], 2),
            'cif_variable': round(legacy_vars['cif_variable'], 2),
            'abc_total': round(total_abc_variable_cost, 2),
            'total': round(total_costos_variables, 2),
            'source': variable_source,
        },
        'abc_calculado': abc_calculado,
        'abc_model_id': latest_model_id,
        'objects_with_abc': objects_with_abc,
        'objects_with_price': objects_with_price,
        'precio_unitario': round(precio_unitario, 4),
        'cvu': round(cvu, 4),
        'mcv': round(mcv, 4),
        'mcv_pct': round(mcv_pct, 1),
        'pe_unidades': round(pe_unidades, 0),
        'pe_soles': round(pe_soles, 2),
        'unidades_producidas': round(total_units, 0),
        'ventas_actuales': round(total_sales_value, 2),
        'margen_seguridad_uds': round(margen_seguridad, 0),
        'margen_seguridad_pct': round(margen_seg_pct, 1),
        'en_equilibrio': total_units >= pe_unidades if mcv > 0 else False,
    }


@breakeven_bp.route('/breakeven')
@login_required
@company_required
@module_required('breakeven', write=False)
def index():
    session['active_module'] = 'breakeven'
    company_id = session['company_id']
    period_id  = session.get('period_id')
    data = calculate_breakeven(company_id, period_id)
    cost_objects = query_db(
        "SELECT id, code, name FROM cost_objects WHERE company_id=? AND (period_id=? OR period_id IS NULL) ORDER BY name",
        (company_id, period_id)
    )
    return render_template('breakeven/index.html', data=data, cost_objects=cost_objects or [])


@breakeven_bp.route('/breakeven/api/data')
@login_required
@company_required
@module_required('breakeven', write=False)
def api_data():
    company_id = session['company_id']
    period_id  = session.get('period_id')
    data = calculate_breakeven(company_id, period_id)
    return jsonify({'success': True, 'data': data})


@breakeven_bp.route('/breakeven/api/narrative', methods=['GET'])
@login_required
@company_required
@module_required('breakeven', write=False)
def api_narrative():
    company_id = session['company_id']
    period_id  = session.get('period_id')
    data = calculate_breakeven(company_id, period_id)

    prompt = (
        f"Analiza el punto de equilibrio para {session.get('company_name')} "
        f"del sector {session.get('sector')}, período {session.get('period_name')}:\n\n"
        f"- Costos fijos totales: S/ {data['costos_fijos']['total']:,.2f}\n"
        f"- Costo variable unitario: S/ {data['cvu']:,.4f}\n"
        f"- Precio de venta unitario: S/ {data['precio_unitario']:,.4f}\n"
        f"- Margen de contribución: S/ {data['mcv']:,.4f} ({data['mcv_pct']}%)\n"
        f"- Punto de equilibrio: {data['pe_unidades']:,.0f} unidades / S/ {data['pe_soles']:,.2f}\n"
        f"- Producción actual: {data['unidades_producidas']:,.0f} unidades\n"
        f"- Margen de seguridad: {data['margen_seguridad_uds']:,.0f} uds ({data['margen_seguridad_pct']}%)\n\n"
        f"Explica qué significa este punto de equilibrio para la empresa, "
        f"si está en zona segura o de riesgo, y da 3 recomendaciones concretas "
        f"para mejorar el margen de contribución o reducir costos fijos."
    )
    result = send_message(prompt, agent_type='reportes')
    return jsonify(result)


@breakeven_bp.route('/breakeven/product/<int:product_id>')
@login_required
@company_required
@module_required('breakeven', write=False)
def by_product(product_id):
    """PE para un producto/objeto de costo específico con costo unitario ABC."""
    company_id = session['company_id']
    period_id  = session.get('period_id')
    latest_model_id = _latest_model_id(company_id, period_id)

    obj = query_db(
        """SELECT co.*, ps.sale_price as catalog_price,
                  ar.unit_cost_abc as result_unit_cost_abc,
                  ar.total_cost as result_total_cost,
                  ar.sale_price as result_sale_price
           FROM cost_objects co
           LEFT JOIN products_services ps ON co.product_id = ps.id
           LEFT JOIN abc_results ar
                  ON ar.cost_object_id = co.id
                 AND ar.abc_model_id = ?
           WHERE co.id=? AND co.company_id=?""",
        (latest_model_id, product_id, company_id), one=True
    )
    if not obj:
        return jsonify({'success': False, 'error': 'Producto no encontrado'}), 404

    qty = _safe(obj['quantity_month'])
    precio = _safe(obj['catalog_price'])
    if precio <= 0 and qty > 0:
        precio = _safe(obj['result_sale_price']) / qty

    # El costo variable unitario del PE por producto viene del costo unitario ABC.
    cu_var = _safe(obj['result_unit_cost_abc']) or _safe(obj['unit_cost_abc'])
    if cu_var <= 0:
        return jsonify({
            'success': False,
            'error': 'Primero calcula el ABC para este objeto de costo. Sin costo unitario ABC no se puede calcular el punto de equilibrio.'
        }), 400
    if precio <= 0:
        return jsonify({
            'success': False,
            'error': 'Este objeto no tiene precio de venta unitario. Vincúlalo a un producto con precio de venta o registra el precio antes de calcular el PE.'
        }), 400

    cf_fijo = _fixed_costs(company_id, period_id)['total']
    mcv = precio - cu_var
    pe_uds = (cf_fijo / mcv) if mcv > 0 else 0.0
    pe_sol = pe_uds * precio

    data = {
        'producto': obj['name'],
        'precio_unitario': round(precio, 4),
        'cu_variable': round(cu_var, 4),
        'costo_fijo_total': round(cf_fijo, 2),
        'mcv': round(mcv, 4),
        'mcv_pct': round((mcv / precio * 100) if precio else 0, 1),
        'pe_unidades': round(pe_uds, 0),
        'pe_soles': round(pe_sol, 2),
        'unidades_producidas': qty,
        'margen_seguridad_pct': round(((qty - pe_uds) / qty * 100) if qty else 0, 1),
        'en_equilibrio': qty >= pe_uds if mcv > 0 else False,
        'formula': {
            'ingresos': 'Ingresos = precio de venta unitario × unidades',
            'costos': 'Costos totales = costos fijos + costo unitario ABC × unidades'
        }
    }
    return jsonify({'success': True, 'data': data})
