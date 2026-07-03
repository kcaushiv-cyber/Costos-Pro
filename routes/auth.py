from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from models.database import query_db, execute_db
from utils.email_utils import send_welcome_email, send_password_reset_email
import secrets
import re
from datetime import datetime, timedelta

auth_bp = Blueprint('auth', __name__)

SECTORS = [
    'manufactura', 'textil', 'restaurante', 'salud', 'servicios',
    'comercio', 'educacion', 'construccion', 'otro'
]

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        user = query_db("SELECT * FROM users WHERE email = ?", [email], one=True)
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['full_name']
            session['user_role'] = user['role'] or 'analyst'
            # Buscar empresa propia primero
            company = query_db("SELECT * FROM companies WHERE user_id = ?", [user['id']], one=True)
            # Si no tiene empresa propia, buscar en company_users (usuario invitado)
            if not company:
                guest = query_db(
                    """SELECT c.*, cu.role as guest_role, cu.modules as guest_modules
                       FROM company_users cu
                       JOIN companies c ON cu.company_id = c.id
                       WHERE cu.user_id = ? ORDER BY cu.created_at DESC LIMIT 1""",
                    [user['id']], one=True
                )
                if guest:
                    company = guest
                    session['user_role']     = guest['guest_role'] or 'viewer'
                    session['guest_modules'] = guest['guest_modules'] or 'all'
            if company:
                session['company_id'] = company['id']
                session['company_name'] = company['business_name']
                session['sector'] = company['sector']
                # Cargar período activo
                if company['active_period_id']:
                    period = query_db("SELECT * FROM periods WHERE id=?",
                                      [company['active_period_id']], one=True)
                    if period:
                        session['period_id'] = period['id']
                        session['period_name'] = period['name']
            flash('¡Bienvenido de vuelta!', 'success')
            return redirect(url_for('dashboard.index'))
        else:
            flash('Correo o contraseña incorrectos.', 'danger')
    
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        business_name = request.form.get('business_name', '').strip()
        ruc = request.form.get('ruc', '').strip()
        sector = request.form.get('sector', '').strip()
        
        errors = []
        
        if not full_name:
            errors.append("El nombre completo es obligatorio.")
        if not email or not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
            errors.append("Ingresa un correo electrónico válido.")
        if len(password) < 8:
            errors.append("La contraseña debe tener al menos 8 caracteres.")
        if password != confirm_password:
            errors.append("Las contraseñas no coinciden.")
        if not business_name:
            errors.append("El nombre de la empresa es obligatorio.")
        if not ruc or not re.match(r'^\d{11}$', ruc):
            errors.append("El RUC debe tener exactamente 11 dígitos numéricos.")
        if sector.lower() not in SECTORS:
            errors.append("Selecciona un sector válido.")
        
        existing = query_db("SELECT id FROM users WHERE email = ?", [email], one=True)
        if existing:
            errors.append("Ya existe una cuenta con ese correo electrónico.")
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('auth/register.html', sectors=SECTORS,
                                   form_data=request.form)
        
        # Crear usuario
        password_hash = generate_password_hash(password)
        user_id = execute_db(
            "INSERT INTO users (full_name, email, password_hash) VALUES (?, ?, ?)",
            (full_name, email, password_hash)
        )
        
        # Crear empresa
        execute_db(
            "INSERT INTO companies (user_id, business_name, ruc, sector) VALUES (?, ?, ?, ?)",
            (user_id, business_name, ruc, sector)
        )
        
        # Enviar correo de bienvenida
        try:
            mail = current_app.extensions.get('mail')
            if mail and current_app.config.get('MAIL_USERNAME'):
                send_welcome_email(mail, email, full_name, business_name)
        except Exception as e:
            current_app.logger.error(f'Error correo bienvenida: {e}')
        
        # Audit log
        execute_db(
            "INSERT INTO audit_logs (user_id, entity_type, action, new_value) VALUES (?, ?, ?, ?)",
            (user_id, 'user', 'register', f"Nuevo usuario: {email}")
        )
        
        flash('¡Cuenta creada exitosamente! Ya puedes iniciar sesión.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', sectors=SECTORS, form_data={})

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = query_db("SELECT * FROM users WHERE email = ?", [email], one=True)
        
        if user:
            token = secrets.token_urlsafe(32)
            expiry = (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
            execute_db(
                "UPDATE users SET reset_token = ?, reset_token_expiry = ? WHERE id = ?",
                (token, expiry, user['id'])
            )
            # Construir link con el host correcto (localhost:5001 en local)
            host = current_app.config.get('APP_URL', 'http://localhost:5001')
            reset_link = f"{host}/reset-password/{token}" 
            try:
                mail = current_app.extensions.get('mail')
                if mail and current_app.config.get('MAIL_USERNAME'):
                    send_password_reset_email(mail, email, user['full_name'], reset_link)
                    current_app.logger.info(f'Reset email enviado a {email}')
            except Exception as e:
                current_app.logger.error(f'Error correo reset: {e}')
        
        flash('Si el correo existe, recibirás instrucciones para restablecer tu contraseña.', 'info')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/forgot_password.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = query_db(
        "SELECT * FROM users WHERE reset_token = ? AND reset_token_expiry > datetime('now')",
        [token], one=True
    )
    
    if not user:
        flash('El enlace de recuperación es inválido o ha expirado.', 'danger')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        
        if len(password) < 8:
            flash('La contraseña debe tener al menos 8 caracteres.', 'danger')
            return render_template('auth/reset_password.html', token=token)
        
        if password != confirm:
            flash('Las contraseñas no coinciden.', 'danger')
            return render_template('auth/reset_password.html', token=token)
        
        execute_db(
            "UPDATE users SET password_hash = ?, reset_token = NULL, reset_token_expiry = NULL WHERE id = ?",
            (generate_password_hash(password), user['id'])
        )
        flash('Contraseña restablecida correctamente. Ya puedes iniciar sesión.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html', token=token)

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('auth.login'))
