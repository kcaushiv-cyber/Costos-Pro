from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, flash
from models.database import query_db, execute_db
from routes.dashboard import login_required, company_required, module_required
from services.budget_service import get_budget_summary, calculate_cashflow, calculate_debt_service

budgets_bp = Blueprint('budgets', __name__)


@budgets_bp.route('/budgets')
@login_required
@company_required
@module_required('budgets', write=False)
def index():
    session['active_module'] = 'budgets'
    company_id = session['company_id']
    period_id  = session.get('period_id')

    budgets = query_db(
        "SELECT * FROM budgets WHERE company_id=? AND period_id=? ORDER BY created_at DESC",
        (company_id, period_id)
    )
    return render_template('budgets/index.html', budgets=budgets)


@budgets_bp.route('/budgets/new', methods=['GET', 'POST'])
@login_required
@company_required
@module_required('budgets', write=True)
def new():
    company_id = session['company_id']
    period_id  = session.get('period_id')

    if request.method == 'POST':
        d = request.form
        bid = execute_db(
            "INSERT INTO budgets (company_id, period_id, name) VALUES (?,?,?)",
            (company_id, period_id, d['name'])
        )
        flash('Presupuesto creado', 'success')
        return redirect(url_for('budgets.detail', bid=bid))

    return render_template('budgets/new.html')


@budgets_bp.route('/budgets/<int:bid>')
@login_required
@company_required
@module_required('budgets', write=False)
def detail(bid):
    company_id = session['company_id']
    budget = query_db("SELECT * FROM budgets WHERE id=? AND company_id=?",
                      (bid, company_id), one=True)
    if not budget:
        return redirect(url_for('budgets.index'))

    summary   = get_budget_summary(bid)
    sales     = query_db("SELECT * FROM budget_sales     WHERE budget_id=? ORDER BY month, product_name", (bid,))
    prod      = query_db("SELECT * FROM budget_production WHERE budget_id=? ORDER BY month, product_name", (bid,))
    labor     = query_db("SELECT * FROM budget_labor     WHERE budget_id=? ORDER BY month, position_name", (bid,))
    cif       = query_db("SELECT * FROM budget_cif       WHERE budget_id=? ORDER BY month, concept",       (bid,))
    debt      = query_db("SELECT * FROM budget_debt_service WHERE budget_id=? ORDER BY concept, month",    (bid,))
    cashflow  = query_db("SELECT * FROM budget_cashflow  WHERE budget_id=? ORDER BY month",                (bid,))
    products  = query_db("SELECT id, code, name FROM products_services WHERE company_id=? AND is_active=1 ORDER BY name", (company_id,))
    employees = query_db("SELECT id, code, full_name, labor_type, cost_per_hour FROM employees WHERE company_id=? AND is_active=1 ORDER BY full_name", (company_id,))

    return render_template('budgets/detail.html',
                           budget=budget, summary=summary,
                           sales=sales, prod=prod, labor=labor,
                           cif=cif, debt=debt, cashflow=cashflow,
                           products=products, employees=employees,
                           months=list(range(1, 13)))


# ── Ventas ─────────────────────────────────────────────────────────────────

@budgets_bp.route('/budgets/<int:bid>/sales/add', methods=['POST'])
@login_required
@company_required
@module_required('budgets', write=True)
def add_sale(bid):
    d = request.form
    qty   = float(d.get('quantity', 0))
    price = float(d.get('unit_price', 0))
    execute_db(
        """INSERT INTO budget_sales
           (budget_id, product_id, product_name, month, quantity, unit_price, total_sales)
           VALUES (?,?,?,?,?,?,?)""",
        (bid, d.get('product_id') or None,
         d.get('product_name', ''), int(d.get('month', 1)),
         qty, price, qty * price)
    )
    flash('Venta presupuestada agregada', 'success')
    return redirect(url_for('budgets.detail', bid=bid) + '#ventas')


@budgets_bp.route('/budgets/<int:bid>/sales/<int:sid>/delete', methods=['POST'])
@login_required
@company_required
@module_required('budgets', write=True)
def delete_sale(bid, sid):
    execute_db("DELETE FROM budget_sales WHERE id=? AND budget_id=?", (sid, bid))
    return redirect(url_for('budgets.detail', bid=bid) + '#ventas')


# ── Producción ─────────────────────────────────────────────────────────────

@budgets_bp.route('/budgets/<int:bid>/production/add', methods=['POST'])
@login_required
@company_required
@module_required('budgets', write=True)
def add_production(bid):
    d = request.form
    sales_u  = float(d.get('sales_units', 0))
    end_inv  = float(d.get('ending_inventory', 0))
    beg_inv  = float(d.get('beginning_inventory', 0))
    req_prod = sales_u + end_inv - beg_inv
    execute_db(
        """INSERT INTO budget_production
           (budget_id, product_id, product_name, month,
            sales_units, ending_inventory, beginning_inventory, required_production)
           VALUES (?,?,?,?,?,?,?,?)""",
        (bid, d.get('product_id') or None,
         d.get('product_name', ''), int(d.get('month', 1)),
         sales_u, end_inv, beg_inv, req_prod)
    )
    flash('Producción requerida calculada', 'success')
    return redirect(url_for('budgets.detail', bid=bid) + '#produccion')


@budgets_bp.route('/budgets/<int:bid>/production/<int:pid>/delete', methods=['POST'])
@login_required
@company_required
@module_required('budgets', write=True)
def delete_production(bid, pid):
    execute_db("DELETE FROM budget_production WHERE id=? AND budget_id=?", (pid, bid))
    return redirect(url_for('budgets.detail', bid=bid) + '#produccion')


# ── Mano de obra ───────────────────────────────────────────────────────────

@budgets_bp.route('/budgets/<int:bid>/labor/add', methods=['POST'])
@login_required
@company_required
@module_required('budgets', write=True)
def add_labor(bid):
    d = request.form
    hours = float(d.get('hours_required', 0))
    rate  = float(d.get('cost_per_hour', 0))
    execute_db(
        """INSERT INTO budget_labor
           (budget_id, employee_id, position_name, labor_type, month,
            hours_required, cost_per_hour, total_cost)
           VALUES (?,?,?,?,?,?,?,?)""",
        (bid, d.get('employee_id') or None,
         d.get('position_name', ''), d.get('labor_type', 'MOD'),
         int(d.get('month', 1)), hours, rate, hours * rate)
    )
    flash('MOD presupuestada agregada', 'success')
    return redirect(url_for('budgets.detail', bid=bid) + '#labor')


@budgets_bp.route('/budgets/<int:bid>/labor/<int:lid>/delete', methods=['POST'])
@login_required
@company_required
@module_required('budgets', write=True)
def delete_labor(bid, lid):
    execute_db("DELETE FROM budget_labor WHERE id=? AND budget_id=?", (lid, bid))
    return redirect(url_for('budgets.detail', bid=bid) + '#labor')


# ── CIF ────────────────────────────────────────────────────────────────────

@budgets_bp.route('/budgets/<int:bid>/cif/add', methods=['POST'])
@login_required
@company_required
@module_required('budgets', write=True)
def add_cif(bid):
    d = request.form
    execute_db(
        """INSERT INTO budget_cif
           (budget_id, concept, cif_type, month, amount)
           VALUES (?,?,?,?,?)""",
        (bid, d.get('concept', ''), d.get('cif_type', 'fijo'),
         int(d.get('month', 1)), float(d.get('amount', 0)))
    )
    flash('CIF presupuestado agregado', 'success')
    return redirect(url_for('budgets.detail', bid=bid) + '#cif')


@budgets_bp.route('/budgets/<int:bid>/cif/<int:cid>/delete', methods=['POST'])
@login_required
@company_required
@module_required('budgets', write=True)
def delete_cif(bid, cid):
    execute_db("DELETE FROM budget_cif WHERE id=? AND budget_id=?", (cid, bid))
    return redirect(url_for('budgets.detail', bid=bid) + '#cif')


# ── Deuda / Inversión ──────────────────────────────────────────────────────

@budgets_bp.route('/budgets/<int:bid>/debt/add', methods=['POST'])
@login_required
@company_required
@module_required('budgets', write=True)
def add_debt(bid):
    d = request.form
    rows = calculate_debt_service(
        bid,
        concept      = d.get('concept', 'Préstamo'),
        loan_amount  = float(d.get('loan_amount', 0)),
        annual_rate  = float(d.get('annual_rate', 0)) / 100,
        months       = int(d.get('months', 12))
    )
    flash(f'Tabla de amortización generada ({len(rows)} cuotas)', 'success')
    return redirect(url_for('budgets.detail', bid=bid) + '#deuda')


@budgets_bp.route('/budgets/<int:bid>/debt/<string:concept>/delete', methods=['POST'])
@login_required
@company_required
@module_required('budgets', write=True)
def delete_debt(bid, concept):
    execute_db("DELETE FROM budget_debt_service WHERE budget_id=? AND concept=?",
               (bid, concept))
    return redirect(url_for('budgets.detail', bid=bid) + '#deuda')


# ── Flujo de caja ──────────────────────────────────────────────────────────

@budgets_bp.route('/budgets/<int:bid>/cashflow/generate', methods=['POST'])
@login_required
@company_required
@module_required('budgets', write=True)
def generate_cashflow(bid):
    rows = calculate_cashflow(bid)
    return jsonify({'success': True, 'months': len(rows),
                    'redirect': url_for('budgets.detail', bid=bid) + '#flujo'})


# ── Eliminar presupuesto ───────────────────────────────────────────────────

@budgets_bp.route('/budgets/<int:bid>/delete', methods=['POST'])
@login_required
@company_required
@module_required('budgets', write=True)
def delete(bid):
    execute_db("DELETE FROM budgets WHERE id=? AND company_id=?",
               (bid, session['company_id']))
    flash('Presupuesto eliminado', 'success')
    return redirect(url_for('budgets.index'))
