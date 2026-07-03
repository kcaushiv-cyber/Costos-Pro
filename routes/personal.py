from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, flash
from models.database import query_db, execute_db
from routes.dashboard import login_required, company_required, module_required
from services.labor_cost_service import calculate_employee_costs, calculate_team_costs, calculate_hours_utilization

personal_bp = Blueprint('personal', __name__)


@personal_bp.route('/personal')
@login_required
@company_required
@module_required('personal', write=False)
def index():
    session['active_module'] = 'personal'
    company_id = session['company_id']

    search = request.args.get('search', '')
    dept_filter = request.args.get('dept', '')
    type_filter = request.args.get('type', '')
    status_filter = request.args.get('status', 'activo')

    query = """
        SELECT e.*, d.name as dept_name, p.name as position_name
        FROM employees e
        LEFT JOIN departments d ON e.department_id = d.id
        LEFT JOIN positions p ON e.position_id = p.id
        WHERE e.company_id = ?
    """
    params = [company_id]

    if search:
        query += " AND (e.full_name LIKE ? OR e.code LIKE ? OR e.dni LIKE ?)"
        params += [f'%{search}%', f'%{search}%', f'%{search}%']
    if dept_filter:
        query += " AND e.department_id = ?"
        params.append(dept_filter)
    if type_filter:
        query += " AND e.labor_type = ?"
        params.append(type_filter)
    if status_filter == 'activo':
        query += " AND e.is_active = 1"
    elif status_filter == 'inactivo':
        query += " AND e.is_active = 0"

    query += " ORDER BY e.labor_type, e.full_name"
    employees = query_db(query, params)

    team_costs = calculate_team_costs([dict(e) for e in employees])
    hours_util = calculate_hours_utilization([dict(e) for e in employees])

    departments = query_db("SELECT * FROM departments WHERE company_id=? ORDER BY name", (company_id,))

    return render_template('personal/index.html',
                           employees=employees,
                           team_costs=team_costs,
                           hours_util=hours_util,
                           departments=departments,
                           search=search,
                           dept_filter=dept_filter,
                           type_filter=type_filter,
                           status_filter=status_filter)


@personal_bp.route('/personal/new', methods=['GET', 'POST'])
@login_required
@company_required
@module_required('personal', write=True)
def new():
    company_id = session['company_id']

    if request.method == 'POST':
        d = request.form
        basic      = float(d.get('basic_salary', 0))
        bonus      = float(d.get('bonus', 0))
        family     = float(d.get('family_allowance', 0))
        sctr_val   = float(d.get('sctr', 0))
        other      = float(d.get('other_benefits', 0))
        hours      = float(d.get('available_hours_month', 192))
        in_payroll = 1 if d.get('in_payroll') else 0

        # Si no está en planilla → beneficios = 0
        base  = basic + bonus + family
        grat  = round(base / 6,       2) if in_payroll else 0
        cts   = round(base * 7 / 72,  2) if in_payroll else 0
        ess   = round(basic * 0.09,   2) if in_payroll else 0
        sctr  = sctr_val                  if in_payroll else 0
        total = round(base + grat + cts + ess + sctr + other, 2)
        cph   = round(total / hours, 4)   if hours else 0

        eid = execute_db(
            """INSERT INTO employees
               (company_id, code, dni, full_name, position_id, department_id,
                contract_type, start_date, is_active, in_payroll,
                basic_salary, bonus, family_allowance,
                gratification_monthly, cts_monthly, essalud, sctr,
                other_benefits, total_monthly_cost, cost_per_hour,
                available_hours_month, labor_type, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (company_id, d['code'], d.get('dni'), d['full_name'],
             d.get('position_id') or None, d.get('department_id') or None,
             d.get('contract_type', 'indefinido'), d.get('start_date'),
             1 if d.get('is_active') else 0,
             in_payroll,
             basic, bonus, family,
             grat, cts, ess, sctr,
             other, total, cph,
             hours, d.get('labor_type', 'MOD'), d.get('notes'))
        )
        flash('Trabajador registrado exitosamente', 'success')
        return redirect(url_for('personal.detail', eid=eid))

    departments = query_db("SELECT * FROM departments WHERE company_id=? ORDER BY name", (company_id,))
    positions = query_db("SELECT * FROM positions WHERE company_id=? ORDER BY name", (company_id,))
    return render_template('personal/new.html',
                           departments=departments, positions=positions)


@personal_bp.route('/personal/<int:eid>')
@login_required
@company_required
@module_required('personal', write=False)
def detail(eid):
    company_id = session['company_id']
    employee = query_db(
        """SELECT e.*, d.name as dept_name, p.name as position_name
           FROM employees e
           LEFT JOIN departments d ON e.department_id = d.id
           LEFT JOIN positions p ON e.position_id = p.id
           WHERE e.id=? AND e.company_id=?""",
        (eid, company_id), one=True
    )
    if not employee:
        flash('Trabajador no encontrado', 'error')
        return redirect(url_for('personal.index'))

    # Actividades asignadas
    assignments = query_db(
        """SELECT eaa.*, a.name as activity_name, ac.name as center_name
           FROM employee_activity_assignments eaa
           JOIN activities a ON eaa.activity_id = a.id
           JOIN activity_centers ac ON a.center_id = ac.id
           WHERE eaa.employee_id = ?""",
        (eid,)
    )
    return render_template('personal/detail.html',
                           employee=employee, assignments=assignments)


@personal_bp.route('/personal/<int:eid>/edit', methods=['GET', 'POST'])
@login_required
@company_required
@module_required('personal', write=True)
def edit(eid):
    company_id = session['company_id']
    employee = query_db(
        "SELECT * FROM employees WHERE id=? AND company_id=?", (eid, company_id), one=True
    )
    if not employee:
        return redirect(url_for('personal.index'))

    if request.method == 'POST':
        d = request.form
        basic      = float(d.get('basic_salary', 0))
        bonus      = float(d.get('bonus', 0))
        family     = float(d.get('family_allowance', 0))
        sctr_val   = float(d.get('sctr', 0))
        other      = float(d.get('other_benefits', 0))
        hours      = float(d.get('available_hours_month', 192))
        in_payroll = 1 if d.get('in_payroll') else 0

        # Si no está en planilla → beneficios = 0
        base = basic + bonus + family
        grat = round(base / 6,        2) if in_payroll else 0
        cts  = round(base * 7 / 72,   2) if in_payroll else 0
        ess  = round(basic * 0.09,    2) if in_payroll else 0
        sctr = sctr_val                    if in_payroll else 0
        total = round(base + grat + cts + ess + sctr + other, 2)
        cph   = round(total / hours, 4)    if hours else 0

        # Departamento: texto libre → buscar/crear en tabla departments
        dept_name = (d.get('department_name') or '').strip()
        dept_id   = None
        if dept_name:
            dept = query_db("SELECT id FROM departments WHERE company_id=? AND name=?",
                            (company_id, dept_name), one=True)
            if dept:
                dept_id = dept['id']
            else:
                dept_id = execute_db(
                    "INSERT INTO departments (company_id, name, code) VALUES (?,?,?)",
                    (company_id, dept_name, dept_name[:6].upper())
                )

        # Cargo: texto libre → buscar/crear en tabla positions
        pos_name = (d.get('position_name') or '').strip()
        pos_id   = None
        if pos_name:
            pos = query_db("SELECT id FROM positions WHERE company_id=? AND name=?",
                           (company_id, pos_name), one=True)
            if pos:
                pos_id = pos['id']
            else:
                pos_id = execute_db(
                    "INSERT INTO positions (company_id, name, code) VALUES (?,?,?)",
                    (company_id, pos_name, pos_name[:6].upper())
                )

        execute_db(
            """UPDATE employees SET
               code=?, dni=?, full_name=?, position_id=?, department_id=?,
               contract_type=?, start_date=?, is_active=?, in_payroll=?,
               basic_salary=?, bonus=?, family_allowance=?,
               gratification_monthly=?, cts_monthly=?, essalud=?, sctr=?,
               other_benefits=?, total_monthly_cost=?, cost_per_hour=?,
               available_hours_month=?, labor_type=?, notes=?,
               updated_at=CURRENT_TIMESTAMP
               WHERE id=? AND company_id=?""",
            (d['code'], d.get('dni'), d['full_name'],
             pos_id, dept_id,
             d.get('contract_type', 'indefinido'), d.get('start_date') or None,
             1 if d.get('is_active') else 0,
             in_payroll,
             basic, bonus, family,
             grat, cts, ess, sctr,
             other, total, cph,
             hours, d.get('labor_type', 'MOD'), d.get('notes'),
             eid, company_id)
        )
        flash('Trabajador actualizado', 'success')
        return redirect(url_for('personal.detail', eid=eid))

    departments = query_db("SELECT * FROM departments WHERE company_id=? ORDER BY name", (company_id,))
    positions   = query_db("SELECT * FROM positions WHERE company_id=? ORDER BY name", (company_id,))
    # Pasar nombres actuales al template
    emp_data = dict(employee)
    emp_data['dept_name'] = ''
    emp_data['pos_name']  = ''
    if employee['department_id']:
        dept = query_db("SELECT name FROM departments WHERE id=?", (employee['department_id'],), one=True)
        if dept: emp_data['dept_name'] = dept['name']
    if employee['position_id']:
        pos = query_db("SELECT name FROM positions WHERE id=?", (employee['position_id'],), one=True)
        if pos: emp_data['pos_name'] = pos['name']

    from werkzeug.datastructures import ImmutableMultiDict
    class AttrDict(dict):
        def __getattr__(self, k): return self.get(k)
    employee = AttrDict(emp_data)

    return render_template('personal/edit.html',
                           employee=employee,
                           departments=departments,
                           positions=positions)


@personal_bp.route('/personal/<int:eid>/toggle', methods=['POST'])
@login_required
@company_required
@module_required('personal', write=True)
def toggle_active(eid):
    company_id = session['company_id']
    emp = query_db("SELECT is_active FROM employees WHERE id=? AND company_id=?",
                   (eid, company_id), one=True)
    if emp:
        execute_db("UPDATE employees SET is_active=? WHERE id=?",
                   (0 if emp['is_active'] else 1, eid))
    return redirect(url_for('personal.index'))


@personal_bp.route('/personal/api/calculate', methods=['POST'])
@login_required
@module_required('personal', write=True)
def api_calculate():
    """API para calcular costo en tiempo real desde el formulario."""
    d = request.get_json()
    try:
        in_payroll = bool(d.get('in_payroll', True))
        basic  = float(d.get('basic_salary', 0))
        bonus  = float(d.get('bonus', 0))
        family = float(d.get('family_allowance', 0))
        sctr_v = float(d.get('sctr', 0))
        other  = float(d.get('other_benefits', 0))
        hours  = float(d.get('available_hours', 192))

        base  = basic + bonus + family
        grat  = round(base / 6,       2) if in_payroll else 0
        cts   = round(base * 7 / 72,  2) if in_payroll else 0
        ess   = round(basic * 0.09,   2) if in_payroll else 0
        sctr  = sctr_v                    if in_payroll else 0
        total = round(base + grat + cts + ess + sctr + other, 2)
        cph   = round(total / hours, 4)   if hours else 0

        costs = {
            'basic_salary': round(basic, 2),
            'bonus': round(bonus, 2),
            'family_allowance': round(family, 2),
            'gratification_monthly': grat,
            'cts_monthly': cts,
            'essalud': ess,
            'sctr': sctr,
            'other_benefits': round(other, 2),
            'total_monthly_cost': total,
            'cost_per_hour': cph,
            'available_hours': hours,
        }
        return jsonify({'success': True, 'costs': costs})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@personal_bp.route('/personal/departments', methods=['GET', 'POST'])
@login_required
@company_required
@module_required('personal', write=True)
def departments():
    company_id = session['company_id']
    if request.method == 'POST':
        d = request.form
        try:
            execute_db(
                "INSERT INTO departments (company_id, code, name) VALUES (?,?,?)",
                (company_id, d['code'], d['name'])
            )
            flash('Departamento creado', 'success')
        except Exception:
            flash('El código ya existe', 'error')
    depts = query_db("SELECT * FROM departments WHERE company_id=? ORDER BY name", (company_id,))
    return render_template('personal/departments.html', departments=depts)
