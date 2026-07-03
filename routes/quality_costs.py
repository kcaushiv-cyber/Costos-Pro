from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, flash
from models.database import query_db, execute_db
from routes.dashboard import login_required, company_required, module_required
from services.claude_service import classify_quality_cost

quality_costs_bp = Blueprint('quality_costs', __name__)

CATEGORIES = [
    ('prevencion',      'Prevención',      'Actividades para evitar defectos'),
    ('evaluacion',      'Evaluación',      'Inspección y medición de calidad'),
    ('falla_interna',   'Falla Interna',   'Defectos detectados antes de entregar'),
    ('falla_externa',   'Falla Externa',   'Defectos detectados por el cliente'),
]


@quality_costs_bp.route('/quality-costs')
@login_required
@company_required
@module_required('quality_costs', write=False)
def index():
    session['active_module'] = 'quality_costs'
    company_id = session['company_id']
    period_id  = session.get('period_id')

    costs = query_db(
        "SELECT * FROM quality_costs WHERE company_id=? AND period_id=? ORDER BY category, activity_name",
        (company_id, period_id)
    )

    # Totales por categoría
    totals = {c[0]: 0.0 for c in CATEGORIES}
    total_all = 0.0
    for c in costs:
        cat = c['category']
        if cat in totals:
            totals[cat] += float(c['monthly_cost'] or 0)
        total_all += float(c['monthly_cost'] or 0)

    # KPIs PAF
    prevention  = totals.get('prevencion', 0)
    evaluation  = totals.get('evaluacion', 0)
    int_failure = totals.get('falla_interna', 0)
    ext_failure = totals.get('falla_externa', 0)
    conformance = prevention + evaluation
    nonconform  = int_failure + ext_failure

    # % sobre ventas (del presupuesto activo si existe)
    budget = query_db(
        "SELECT total_sales FROM budgets WHERE company_id=? AND period_id=? LIMIT 1",
        (company_id, period_id), one=True
    )
    ventas = float(budget['total_sales'] or 0) if budget and budget['total_sales'] else 0

    return render_template('quality_costs/index.html',
                           costs=costs,
                           totals=totals,
                           total_all=total_all,
                           prevention=prevention,
                           evaluation=evaluation,
                           int_failure=int_failure,
                           ext_failure=ext_failure,
                           conformance=conformance,
                           nonconform=nonconform,
                           ventas=ventas,
                           categories=CATEGORIES)


@quality_costs_bp.route('/quality-costs/new', methods=['GET', 'POST'])
@login_required
@company_required
@module_required('quality_costs', write=True)
def new():
    company_id = session['company_id']
    period_id  = session.get('period_id')

    if request.method == 'POST':
        d = request.form
        monthly = float(d.get('monthly_cost', 0))
        execute_db(
            """INSERT INTO quality_costs
               (company_id, period_id, activity_name, description,
                category, responsible, monthly_cost, annual_cost, ai_classified)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (company_id, period_id,
             d['activity_name'], d.get('description'),
             d.get('category', 'prevencion'),
             d.get('responsible'),
             monthly, monthly * 12, 0)
        )
        flash('Actividad de calidad registrada', 'success')
        return redirect(url_for('quality_costs.index'))

    return render_template('quality_costs/new.html', categories=CATEGORIES)


@quality_costs_bp.route('/quality-costs/<int:qid>/edit', methods=['GET', 'POST'])
@login_required
@company_required
@module_required('quality_costs', write=True)
def edit(qid):
    company_id = session['company_id']
    cost = query_db("SELECT * FROM quality_costs WHERE id=? AND company_id=?",
                    (qid, company_id), one=True)
    if not cost:
        return redirect(url_for('quality_costs.index'))

    if request.method == 'POST':
        d = request.form
        monthly = float(d.get('monthly_cost', 0))
        execute_db(
            """UPDATE quality_costs SET
               activity_name=?, description=?, category=?,
               responsible=?, monthly_cost=?, annual_cost=?
               WHERE id=?""",
            (d['activity_name'], d.get('description'),
             d.get('category'), d.get('responsible'),
             monthly, monthly * 12, qid)
        )
        flash('Actualizado', 'success')
        return redirect(url_for('quality_costs.index'))

    return render_template('quality_costs/edit.html', cost=cost, categories=CATEGORIES)


@quality_costs_bp.route('/quality-costs/<int:qid>/delete', methods=['POST'])
@login_required
@company_required
@module_required('quality_costs', write=True)
def delete(qid):
    execute_db("DELETE FROM quality_costs WHERE id=? AND company_id=?",
               (qid, session['company_id']))
    flash('Actividad eliminada', 'success')
    return redirect(url_for('quality_costs.index'))


@quality_costs_bp.route('/quality-costs/api/classify', methods=['POST'])
@login_required
@module_required('quality_costs', write=True)
def api_classify():
    """Clasificar una actividad con IA y guardar el resultado."""
    data = request.get_json()
    name = data.get('activity_name', '').strip()
    desc = data.get('description', '')
    if not name:
        return jsonify({'success': False, 'error': 'Nombre requerido'}), 400

    result = classify_quality_cost(name, desc)
    if 'error' not in result:
        return jsonify({'success': True, 'data': result})
    return jsonify({'success': False, 'error': result['error']}), 200


@quality_costs_bp.route('/quality-costs/bulk-add', methods=['POST'])
@login_required
@company_required
@module_required('quality_costs', write=True)
def bulk_add():
    """Agrega múltiples actividades desde el asistente IA."""
    company_id = session['company_id']
    period_id  = session.get('period_id')
    data = request.get_json()
    activities = data.get('activities', [])
    count = 0
    for act in activities:
        monthly = float(act.get('monthly_cost', 0))
        execute_db(
            """INSERT INTO quality_costs
               (company_id, period_id, activity_name, description,
                category, responsible, monthly_cost, annual_cost, ai_classified)
               VALUES (?,?,?,?,?,?,?,?,1)""",
            (company_id, period_id,
             act.get('activity_name', ''), act.get('description', ''),
             act.get('category', 'prevencion'), act.get('responsible', ''),
             monthly, monthly * 12)
        )
        count += 1
    return jsonify({'success': True, 'count': count})
