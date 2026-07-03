from flask import Blueprint, render_template, session, request, jsonify
from models.database import query_db
from routes.dashboard import login_required, company_required, module_required

compare_bp = Blueprint('compare', __name__)


def _safe(v):
    return float(v) if v else 0.0


def _get_period_kpis(company_id: int, period_id: int) -> dict:
    """KPIs de un período específico."""
    personal = query_db(
        "SELECT COUNT(*) as n, SUM(total_monthly_cost) as costo FROM employees WHERE company_id=? AND is_active=1",
        (company_id,), one=True
    )
    presupuesto = query_db(
        "SELECT total_sales, total_production_cost, gross_profit FROM budgets WHERE company_id=? AND period_id=? LIMIT 1",
        (company_id, period_id), one=True
    )
    inventario = query_db(
        "SELECT SUM(current_stock * average_cost) as valor FROM inventory_items WHERE company_id=? AND is_active=1",
        (company_id,), one=True
    )
    calidad = query_db(
        "SELECT SUM(monthly_cost) as total FROM quality_costs WHERE company_id=? AND period_id=?",
        (company_id, period_id), one=True
    )
    abc = query_db(
        "SELECT COUNT(*) as n FROM abc_models WHERE company_id=? AND period_id=? AND status='calculado'",
        (company_id, period_id), one=True
    )

    ventas     = _safe(presupuesto['total_sales'] if presupuesto else 0)
    utilidad   = _safe(presupuesto['gross_profit'] if presupuesto else 0)
    costo_prod = _safe(presupuesto['total_production_cost'] if presupuesto else 0)

    return {
        'ventas':          round(ventas, 2),
        'costo_prod':      round(costo_prod, 2),
        'utilidad':        round(utilidad, 2),
        'margen_pct':      round((utilidad / ventas * 100) if ventas else 0, 1),
        'costo_personal':  round(_safe(personal['costo'] if personal else 0), 2),
        'headcount':       personal['n'] if personal else 0,
        'stock_valor':     round(_safe(inventario['valor'] if inventario else 0), 2),
        'costo_calidad':   round(_safe(calidad['total'] if calidad else 0), 2),
        'modelos_abc':     abc['n'] if abc else 0,
    }


def _variacion(v1, v2):
    """Calcula variación % entre dos valores."""
    if v1 == 0:
        return 0 if v2 == 0 else 100
    return round((v2 - v1) / abs(v1) * 100, 1)


@compare_bp.route('/compare')
@login_required
@company_required
@module_required('compare', write=False)
def index():
    session['active_module'] = 'compare'
    company_id = session['company_id']

    periods = query_db(
        "SELECT * FROM periods WHERE company_id=? ORDER BY start_date DESC",
        (company_id,)
    )

    # Períodos seleccionados via query params
    pid1 = request.args.get('p1', type=int)
    pid2 = request.args.get('p2', type=int)

    data1 = data2 = period1 = period2 = None

    if pid1 and pid2:
        period1 = query_db("SELECT * FROM periods WHERE id=? AND company_id=?", (pid1, company_id), one=True)
        period2 = query_db("SELECT * FROM periods WHERE id=? AND company_id=?", (pid2, company_id), one=True)
        if period1 and period2:
            data1 = _get_period_kpis(company_id, pid1)
            data2 = _get_period_kpis(company_id, pid2)

            # Calcular variaciones
            vars_ = {}
            for key in data1:
                vars_[key] = _variacion(data1[key], data2[key])

            return render_template('compare/index.html',
                                   periods=periods,
                                   period1=period1, period2=period2,
                                   data1=data1, data2=data2,
                                   vars=vars_,
                                   pid1=pid1, pid2=pid2)

    return render_template('compare/index.html',
                           periods=periods,
                           period1=None, period2=None,
                           data1=None, data2=None,
                           vars=None, pid1=pid1, pid2=pid2)
