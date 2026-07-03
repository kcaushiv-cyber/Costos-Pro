from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, flash
from models.database import query_db, execute_db
from routes.dashboard import login_required, company_required, module_required

products_bp = Blueprint('products', __name__)


@products_bp.route('/products')
@login_required
@company_required
@module_required('products', write=False)
def index():
    session['active_module'] = 'products'
    company_id = session['company_id']
    search = request.args.get('search', '')
    cat_filter = request.args.get('category', '')

    q = """SELECT ps.*, u.name as unit_name
           FROM products_services ps
           LEFT JOIN units_of_measure u ON ps.unit_id = u.id
           WHERE ps.company_id = ?"""
    params = [company_id]
    if search:
        q += " AND (ps.name LIKE ? OR ps.code LIKE ?)"
        params += [f'%{search}%', f'%{search}%']
    if cat_filter:
        q += " AND ps.category = ?"
        params.append(cat_filter)
    q += " ORDER BY ps.category, ps.name"
    products = query_db(q, params)

    units = query_db("SELECT * FROM units_of_measure WHERE company_id=? ORDER BY name", (company_id,))
    return render_template('products/index.html',
                           products=products, units=units,
                           search=search, cat_filter=cat_filter)


@products_bp.route('/products/new', methods=['GET', 'POST'])
@login_required
@company_required
@module_required('products', write=True)
def new():
    company_id = session['company_id']
    if request.method == 'POST':
        d = request.form
        try:
            execute_db(
                """INSERT INTO products_services
                   (company_id, code, name, description, category, unit_id, sale_price, standard_cost)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (company_id, d['code'], d['name'], d.get('description'),
                 d.get('category', 'producto'),
                 d.get('unit_id') or None,
                 float(d.get('sale_price', 0)),
                 float(d.get('standard_cost', 0)))
            )
            flash('Producto/Servicio registrado', 'success')
            return redirect(url_for('products.index'))
        except Exception as e:
            flash(f'Error: el código ya existe o datos inválidos', 'error')

    units = query_db("SELECT * FROM units_of_measure WHERE company_id=? ORDER BY name", (company_id,))
    categories = ['producto', 'servicio', 'semielaborado', 'materia_prima']
    return render_template('products/new.html', units=units, categories=categories)


@products_bp.route('/products/<int:pid>/edit', methods=['GET', 'POST'])
@login_required
@company_required
@module_required('products', write=True)
def edit(pid):
    company_id = session['company_id']
    product = query_db(
        "SELECT * FROM products_services WHERE id=? AND company_id=?", (pid, company_id), one=True
    )
    if not product:
        return redirect(url_for('products.index'))

    if request.method == 'POST':
        d = request.form
        execute_db(
            """UPDATE products_services SET
               code=?, name=?, description=?, category=?,
               unit_id=?, sale_price=?, standard_cost=?, is_active=?
               WHERE id=? AND company_id=?""",
            (d['code'], d['name'], d.get('description'), d.get('category'),
             d.get('unit_id') or None,
             float(d.get('sale_price', 0)),
             float(d.get('standard_cost', 0)),
             1 if d.get('is_active') != 'off' else 0,
             pid, company_id)
        )
        flash('Producto actualizado', 'success')
        return redirect(url_for('products.index'))

    units = query_db("SELECT * FROM units_of_measure WHERE company_id=? ORDER BY name", (company_id,))
    categories = ['producto', 'servicio', 'semielaborado', 'materia_prima']
    return render_template('products/edit.html',
                           product=product, units=units, categories=categories)


@products_bp.route('/products/<int:pid>/delete', methods=['POST'])
@login_required
@company_required
@module_required('products', write=True)
def delete(pid):
    company_id = session['company_id']
    execute_db(
        "UPDATE products_services SET is_active=0 WHERE id=? AND company_id=?",
        (pid, company_id)
    )
    flash('Producto desactivado', 'success')
    return redirect(url_for('products.index'))


@products_bp.route('/products/units', methods=['GET', 'POST'])
@login_required
@company_required
@module_required('products', write=True)
def units():
    company_id = session['company_id']
    if request.method == 'POST':
        d = request.form
        try:
            execute_db(
                "INSERT INTO units_of_measure (company_id, code, name, category) VALUES (?,?,?,?)",
                (company_id, d['code'], d['name'], d.get('category', 'unidad'))
            )
            flash('Unidad de medida creada', 'success')
        except Exception:
            flash('El código ya existe', 'error')
    uom = query_db("SELECT * FROM units_of_measure WHERE company_id=? ORDER BY name", (company_id,))
    return render_template('products/units.html', units=uom)


@products_bp.route('/products/api/search')
@login_required
@company_required
@module_required('products', write=False)
def api_search():
    company_id = session['company_id']
    q = request.args.get('q', '')
    products = query_db(
        "SELECT id, code, name, sale_price FROM products_services WHERE company_id=? AND name LIKE ? AND is_active=1 LIMIT 10",
        (company_id, f'%{q}%')
    )
    return jsonify([dict(p) for p in products])
