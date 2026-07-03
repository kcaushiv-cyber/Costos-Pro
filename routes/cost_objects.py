from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, flash
from models.database import query_db, execute_db
from routes.dashboard import login_required, company_required

cost_objects_bp = Blueprint('cost_objects', __name__)


@cost_objects_bp.route('/cost-objects')
@login_required
@company_required
def index():
    session['active_module'] = 'cost_objects'
    company_id = session['company_id']
    period_id  = session.get('period_id')

    latest_model = query_db(
        """SELECT id
           FROM abc_models
           WHERE company_id=? AND period_id=? AND status IN ('calculado', 'aprobado')
           ORDER BY COALESCE(calculated_at, created_at) DESC, id DESC
           LIMIT 1""",
        (company_id, period_id), one=True
    )
    latest_model_id = latest_model['id'] if latest_model else 0

    objects = query_db(
        """SELECT co.*, ps.name as product_name,
                  ar.unit_cost_abc as abc_unit_cost_latest,
                  ar.unit_cost_traditional as trad_unit_cost_latest,
                  ar.total_cost as abc_total_cost_latest
           FROM cost_objects co
           LEFT JOIN products_services ps ON co.product_id = ps.id
           LEFT JOIN abc_results ar
                  ON ar.cost_object_id = co.id
                 AND ar.abc_model_id = ?
           WHERE co.company_id=? AND (co.period_id=? OR co.period_id IS NULL)
           ORDER BY co.name""",
        (latest_model_id, company_id, period_id)
    )
    products = query_db(
        "SELECT id, code, name FROM products_services WHERE company_id=? AND is_active=1 ORDER BY name",
        (company_id,)
    )
    return render_template('cost_objects/index.html',
                           objects=objects, products=products)


@cost_objects_bp.route('/cost-objects/new', methods=['GET', 'POST'])
@login_required
@company_required
def new():
    company_id = session['company_id']
    period_id  = session.get('period_id')

    if request.method == 'POST':
        d = request.form
        try:
            execute_db(
                """INSERT INTO cost_objects
                   (company_id, period_id, code, name, product_id, quantity_month,
                    unit_cost_traditional, notes)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (company_id, period_id,
                 d['code'], d['name'],
                 d.get('product_id') or None,
                 float(d.get('quantity_month', 0)),
                 float(d.get('unit_cost_traditional', 0)),
                 d.get('notes'))
            )
            flash('Objeto de costo creado', 'success')
            return redirect(url_for('cost_objects.index'))
        except Exception:
            flash('El código ya existe en este período', 'error')

    products = query_db(
        "SELECT id, code, name FROM products_services WHERE company_id=? AND is_active=1 ORDER BY name",
        (company_id,)
    )
    return render_template('cost_objects/new.html', products=products)


@cost_objects_bp.route('/cost-objects/<int:oid>/edit', methods=['GET', 'POST'])
@login_required
@company_required
def edit(oid):
    company_id = session['company_id']
    obj = query_db("SELECT * FROM cost_objects WHERE id=? AND company_id=?",
                   (oid, company_id), one=True)
    if not obj:
        return redirect(url_for('cost_objects.index'))

    if request.method == 'POST':
        d = request.form
        execute_db(
            """UPDATE cost_objects SET code=?, name=?, product_id=?, quantity_month=?,
               unit_cost_traditional=?, notes=? WHERE id=?""",
            (d['code'], d['name'], d.get('product_id') or None,
             float(d.get('quantity_month', 0)),
             float(d.get('unit_cost_traditional', 0)),
             d.get('notes'), oid)
        )
        flash('Objeto de costo actualizado', 'success')
        return redirect(url_for('cost_objects.index'))

    products = query_db(
        "SELECT id, code, name FROM products_services WHERE company_id=? AND is_active=1 ORDER BY name",
        (company_id,)
    )
    return render_template('cost_objects/edit.html', obj=obj, products=products)


@cost_objects_bp.route('/cost-objects/<int:oid>/delete', methods=['POST'])
@login_required
@company_required
def delete(oid):
    execute_db("DELETE FROM cost_objects WHERE id=? AND company_id=?",
               (oid, session['company_id']))
    flash('Objeto de costo eliminado', 'success')
    return redirect(url_for('cost_objects.index'))


@cost_objects_bp.route('/cost-objects/api/list')
@login_required
@company_required
def api_list():
    company_id = session['company_id']
    period_id  = session.get('period_id')
    rows = query_db(
        """SELECT co.id, co.code, co.name, co.quantity_month, ps.name as product_name
           FROM cost_objects co LEFT JOIN products_services ps ON co.product_id=ps.id
           WHERE co.company_id=? AND (co.period_id=? OR co.period_id IS NULL)
           ORDER BY co.name""",
        (company_id, period_id)
    )
    return jsonify([dict(r) for r in rows])
