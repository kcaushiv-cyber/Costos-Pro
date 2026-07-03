from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, flash
from models.database import query_db, execute_db
from routes.dashboard import login_required, company_required

resources_bp = Blueprint('resources', __name__)

CATEGORIES = [
    ('energia',       'Energía (luz, agua, gas)'),
    ('personal',      'Personal / Nómina'),
    ('depreciacion',  'Depreciación activos'),
    ('materiales',    'Materiales indirectos'),
    ('servicios',     'Servicios externos'),
    ('mantenimiento', 'Mantenimiento'),
    ('seguros',       'Seguros y licencias'),
    ('otros',         'Otros gastos'),
]


@resources_bp.route('/resources')
@login_required
@company_required
def index():
    session['active_module'] = 'resources'
    company_id = session['company_id']
    period_id  = session.get('period_id')

    resources = query_db(
        """SELECT * FROM resources
           WHERE company_id=? AND (period_id=? OR period_id IS NULL)
           ORDER BY category, name""",
        (company_id, period_id)
    )

    total = sum(r['monthly_amount'] or 0 for r in resources)
    by_cat = {}
    for r in resources:
        c = r['category'] or 'otros'
        by_cat[c] = by_cat.get(c, 0) + (r['monthly_amount'] or 0)

    return render_template('resources/index.html',
                           resources=resources,
                           total=total,
                           by_cat=by_cat,
                           categories=CATEGORIES)


@resources_bp.route('/resources/new', methods=['GET', 'POST'])
@login_required
@company_required
def new():
    company_id = session['company_id']
    period_id  = session.get('period_id')

    if request.method == 'POST':
        d = request.form
        monthly = float(d.get('monthly_amount', 0))
        annual  = monthly * 12
        try:
            execute_db(
                """INSERT INTO resources
                   (company_id, period_id, code, name, category,
                    monthly_amount, annual_amount, driver_type, notes)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (company_id, period_id,
                 d['code'], d['name'], d.get('category', 'otros'),
                 monthly, annual,
                 d.get('driver_type'), d.get('notes'))
            )
            flash('Recurso registrado', 'success')
            return redirect(url_for('resources.index'))
        except Exception:
            flash('El código ya existe en este período', 'error')

    return render_template('resources/new.html', categories=CATEGORIES)


@resources_bp.route('/resources/<int:rid>/edit', methods=['GET', 'POST'])
@login_required
@company_required
def edit(rid):
    company_id = session['company_id']
    res = query_db("SELECT * FROM resources WHERE id=? AND company_id=?",
                   (rid, company_id), one=True)
    if not res:
        return redirect(url_for('resources.index'))

    if request.method == 'POST':
        d = request.form
        monthly = float(d.get('monthly_amount', 0))
        execute_db(
            """UPDATE resources SET code=?, name=?, category=?,
               monthly_amount=?, annual_amount=?, driver_type=?, notes=?
               WHERE id=?""",
            (d['code'], d['name'], d.get('category'),
             monthly, monthly * 12,
             d.get('driver_type'), d.get('notes'), rid)
        )
        flash('Recurso actualizado', 'success')
        return redirect(url_for('resources.index'))

    return render_template('resources/edit.html', resource=res, categories=CATEGORIES)


@resources_bp.route('/resources/<int:rid>/delete', methods=['POST'])
@login_required
@company_required
def delete(rid):
    # Borrar primero las asignaciones ABC que referencian este recurso
    execute_db("DELETE FROM abc_resource_allocations WHERE resource_id=?", (rid,))
    execute_db("DELETE FROM resources WHERE id=? AND company_id=?",
               (rid, session['company_id']))
    flash('Recurso eliminado', 'success')
    return redirect(url_for('resources.index'))


@resources_bp.route('/resources/api/list')
@login_required
@company_required
def api_list():
    company_id = session['company_id']
    period_id  = session.get('period_id')
    rows = query_db(
        "SELECT id, code, name, monthly_amount, driver_type FROM resources WHERE company_id=? AND (period_id=? OR period_id IS NULL) ORDER BY name",
        (company_id, period_id)
    )
    return jsonify([dict(r) for r in rows])
