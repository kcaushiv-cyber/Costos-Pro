from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, flash
from models.database import query_db, execute_db
from routes.dashboard import login_required, company_required, module_required

activity_centers_bp = Blueprint('activity_centers', __name__)

CENTER_TYPES = [
    ('estrategico', 'Estratégico (dirección, gerencia)'),
    ('operativo',   'Operativo (producción, operaciones)'),
    ('apoyo',       'Apoyo (RRHH, contabilidad, IT)'),
]


@activity_centers_bp.route('/activity-centers')
@login_required
@company_required
@module_required('activity_centers', write=False)
def index():
    session['active_module'] = 'activity_centers'
    company_id = session['company_id']
    period_id  = session.get('period_id')

    centers = query_db(
        """SELECT ac.*,
                  (SELECT COUNT(*) FROM activities a WHERE a.center_id = ac.id) as activity_count
           FROM activity_centers ac
           WHERE ac.company_id=? AND (ac.period_id=? OR ac.period_id IS NULL)
           ORDER BY ac.center_type, ac.name""",
        (company_id, period_id)
    )
    total = sum(c['total_cost_monthly'] or 0 for c in centers)
    return render_template('activity_centers/index.html',
                           centers=centers, total=total,
                           center_types=CENTER_TYPES)


@activity_centers_bp.route('/activity-centers/new', methods=['GET', 'POST'])
@login_required
@company_required
@module_required('activity_centers', write=True)
def new():
    company_id = session['company_id']
    period_id  = session.get('period_id')

    if request.method == 'POST':
        d = request.form
        try:
            execute_db(
                """INSERT INTO activity_centers
                   (company_id, period_id, code, name, center_type, total_cost_monthly, total_cost_annual, notes)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (company_id, period_id,
                 d['code'], d['name'],
                 d.get('center_type', 'operativo'),
                 float(d.get('total_cost_monthly') or 0),
                 float(d.get('total_cost_annual') or 0),
                 d.get('notes'))
            )
            flash('Centro de actividad creado', 'success')
            return redirect(url_for('activity_centers.index'))
        except Exception:
            flash('El código ya existe en este período', 'error')

    return render_template('activity_centers/new.html', center_types=CENTER_TYPES)


@activity_centers_bp.route('/activity-centers/<int:cid>/edit', methods=['GET', 'POST'])
@login_required
@company_required
@module_required('activity_centers', write=True)
def edit(cid):
    company_id = session['company_id']
    center = query_db("SELECT * FROM activity_centers WHERE id=? AND company_id=?",
                      (cid, company_id), one=True)
    if not center:
        return redirect(url_for('activity_centers.index'))

    if request.method == 'POST':
        d = request.form
        execute_db(
            """UPDATE activity_centers
               SET code=?, name=?, center_type=?, total_cost_monthly=?, total_cost_annual=?, notes=?
               WHERE id=?""",
            (d['code'], d['name'], d.get('center_type'),
             float(d.get('total_cost_monthly') or 0),
             float(d.get('total_cost_annual') or 0),
             d.get('notes'), cid)
        )
        flash('Centro actualizado', 'success')
        return redirect(url_for('activity_centers.index'))

    activities = query_db("SELECT * FROM activities WHERE center_id=? ORDER BY name", (cid,))
    return render_template('activity_centers/edit.html',
                           center=center, activities=activities,
                           center_types=CENTER_TYPES)


@activity_centers_bp.route('/activity-centers/<int:cid>/delete', methods=['POST'])
@login_required
@company_required
@module_required('activity_centers', write=True)
def delete(cid):
    acts = query_db("SELECT COUNT(*) as n FROM activities WHERE center_id=?", (cid,), one=True)
    if acts and acts['n'] > 0:
        flash('No se puede eliminar: tiene actividades asignadas', 'error')
    else:
        execute_db("DELETE FROM activity_centers WHERE id=? AND company_id=?",
                   (cid, session['company_id']))
        flash('Centro eliminado', 'success')
    return redirect(url_for('activity_centers.index'))


@activity_centers_bp.route('/activity-centers/api/list')
@login_required
@company_required
@module_required('activity_centers', write=False)
def api_list():
    company_id = session['company_id']
    period_id  = session.get('period_id')
    rows = query_db(
        "SELECT id, code, name, center_type FROM activity_centers WHERE company_id=? AND (period_id=? OR period_id IS NULL) ORDER BY name",
        (company_id, period_id)
    )
    return jsonify([dict(r) for r in rows])
