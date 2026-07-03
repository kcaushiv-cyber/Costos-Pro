from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, flash
from models.database import query_db, execute_db
from routes.dashboard import login_required, company_required, module_required
from services.process_cost_service import calculate_model, get_model_with_departments

process_costs_bp = Blueprint('process_costs', __name__)

MODEL_TYPES = [
    ('normal',    'Normal',             'Sin pérdidas ni unidades agregadas'),
    ('agregadas', 'Unidades Agregadas', 'Con UAg: unidades incorporadas en el proceso'),
    ('perdidas',  'Unidades Perdidas',  'Con UP: merma o desperdicio normal'),
    ('protecho',  'PROTECHO',           'Con UTNT: terminadas no transferidas al cierre'),
]


@process_costs_bp.route('/process-costs')
@login_required
@company_required
@module_required('process_costs', write=False)
def index():
    session['active_module'] = 'process_costs'
    company_id = session['company_id']
    period_id  = session.get('period_id')

    models = query_db(
        """SELECT m.*,
                  (SELECT COUNT(*) FROM process_departments pd WHERE pd.model_id = m.id) as dept_count
           FROM process_cost_models m
           WHERE m.company_id=? AND m.period_id=?
           ORDER BY m.created_at DESC""",
        (company_id, period_id)
    )
    return render_template('process_costs/index.html',
                           models=models, model_types=MODEL_TYPES)


@process_costs_bp.route('/process-costs/new', methods=['GET', 'POST'])
@login_required
@company_required
@module_required('process_costs', write=True)
def new():
    company_id = session['company_id']
    period_id  = session.get('period_id')

    if request.method == 'POST':
        d = request.form
        mid = execute_db(
            """INSERT INTO process_cost_models
               (company_id, period_id, name, model_type, product_name)
               VALUES (?,?,?,?,?)""",
            (company_id, period_id,
             d['name'], d['model_type'], d.get('product_name'))
        )
        flash('Modelo creado. Ahora define los departamentos.', 'success')
        return redirect(url_for('process_costs.edit', mid=mid))

    return render_template('process_costs/new.html', model_types=MODEL_TYPES)


@process_costs_bp.route('/process-costs/<int:mid>', methods=['GET'])
@login_required
@company_required
@module_required('process_costs', write=False)
def edit(mid):
    company_id = session['company_id']
    data = get_model_with_departments(mid)
    if not data or data['model']['company_id'] != company_id:
        return redirect(url_for('process_costs.index'))

    return render_template('process_costs/edit.html',
                           model=data['model'],
                           departments=data['departments'],
                           model_types=MODEL_TYPES)


@process_costs_bp.route('/process-costs/<int:mid>/dept/new', methods=['POST'])
@login_required
@company_required
@module_required('process_costs', write=True)
def new_dept(mid):
    d = request.form
    # Calcular el siguiente orden
    last = query_db(
        "SELECT MAX(dept_order) as mx FROM process_departments WHERE model_id=?",
        (mid,), one=True
    )
    order = (last['mx'] or 0) + 1

    execute_db(
        """INSERT INTO process_departments
           (model_id, dept_order, name,
            uiipp, uprod, uag, utt, utnt, uifpp, up,
            mat_pct_uiipp, conv_pct_uiipp, mat_pct_uifpp, conv_pct_uifpp,
            cost_mat_prior, cost_conv_prior, cost_transfer_in,
            cost_mat_current, cost_mod_current, cost_cif_current)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (mid, order, d.get('name', f'Departamento {order}'),
         float(d.get('uiipp', 0)),  float(d.get('uprod', 0)),
         float(d.get('uag', 0)),    float(d.get('utt', 0)),
         float(d.get('utnt', 0)),   float(d.get('uifpp', 0)),
         float(d.get('up', 0)),
         float(d.get('mat_pct_uiipp', 0)),  float(d.get('conv_pct_uiipp', 0)),
         float(d.get('mat_pct_uifpp', 0)),  float(d.get('conv_pct_uifpp', 0)),
         float(d.get('cost_mat_prior', 0)), float(d.get('cost_conv_prior', 0)),
         float(d.get('cost_transfer_in', 0)),
         float(d.get('cost_mat_current', 0)),
         float(d.get('cost_mod_current', 0)),
         float(d.get('cost_cif_current', 0)))
    )
    flash('Departamento agregado', 'success')
    return redirect(url_for('process_costs.edit', mid=mid))


@process_costs_bp.route('/process-costs/<int:mid>/dept/<int:did>/update', methods=['POST'])
@login_required
@company_required
@module_required('process_costs', write=True)
def update_dept(mid, did):
    d = request.form
    execute_db(
        """UPDATE process_departments SET
           name=?,
           uiipp=?, uprod=?, uag=?, utt=?, utnt=?, uifpp=?, up=?,
           mat_pct_uiipp=?, conv_pct_uiipp=?,
           mat_pct_uifpp=?, conv_pct_uifpp=?,
           cost_mat_prior=?, cost_conv_prior=?, cost_transfer_in=?,
           cost_mat_current=?, cost_mod_current=?, cost_cif_current=?
           WHERE id=? AND model_id=?""",
        (d.get('name'),
         float(d.get('uiipp', 0)),  float(d.get('uprod', 0)),
         float(d.get('uag', 0)),    float(d.get('utt', 0)),
         float(d.get('utnt', 0)),   float(d.get('uifpp', 0)),
         float(d.get('up', 0)),
         float(d.get('mat_pct_uiipp', 0)),  float(d.get('conv_pct_uiipp', 0)),
         float(d.get('mat_pct_uifpp', 0)),  float(d.get('conv_pct_uifpp', 0)),
         float(d.get('cost_mat_prior', 0)), float(d.get('cost_conv_prior', 0)),
         float(d.get('cost_transfer_in', 0)),
         float(d.get('cost_mat_current', 0)),
         float(d.get('cost_mod_current', 0)),
         float(d.get('cost_cif_current', 0)),
         did, mid)
    )
    flash('Departamento actualizado', 'success')
    return redirect(url_for('process_costs.edit', mid=mid))


@process_costs_bp.route('/process-costs/<int:mid>/dept/<int:did>/delete', methods=['POST'])
@login_required
@company_required
@module_required('process_costs', write=True)
def delete_dept(mid, did):
    execute_db("DELETE FROM process_departments WHERE id=? AND model_id=?", (did, mid))
    flash('Departamento eliminado', 'success')
    return redirect(url_for('process_costs.edit', mid=mid))


@process_costs_bp.route('/process-costs/<int:mid>/calculate', methods=['POST'])
@login_required
@company_required
@module_required('process_costs', write=True)
def calculate(mid):
    result = calculate_model(mid)
    if result['success']:
        return jsonify({
            'success': True,
            'redirect': url_for('process_costs.results', mid=mid)
        })
    return jsonify({'success': False, 'error': result.get('error', 'Error desconocido')}), 400


@process_costs_bp.route('/process-costs/<int:mid>/results')
@login_required
@company_required
@module_required('process_costs', write=False)
def results(mid):
    company_id = session['company_id']
    data = get_model_with_departments(mid)
    if not data or data['model']['company_id'] != company_id:
        return redirect(url_for('process_costs.index'))

    # Recalcular para mostrar resultados frescos
    calc = calculate_model(mid)

    return render_template('process_costs/results.html',
                           model=data['model'],
                           departments=data['departments'],
                           calc=calc)


@process_costs_bp.route('/process-costs/<int:mid>/delete', methods=['POST'])
@login_required
@company_required
@module_required('process_costs', write=True)
def delete(mid):
    execute_db("DELETE FROM process_cost_models WHERE id=? AND company_id=?",
               (mid, session['company_id']))
    flash('Modelo eliminado', 'success')
    return redirect(url_for('process_costs.index'))
