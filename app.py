import os
import json
from datetime import date
from flask import Flask, render_template, session
from flask_mail import Mail
from dotenv import load_dotenv
from models.database import init_db, init_app

load_dotenv()
mail = Mail()

def create_app(config_name='default'):
    app = Flask(__name__)

    from config import config
    app.config.from_object(config[config_name])

    mail.init_app(app)
    init_app(app)

    # ── Blueprints Fase 1 ──────────────────────────────────────
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.companies import companies_bp
    from routes.personal import personal_bp
    from routes.products import products_bp
    from routes.kardex import kardex_bp
    from routes.structures import structures_bp
    from routes.ai import ai_bp
    from routes.manual import manual_bp
    from routes.settings import settings_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(companies_bp)
    app.register_blueprint(personal_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(kardex_bp)
    app.register_blueprint(structures_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(manual_bp)
    app.register_blueprint(settings_bp)

    # ── Fase 2: Sistema ABC ────────────────────────────────────────────────
    from routes.resources import resources_bp
    from routes.activity_centers import activity_centers_bp
    from routes.activities import activities_bp
    from routes.cost_objects import cost_objects_bp
    from routes.abc import abc_bp

    app.register_blueprint(resources_bp)
    app.register_blueprint(activity_centers_bp)
    app.register_blueprint(activities_bp)
    app.register_blueprint(cost_objects_bp)
    app.register_blueprint(abc_bp)

    # ── Fase 3: Proceso, Presupuestos, Calidad ───────────────────────────
    from routes.process_costs import process_costs_bp
    from routes.budgets import budgets_bp
    from routes.quality_costs import quality_costs_bp

    app.register_blueprint(process_costs_bp)
    app.register_blueprint(budgets_bp)
    app.register_blueprint(quality_costs_bp)

    # ── Fase 4: Reportes ─────────────────────────────────────────────────
    from routes.reports import reports_bp
    from routes.breakeven import breakeven_bp
    from routes.compare import compare_bp
    from routes.import_data import import_bp
    from routes.users_mgmt import users_bp

    app.register_blueprint(reports_bp)
    app.register_blueprint(breakeven_bp)
    app.register_blueprint(compare_bp)
    app.register_blueprint(import_bp)
    app.register_blueprint(users_bp)

    with app.app_context():
        init_db()
        _seed_demo_data()

    # ── Error handlers ─────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return render_template('partials/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('partials/500.html'), 500

    # ── Template filters ───────────────────────────────────────
    @app.template_filter('from_json')
    def from_json_filter(value):
        try:
            return json.loads(value) if value else {}
        except Exception:
            return {}

    @app.template_filter('currency')
    def currency_filter(value):
        try:
            return f"S/ {float(value):,.2f}"
        except Exception:
            return "S/ 0.00"

    @app.template_filter('pct')
    def pct_filter(value):
        try:
            return f"{float(value):.1f}%"
        except Exception:
            return "0.0%"

    # ── Context processor ──────────────────────────────────────
    @app.context_processor
    def inject_globals():
        return {
            'current_user_name': session.get('user_name', ''),
            'current_user_id': session.get('user_id'),
            'current_user_role': session.get('user_role', 'analyst'),
            'current_company': session.get('company_name', ''),
            'current_company_id': session.get('company_id'),
            'current_sector': session.get('sector', ''),
            'current_period': session.get('period_name', ''),
            'current_period_id': session.get('period_id'),
            'user_logged_in': 'user_id' in session,
            'today': date.today().isoformat(),
            'app_version': '5.0',
        }

    return app


def _seed_demo_data():
    """Inserta datos demo si la BD está vacía."""
    from models.database import query_db, execute_db
    from werkzeug.security import generate_password_hash

    existing = query_db("SELECT id FROM users WHERE email = 'demo@costospro.com'", one=True)
    if existing:
        return

    # Usuario demo
    uid = execute_db(
        "INSERT INTO users (full_name, email, password_hash, role) VALUES (?,?,?,?)",
        ('Demo Usuario', 'demo@costospro.com',
         generate_password_hash('demo1234'), 'admin')
    )

    # Empresa demo
    cid = execute_db(
        """INSERT INTO companies (user_id, business_name, trade_name, ruc, sector, currency)
           VALUES (?,?,?,?,?,?)""",
        (uid, 'Empresa Demo S.A.', 'Demo SA', '20123456789', 'manufactura', 'PEN')
    )

    # Período demo
    pid = execute_db(
        """INSERT INTO periods (company_id, name, period_type, start_date, end_date, is_active)
           VALUES (?,?,?,?,?,?)""",
        (cid, 'Enero 2025', 'monthly', '2025-01-01', '2025-01-31', 1)
    )

    # Actualizar período activo
    execute_db("UPDATE companies SET active_period_id = ? WHERE id = ?", (pid, cid))

    # Departamentos demo
    dept_prod = execute_db(
        "INSERT INTO departments (company_id, code, name) VALUES (?,?,?)",
        (cid, 'PROD', 'Producción')
    )
    dept_adm = execute_db(
        "INSERT INTO departments (company_id, code, name) VALUES (?,?,?)",
        (cid, 'ADM', 'Administración')
    )

    # Cargos demo
    execute_db(
        "INSERT INTO positions (company_id, code, name, department_id, labor_type) VALUES (?,?,?,?,?)",
        (cid, 'OP01', 'Operario de Producción', dept_prod, 'MOD')
    )
    execute_db(
        "INSERT INTO positions (company_id, code, name, department_id, labor_type) VALUES (?,?,?,?,?)",
        (cid, 'ADM01', 'Asistente Administrativo', dept_adm, 'admin')
    )

    # Empleados demo
    execute_db(
        """INSERT INTO employees
           (company_id, code, full_name, position_id, department_id,
            basic_salary, essalud, total_monthly_cost, cost_per_hour,
            available_hours_month, labor_type, is_active, in_payroll)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (cid, 'EMP001', 'Juan Pérez García', 1, dept_prod,
         1200.0, 108.0, 1350.0, 7.03, 192.0, 'MOD', 1, 1)
    )
    execute_db(
        """INSERT INTO employees
           (company_id, code, full_name, position_id, department_id,
            basic_salary, essalud, total_monthly_cost, cost_per_hour,
            available_hours_month, labor_type, is_active, in_payroll)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (cid, 'EMP002', 'María López Torres', 2, dept_adm,
         1500.0, 135.0, 1680.0, 8.75, 192.0, 'admin', 1, 1)
    )

    # Productos demo
    execute_db(
        """INSERT INTO products_services
           (company_id, code, name, category, sale_price)
           VALUES (?,?,?,?,?)""",
        (cid, 'PROD001', 'Producto A', 'producto', 150.0)
    )
    execute_db(
        """INSERT INTO products_services
           (company_id, code, name, category, sale_price)
           VALUES (?,?,?,?,?)""",
        (cid, 'PROD002', 'Producto B', 'producto', 200.0)
    )

    # Unidades de medida demo
    for code, name, cat in [
        ('UND', 'Unidad', 'unidad'),
        ('KG', 'Kilogramo', 'peso'),
        ('LT', 'Litro', 'volumen'),
        ('HR', 'Hora', 'tiempo'),
        ('M2', 'Metro cuadrado', 'longitud'),
    ]:
        execute_db(
            "INSERT INTO units_of_measure (company_id, code, name, category) VALUES (?,?,?,?)",
            (cid, code, name, cat)
        )

    # Inventario demo
    inv1 = execute_db(
        """INSERT INTO inventory_items
           (company_id, code, name, category, current_stock, average_cost, valuation_method)
           VALUES (?,?,?,?,?,?,?)""",
        (cid, 'INS001', 'Materia Prima A', 'insumo', 500.0, 5.50, 'promedio')
    )
    execute_db(
        """INSERT INTO kardex_movements
           (inventory_item_id, movement_date, movement_type, quantity, unit_cost,
            total_cost, stock_after, average_cost_after, reference)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (inv1, '2025-01-05', 'entrada', 500.0, 5.50,
         2750.0, 500.0, 5.50, 'Compra inicial')
    )


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5001)
