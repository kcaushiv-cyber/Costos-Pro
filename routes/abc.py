from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, flash
from models.database import query_db, execute_db
from routes.dashboard import login_required, company_required
from services.abc_service import (
    calculate_abc_results, get_model_summary,
    save_resource_allocation, save_center_allocation, save_object_allocation,
    distribute_resources_to_centers, distribute_centers_to_activities,
    recalculate_model_allocations,
    delete_resource_allocation, delete_center_allocation, delete_object_allocation
)

abc_bp = Blueprint('abc', __name__)


@abc_bp.route('/abc')
@login_required
@company_required
def index():
    session['active_module'] = 'abc'
    company_id = session['company_id']
    period_id  = session.get('period_id')

    models = query_db(
        """SELECT m.*, COUNT(DISTINCT ara.resource_id) as res_count,
                  COUNT(DISTINCT ar.id) as result_count
           FROM abc_models m
           LEFT JOIN abc_resource_allocations ara ON ara.abc_model_id = m.id
           LEFT JOIN abc_results ar ON ar.abc_model_id = m.id
           WHERE m.company_id=? AND m.period_id=?
           GROUP BY m.id
           ORDER BY m.created_at DESC""",
        (company_id, period_id)
    )
    return render_template('abc/index.html', models=models)


@abc_bp.route('/abc/new', methods=['GET', 'POST'])
@login_required
@company_required
def new():
    company_id = session['company_id']
    period_id  = session.get('period_id')

    if request.method == 'POST':
        d = request.form
        mid = execute_db(
            """INSERT INTO abc_models
               (company_id, period_id, name, sector,
                admin_expense, sales_expense, financial_expense, desired_margin, image_path)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (company_id, period_id,
             d['name'], d.get('sector', session.get('sector', '')),
             float(d.get('admin_expense', 0)),
             float(d.get('sales_expense', 0)),
             float(d.get('financial_expense', 0)),
             float(d.get('desired_margin', 0)),
             d.get('image_path') or None)
        )
        flash('Modelo ABC creado. Ahora asigna los inductores.', 'success')
        return redirect(url_for('abc.step1_resources', mid=mid))

    return render_template('abc/new.html')


# ── PASO 1: Recursos → Centros ─────────────────────────────────────────────

@abc_bp.route('/abc/<int:mid>/step1', methods=['GET', 'POST'])
@login_required
@company_required
def step1_resources(mid):
    company_id = session['company_id']
    period_id  = session.get('period_id')
    model = _get_model(mid, company_id)
    if not model:
        return redirect(url_for('abc.index'))

    if request.method == 'POST':
        data = request.get_json()
        if data:
            for item in data.get('allocations', []):
                save_resource_allocation(mid,
                                         item['resource_id'],
                                         item['center_id'],
                                         item['driver_qty'])
        recalculate_model_allocations(mid)
        return jsonify({'success': True})

    resources = query_db(
        "SELECT * FROM resources WHERE company_id=? AND (period_id=? OR period_id IS NULL) ORDER BY category, name",
        (company_id, period_id)
    )
    centers = query_db(
        "SELECT * FROM activity_centers WHERE company_id=? AND (period_id=? OR period_id IS NULL) ORDER BY name",
        (company_id, period_id)
    )
    existing = query_db(
        """SELECT ara.*, r.name as res_name, ac.name as center_name
           FROM abc_resource_allocations ara
           JOIN resources r ON ara.resource_id=r.id
           JOIN activity_centers ac ON ara.center_id=ac.id
           WHERE ara.abc_model_id=?""",
        (mid,)
    )
    summary = get_model_summary(mid)

    return render_template('abc/step1_resources.html',
                           model=model, resources=resources,
                           centers=centers, existing=existing,
                           summary=summary)


# ── PASO 2: Centros → Actividades ──────────────────────────────────────────

@abc_bp.route('/abc/<int:mid>/step2', methods=['GET', 'POST'])
@login_required
@company_required
def step2_centers(mid):
    company_id = session['company_id']
    period_id  = session.get('period_id')
    model = _get_model(mid, company_id)
    if not model:
        return redirect(url_for('abc.index'))

    if request.method == 'POST':
        data = request.get_json()
        if data:
            for item in data.get('allocations', []):
                save_center_allocation(mid,
                                       item['center_id'],
                                       item['activity_id'],
                                       item['driver_qty'])
        recalculate_model_allocations(mid)
        return jsonify({'success': True})

    centers = query_db(
        "SELECT * FROM activity_centers WHERE company_id=? AND (period_id=? OR period_id IS NULL) ORDER BY name",
        (company_id, period_id)
    )
    activities = query_db(
        """SELECT a.*, ac.name as center_name
           FROM activities a
           JOIN activity_centers ac ON a.center_id=ac.id
           WHERE ac.company_id=? AND (ac.period_id=? OR ac.period_id IS NULL)
           ORDER BY ac.name, a.name""",
        (company_id, period_id)
    )
    existing = query_db(
        """SELECT aca.*, ac.name as center_name, a.name as act_name
           FROM abc_center_allocations aca
           JOIN activity_centers ac ON aca.center_id=ac.id
           JOIN activities a ON aca.activity_id=a.id
           WHERE aca.abc_model_id=?""",
        (mid,)
    )
    summary = get_model_summary(mid)

    return render_template('abc/step2_centers.html',
                           model=model, centers=centers,
                           activities=activities, existing=existing,
                           summary=summary)


# ── PASO 3: Actividades → Objetos de Costo ────────────────────────────────

@abc_bp.route('/abc/<int:mid>/step3', methods=['GET', 'POST'])
@login_required
@company_required
def step3_objects(mid):
    company_id = session['company_id']
    period_id  = session.get('period_id')
    model = _get_model(mid, company_id)
    if not model:
        return redirect(url_for('abc.index'))

    if request.method == 'POST':
        data = request.get_json()
        if data:
            for item in data.get('allocations', []):
                save_object_allocation(mid,
                                       item['activity_id'],
                                       item['object_id'],
                                       item['driver_qty'])
        recalculate_model_allocations(mid)
        return jsonify({'success': True})

    activities = query_db(
        """SELECT a.*, ac.name as center_name
           FROM activities a
           JOIN activity_centers ac ON a.center_id=ac.id
           WHERE ac.company_id=? AND (ac.period_id=? OR ac.period_id IS NULL)
           ORDER BY ac.name, a.name""",
        (company_id, period_id)
    )
    objects = query_db(
        "SELECT * FROM cost_objects WHERE company_id=? AND (period_id=? OR period_id IS NULL) ORDER BY name",
        (company_id, period_id)
    )
    existing = query_db(
        """SELECT aoa.*, a.name as act_name, co.name as obj_name
           FROM abc_object_allocations aoa
           JOIN activities a ON aoa.activity_id=a.id
           JOIN cost_objects co ON aoa.cost_object_id=co.id
           WHERE aoa.abc_model_id=?""",
        (mid,)
    )
    summary = get_model_summary(mid)

    return render_template('abc/step3_objects.html',
                           model=model, activities=activities,
                           objects=objects, existing=existing,
                           summary=summary)


# ── Eliminar asignaciones ABC ───────────────────────────────────────────────

@abc_bp.route('/abc/<int:mid>/step1/allocations/<int:allocation_id>/delete', methods=['POST'])
@login_required
@company_required
def delete_step1_allocation(mid, allocation_id):
    model = _get_model(mid, session['company_id'])
    if not model:
        return redirect(url_for('abc.index'))
    if delete_resource_allocation(mid, allocation_id):
        flash('Asignación eliminada', 'success')
    else:
        flash('Asignación no encontrada', 'error')
    return redirect(url_for('abc.step1_resources', mid=mid))


@abc_bp.route('/abc/<int:mid>/step2/allocations/<int:allocation_id>/delete', methods=['POST'])
@login_required
@company_required
def delete_step2_allocation(mid, allocation_id):
    model = _get_model(mid, session['company_id'])
    if not model:
        return redirect(url_for('abc.index'))
    if delete_center_allocation(mid, allocation_id):
        flash('Asignación eliminada', 'success')
    else:
        flash('Asignación no encontrada', 'error')
    return redirect(url_for('abc.step2_centers', mid=mid))


@abc_bp.route('/abc/<int:mid>/step3/allocations/<int:allocation_id>/delete', methods=['POST'])
@login_required
@company_required
def delete_step3_allocation(mid, allocation_id):
    model = _get_model(mid, session['company_id'])
    if not model:
        return redirect(url_for('abc.index'))
    if delete_object_allocation(mid, allocation_id):
        flash('Asignación eliminada', 'success')
    else:
        flash('Asignación no encontrada', 'error')
    return redirect(url_for('abc.step3_objects', mid=mid))


# ── PASO 4: Resultados finales ─────────────────────────────────────────────

@abc_bp.route('/abc/<int:mid>/results')
@login_required
@company_required
def results(mid):
    company_id = session['company_id']
    model = _get_model(mid, company_id)
    if not model:
        return redirect(url_for('abc.index'))

    results_data = query_db(
        """SELECT ar.*, co.name as obj_name, co.quantity_month,
                  co.code as obj_code
           FROM abc_results ar
           JOIN cost_objects co ON ar.cost_object_id = co.id
           WHERE ar.abc_model_id=?
           ORDER BY co.name""",
        (mid,)
    )

    # Totales para el resumen
    total_prod = sum(float(r['production_cost'] or 0) for r in results_data)
    total_cost = sum(float(r['total_cost'] or 0) for r in results_data)
    total_sale = sum(float(r['sale_price'] or 0) for r in results_data)

    return render_template('abc/results.html',
                           model=model,
                           results=results_data,
                           total_prod=total_prod,
                           total_cost=total_cost,
                           total_sale=total_sale)


@abc_bp.route('/abc/<int:mid>/calculate', methods=['POST'])
@login_required
@company_required
def calculate(mid):
    company_id = session['company_id']
    model = _get_model(mid, company_id)
    if not model:
        return jsonify({'success': False, 'error': 'Modelo no encontrado'}), 404

    try:
        results_data = calculate_abc_results(mid)
        return jsonify({
            'success': True,
            'count': len(results_data),
            'redirect': url_for('abc.results', mid=mid)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@abc_bp.route('/abc/<int:mid>/edit-params', methods=['POST'])
@login_required
@company_required
def edit_params(mid):
    d = request.form
    execute_db(
        "UPDATE abc_models SET name=?, admin_expense=?, sales_expense=?, financial_expense=?, desired_margin=? WHERE id=?",
        (d['name'],
         float(d.get('admin_expense', 0)),
         float(d.get('sales_expense', 0)),
         float(d.get('financial_expense', 0)),
         float(d.get('desired_margin', 0)),
         mid)
    )
    flash('Parámetros actualizados', 'success')
    return redirect(request.referrer or url_for('abc.index'))


@abc_bp.route('/abc/<int:mid>/delete', methods=['POST'])
@login_required
@company_required
def delete(mid):
    execute_db("DELETE FROM abc_models WHERE id=? AND company_id=?",
               (mid, session['company_id']))
    flash('Modelo ABC eliminado', 'success')
    return redirect(url_for('abc.index'))


def _get_model(mid, company_id):
    return query_db("SELECT * FROM abc_models WHERE id=? AND company_id=?",
                    (mid, company_id), one=True)
