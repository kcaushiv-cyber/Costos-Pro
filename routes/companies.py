from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, flash
from models.database import query_db, execute_db
from routes.dashboard import login_required

companies_bp = Blueprint('companies', __name__)


@companies_bp.route('/companies')
@login_required
def select():
    user_id = session['user_id']
    companies = query_db(
        "SELECT * FROM companies WHERE user_id=? ORDER BY business_name",
        (user_id,)
    )
    return render_template('companies/select.html', companies=companies)


@companies_bp.route('/companies/new', methods=['GET', 'POST'])
@login_required
def new():
    if request.method == 'POST':
        d = request.form
        cid = execute_db(
            """INSERT INTO companies
               (user_id, business_name, trade_name, ruc, sector, subsector,
                address, phone, email, currency, igv_rate)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (session['user_id'], d['business_name'], d.get('trade_name'),
             d.get('ruc'), d['sector'], d.get('subsector'),
             d.get('address'), d.get('phone'), d.get('email'),
             d.get('currency', 'PEN'), float(d.get('igv_rate', 0.18)))
        )
        # Crear período inicial
        pid = execute_db(
            """INSERT INTO periods (company_id, name, period_type, start_date, end_date, is_active)
               VALUES (?,?,?,?,?,?)""",
            (cid, d.get('period_name', 'Período 1'),
             d.get('period_type', 'monthly'),
             d.get('start_date', '2025-01-01'),
             d.get('end_date', '2025-12-31'), 1)
        )
        execute_db("UPDATE companies SET active_period_id=? WHERE id=?", (pid, cid))

        # Crear unidades de medida básicas
        for code, name, cat in [
            ('UND', 'Unidad', 'unidad'), ('KG', 'Kilogramo', 'peso'),
            ('LT', 'Litro', 'volumen'), ('HR', 'Hora', 'tiempo'),
            ('M2', 'Metro cuadrado', 'longitud'),
        ]:
            try:
                execute_db(
                    "INSERT INTO units_of_measure (company_id, code, name, category) VALUES (?,?,?,?)",
                    (cid, code, name, cat)
                )
            except Exception:
                pass

        _set_company_session(cid)
        flash('Empresa creada exitosamente', 'success')
        return redirect(url_for('dashboard.dashboard'))

    sectors = ['manufactura', 'textil', 'restaurante', 'salud', 'servicios',
               'comercio', 'educacion', 'construccion', 'otro']
    return render_template('companies/new.html', sectors=sectors)


@companies_bp.route('/companies/<int:cid>/select')
@login_required
def set_active(cid):
    user_id = session['user_id']
    company = query_db(
        "SELECT * FROM companies WHERE id=? AND user_id=?", (cid, user_id), one=True
    )
    if not company:
        flash('Empresa no encontrada', 'error')
        return redirect(url_for('companies.select'))
    _set_company_session(cid)
    return redirect(url_for('dashboard.dashboard'))


@companies_bp.route('/companies/<int:cid>/period/<int:pid>/select')
@login_required
def set_period(cid, pid):
    period = query_db(
        "SELECT * FROM periods WHERE id=? AND company_id=?", (pid, cid), one=True
    )
    if period:
        session['period_id'] = pid
        session['period_name'] = period['name']
        # Desactivar todos los períodos de esta empresa
        execute_db("UPDATE periods SET is_active=0 WHERE company_id=?", (cid,))
        # Activar el seleccionado
        execute_db("UPDATE periods SET is_active=1 WHERE id=?", (pid,))
        # Actualizar active_period_id en la empresa
        execute_db("UPDATE companies SET active_period_id=? WHERE id=?", (pid, cid))
        flash(f'Período activo: {period["name"]}', 'success')
    return redirect(request.referrer or url_for('dashboard.dashboard'))


@companies_bp.route('/companies/<int:cid>/settings', methods=['GET', 'POST'])
@login_required
def settings(cid):
    user_id = session['user_id']
    company = query_db("SELECT * FROM companies WHERE id=? AND user_id=?", (cid, user_id), one=True)
    if not company:
        return redirect(url_for('companies.select'))

    if request.method == 'POST':
        d = request.form
        execute_db(
            """UPDATE companies SET business_name=?, trade_name=?, ruc=?, sector=?,
               address=?, phone=?, email=?, currency=?, igv_rate=?
               WHERE id=?""",
            (d['business_name'], d.get('trade_name'), d.get('ruc'), d['sector'],
             d.get('address'), d.get('phone'), d.get('email'),
             d.get('currency', 'PEN'), float(d.get('igv_rate', 0.18)), cid)
        )
        session['company_name'] = d['business_name']
        session['sector'] = d['sector']
        flash('Empresa actualizada', 'success')
        return redirect(url_for('companies.settings', cid=cid))

    periods = query_db("SELECT * FROM periods WHERE company_id=? ORDER BY start_date DESC", (cid,))
    sectors = ['manufactura', 'textil', 'restaurante', 'salud', 'servicios',
               'comercio', 'educacion', 'construccion', 'otro']
    return render_template('companies/settings.html',
                           company=company, periods=periods, sectors=sectors)


@companies_bp.route('/companies/<int:cid>/periods/new', methods=['POST'])
@login_required
def new_period(cid):
    d = request.form
    pid = execute_db(
        """INSERT INTO periods (company_id, name, period_type, start_date, end_date)
           VALUES (?,?,?,?,?)""",
        (cid, d['name'], d.get('period_type', 'monthly'),
         d['start_date'], d['end_date'])
    )
    flash('Período creado', 'success')
    return redirect(url_for('companies.settings', cid=cid))


def _set_company_session(company_id):
    company = query_db("SELECT * FROM companies WHERE id=?", (company_id,), one=True)
    if not company:
        return
    session['company_id'] = company['id']
    session['company_name'] = company['business_name']
    session['sector'] = company['sector']

    if company['active_period_id']:
        period = query_db("SELECT * FROM periods WHERE id=?", (company['active_period_id'],), one=True)
        if period:
            session['period_id'] = period['id']
            session['period_name'] = period['name']
