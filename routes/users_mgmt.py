from flask import Blueprint, render_template, session, request, jsonify, flash, redirect, url_for
from models.database import query_db, execute_db
from routes.dashboard import login_required, company_required
from werkzeug.security import generate_password_hash

users_bp = Blueprint('users_mgmt', __name__)

MODULES = [
    ('personal',         'Personal y MOD'),
    ('products',         'Productos y Servicios'),
    ('kardex',           'Inventario / Kardex'),
    ('structures',       'Estructura de Costos'),
    ('resources',        'Recursos ABC'),
    ('activity_centers', 'Centros de Actividad'),
    ('activities',       'Actividades ABC'),
    ('cost_objects',     'Objetos de Costo'),
    ('abc',              'Costeo ABC'),
    ('process_costs',    'Costos por Proceso'),
    ('budgets',          'Presupuestos'),
    ('quality_costs',    'Costos de Calidad'),
    ('reports',          'Reportes'),
    ('breakeven',        'Punto de Equilibrio'),
    ('compare',          'Comparar Períodos'),
    ('import_data',      'Importar Excel'),
]

ROLES = [
    ('admin',   'Administrador',  'Acceso total — puede crear, editar y eliminar'),
    ('editor',  'Editor',         'Puede crear y editar, no eliminar'),
    ('viewer',  'Solo lectura',   'Solo puede ver datos, sin modificaciones'),
    ('custom',  'Personalizado',  'Define qué módulos puede usar'),
]


@users_bp.route('/settings/users')
@login_required
@company_required
def index():
    company_id = session['company_id']

    # Usuarios de esta empresa (owner + invitados)
    company = query_db("SELECT * FROM companies WHERE id=?", (company_id,), one=True)
    owner   = query_db("SELECT * FROM users WHERE id=?", (company['user_id'],), one=True)

    guests  = query_db(
        """SELECT cu.*, u.full_name, u.email, u.is_active
           FROM company_users cu
           JOIN users u ON cu.user_id = u.id
           WHERE cu.company_id=?
           ORDER BY cu.created_at DESC""",
        (company_id,)
    )

    return render_template('settings/users.html',
                           owner=owner, guests=guests,
                           modules=MODULES, roles=ROLES,
                           company_id=company_id)


@users_bp.route('/settings/users/invite', methods=['POST'])
@login_required
@company_required
def invite():
    """Invita un usuario existente o crea uno nuevo con permisos."""
    company_id = session['company_id']
    d = request.form

    email    = d.get('email', '').strip().lower()
    role     = d.get('role', 'viewer')
    password = d.get('password', '').strip()

    if role == 'custom':
        mod_levels = []
        for mod_id, _label in MODULES:
            level = d.get(f'level_{mod_id}', '')
            if level in ('read', 'write'):
                mod_levels.append(f'{mod_id}:{level}')
        modules = ','.join(mod_levels) if mod_levels else ''
    else:
        modules = 'all'

    if not email:
        flash('El correo es obligatorio', 'error')
        return redirect(url_for('users_mgmt.index'))

    # Buscar si ya existe el usuario
    user = query_db("SELECT * FROM users WHERE email=?", (email,), one=True)

    if not user:
        if not password or len(password) < 6:
            flash('El usuario no existe. Proporciona una contraseña (mín. 6 caracteres) para crearlo.', 'error')
            return redirect(url_for('users_mgmt.index'))
        # Crear usuario nuevo
        uid = execute_db(
            "INSERT INTO users (full_name, email, password_hash, role, is_active) VALUES (?,?,?,?,1)",
            (d.get('full_name', email.split('@')[0]),
             email,
             generate_password_hash(password),
             'analyst')
        )
    else:
        uid = user['id']

    # Verificar que no esté ya invitado
    existing = query_db(
        "SELECT id FROM company_users WHERE company_id=? AND user_id=?",
        (company_id, uid), one=True
    )
    if existing:
        flash('Este usuario ya tiene acceso a la empresa', 'error')
        return redirect(url_for('users_mgmt.index'))

    execute_db(
        "INSERT INTO company_users (company_id, user_id, role, modules, invited_by) VALUES (?,?,?,?,?)",
        (company_id, uid, role, modules, session['user_id'])
    )

    # Enviar correo de bienvenida/invitación
    try:
        from flask import current_app
        from flask_mail import Mail
        from utils.email_utils import send_invite_email
        mail = Mail(current_app)
        company = query_db("SELECT * FROM companies WHERE id=?", (company_id,), one=True)
        invited_user = query_db("SELECT * FROM users WHERE id=?", (uid,), one=True)
        if company and invited_user:
            send_invite_email(
                mail,
                to_email=email,
                full_name=invited_user['full_name'],
                company_name=company['business_name'],
                inviter_name=session.get('user_name', 'El administrador'),
                role=role,
                is_new_user=not user,  # True si fue creado ahora
                password=password if not user else None
            )
    except Exception as e:
        current_app.logger.error(f"Error enviando correo de invitación: {e}")

    flash(f'Usuario {email} agregado con rol {role}. Se envió correo de invitación.', 'success')
    return redirect(url_for('users_mgmt.index'))


@users_bp.route('/settings/users/<int:cuid>/update', methods=['POST'])
@login_required
@company_required
def update_user(cuid):
    company_id = session['company_id']
    d = request.form
    role = d.get('role', 'viewer')

    if role == 'custom':
        mod_levels = []
        for mod_id, _label in MODULES:
            level = d.get(f'level_{mod_id}', '')
            if level in ('read', 'write'):
                mod_levels.append(f'{mod_id}:{level}')
        modules = ','.join(mod_levels) if mod_levels else ''
    else:
        modules = 'all'

    execute_db(
        "UPDATE company_users SET role=?, modules=? WHERE id=? AND company_id=?",
        (role, modules, cuid, company_id)
    )
    flash('Permisos actualizados', 'success')
    return redirect(url_for('users_mgmt.index'))


@users_bp.route('/settings/users/<int:cuid>/remove', methods=['POST'])
@login_required
@company_required
def remove_user(cuid):
    company_id = session['company_id']
    execute_db("DELETE FROM company_users WHERE id=? AND company_id=?", (cuid, company_id))
    flash('Usuario removido', 'success')
    return redirect(url_for('users_mgmt.index'))
