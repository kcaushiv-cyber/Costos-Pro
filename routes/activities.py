from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, flash
from models.database import query_db, execute_db
from routes.dashboard import login_required, company_required, module_required

activities_bp = Blueprint('activities', __name__)

DRIVER_TYPES = [
    ('horas_maquina',   'Horas máquina'),
    ('horas_hombre',    'Horas hombre'),
    ('unidades_prod',   'Unidades producidas'),
    ('pedidos',         'Número de pedidos'),
    ('metros',          'Metros lineales/cuadrados'),
    ('km',              'Kilómetros recorridos'),
    ('kwh',             'Kw-h consumidos'),
    ('m3',              'M³ consumidos'),
    ('setup',           'Número de setups'),
    ('inspecciones',    'Número de inspecciones'),
    ('porcentaje',      'Porcentaje directo'),
    ('otro',            'Otro inductor'),
]


@activities_bp.route('/activities')
@login_required
@company_required
@module_required('activities', write=False)
def index():
    session['active_module'] = 'activities'
    company_id = session['company_id']
    period_id  = session.get('period_id')

    activities = query_db(
        """SELECT a.*, ac.name as center_name, ac.center_type
           FROM activities a
           JOIN activity_centers ac ON a.center_id = ac.id
           WHERE ac.company_id=? AND (ac.period_id=? OR ac.period_id IS NULL)
           ORDER BY ac.name, a.name""",
        (company_id, period_id)
    )
    centers = query_db(
        "SELECT id, name FROM activity_centers WHERE company_id=? AND (period_id=? OR period_id IS NULL) ORDER BY name",
        (company_id, period_id)
    )
    return render_template('activities/index.html',
                           activities=activities,
                           centers=centers,
                           driver_types=DRIVER_TYPES)


@activities_bp.route('/activities/new', methods=['GET', 'POST'])
@login_required
@company_required
@module_required('activities', write=True)
def new():
    company_id = session['company_id']
    period_id  = session.get('period_id')

    if request.method == 'POST':
        d = request.form
        try:
            execute_db(
                """INSERT INTO activities
                   (company_id, center_id, code, name, driver_type, driver_total, total_cost, notes)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (company_id,
                 d['center_id'], d['code'], d['name'],
                 d.get('driver_type'), float(d.get('driver_total') or 0),
                 float(d.get('total_cost') or 0),
                 d.get('notes'))
            )
            flash('Actividad creada', 'success')
            return redirect(url_for('activities.index'))
        except Exception:
            flash('El código ya existe', 'error')

    centers = query_db(
        "SELECT id, name FROM activity_centers WHERE company_id=? AND (period_id=? OR period_id IS NULL) ORDER BY name",
        (company_id, period_id)
    )
    return render_template('activities/new.html',
                           centers=centers, driver_types=DRIVER_TYPES)


@activities_bp.route('/activities/<int:aid>/edit', methods=['GET', 'POST'])
@login_required
@company_required
@module_required('activities', write=True)
def edit(aid):
    company_id = session['company_id']
    period_id  = session.get('period_id')
    activity = query_db(
        "SELECT a.*, ac.name as center_name FROM activities a JOIN activity_centers ac ON a.center_id=ac.id WHERE a.id=? AND ac.company_id=?",
        (aid, company_id), one=True
    )
    if not activity:
        return redirect(url_for('activities.index'))

    if request.method == 'POST':
        d = request.form
        execute_db(
            """UPDATE activities
               SET code=?, name=?, center_id=?, driver_type=?, driver_total=?, total_cost=?, notes=?
               WHERE id=?""",
            (d['code'], d['name'], d['center_id'],
             d.get('driver_type'), float(d.get('driver_total') or 0),
             float(d.get('total_cost') or 0),
             d.get('notes'), aid)
        )
        flash('Actividad actualizada', 'success')
        return redirect(url_for('activities.index'))

    centers = query_db(
        "SELECT id, name FROM activity_centers WHERE company_id=? AND (period_id=? OR period_id IS NULL) ORDER BY name",
        (company_id, period_id)
    )
    # Empleados asignados a esta actividad
    assignments = query_db(
        """SELECT eaa.*, e.full_name, e.code as emp_code, e.labor_type
           FROM employee_activity_assignments eaa
           JOIN employees e ON eaa.employee_id = e.id
           WHERE eaa.activity_id=?""",
        (aid,)
    )
    employees = query_db(
        "SELECT id, code, full_name, labor_type, cost_per_hour, available_hours_month FROM employees WHERE company_id=? AND is_active=1 ORDER BY full_name",
        (company_id,)
    )
    return render_template('activities/edit.html',
                           activity=activity, centers=centers,
                           driver_types=DRIVER_TYPES,
                           assignments=assignments,
                           employees=employees)


@activities_bp.route('/activities/<int:aid>/assign-employee', methods=['POST'])
@login_required
@company_required
@module_required('activities', write=True)
def assign_employee(aid):
    d = request.form
    emp_id = d.get('employee_id')
    pct    = float(d.get('assignment_pct', 0))
    period_id = session.get('period_id')

    # Obtener datos del empleado para calcular horas y costo
    emp = query_db("SELECT * FROM employees WHERE id=? AND company_id=?",
                   (emp_id, session['company_id']), one=True)
    if not emp:
        flash('Empleado no encontrado', 'error')
        return redirect(url_for('activities.edit', aid=aid))

    hours    = (emp['available_hours_month'] or 192) * pct / 100
    cost_asn = hours * (emp['cost_per_hour'] or 0)

    try:
        execute_db(
            """INSERT INTO employee_activity_assignments
               (employee_id, activity_id, assignment_pct, hours_assigned, cost_assigned, period_id)
               VALUES (?,?,?,?,?,?)""",
            (emp_id, aid, pct, hours, cost_asn, period_id)
        )
        # Actualizar horas asignadas del empleado
        execute_db(
            "UPDATE employees SET assigned_hours_month = assigned_hours_month + ? WHERE id=?",
            (hours, emp_id)
        )
        flash('Empleado asignado a la actividad', 'success')
    except Exception:
        flash('Este empleado ya está asignado a esta actividad en este período', 'error')
    return redirect(url_for('activities.edit', aid=aid))


@activities_bp.route('/activities/<int:aid>/assignments/<int:assignment_id>/delete', methods=['POST'])
@login_required
@company_required
@module_required('activities', write=True)
def delete_assignment(aid, assignment_id):
    company_id = session['company_id']
    assignment = query_db(
        """SELECT eaa.*, e.company_id
           FROM employee_activity_assignments eaa
           JOIN employees e ON e.id = eaa.employee_id
           WHERE eaa.id=? AND eaa.activity_id=? AND e.company_id=?""",
        (assignment_id, aid, company_id), one=True
    )
    if not assignment:
        flash('Asignación no encontrada', 'error')
        return redirect(url_for('activities.edit', aid=aid))

    execute_db(
        "UPDATE employees SET assigned_hours_month = MAX(assigned_hours_month - ?, 0) WHERE id=?",
        (assignment['hours_assigned'] or 0, assignment['employee_id'])
    )
    execute_db("DELETE FROM employee_activity_assignments WHERE id=?", (assignment_id,))
    flash('Asignación eliminada', 'success')
    return redirect(url_for('activities.edit', aid=aid))


@activities_bp.route('/activities/<int:aid>/delete', methods=['POST'])
@login_required
@company_required
@module_required('activities', write=True)
def delete(aid):
    execute_db("DELETE FROM activities WHERE id=?", (aid,))
    flash('Actividad eliminada', 'success')
    return redirect(url_for('activities.index'))


@activities_bp.route('/activities/api/list')
@login_required
@company_required
@module_required('activities', write=False)
def api_list():
    company_id = session['company_id']
    period_id  = session.get('period_id')
    rows = query_db(
        """SELECT a.id, a.code, a.name, a.driver_type, a.driver_total, ac.name as center_name
           FROM activities a JOIN activity_centers ac ON a.center_id=ac.id
           WHERE ac.company_id=? AND (ac.period_id=? OR ac.period_id IS NULL)
           ORDER BY a.name""",
        (company_id, period_id)
    )
    return jsonify([dict(r) for r in rows])
