from flask import Blueprint, request, jsonify, session
from models.database import execute_db, query_db
from routes.dashboard import login_required, company_required
from services.claude_service import (
    send_message, classify_cost, classify_quality_cost,
    generate_cost_structure, interpret_chart_data, health_check
)

ai_bp = Blueprint('ai', __name__, url_prefix='/ai')


def _save_message(conv_id, role, content, tokens=0):
    if conv_id:
        try:
            execute_db(
                "INSERT INTO ai_messages (conversation_id, role, content, tokens_used) VALUES (?,?,?,?)",
                (conv_id, role, content, tokens)
            )
        except Exception:
            pass


def _get_or_create_conversation(agent_type='general'):
    user_id = session.get('user_id')
    if not user_id:
        return None
    company_id = session.get('company_id')
    period_id = session.get('period_id')
    module = session.get('active_module', 'dashboard')

    conv_id = execute_db(
        """INSERT INTO ai_conversations
           (user_id, company_id, period_id, agent_type, module_context)
           VALUES (?,?,?,?,?)""",
        (user_id, company_id, period_id, agent_type, module)
    )
    return conv_id


@ai_bp.route('/chat', methods=['POST'])
@login_required
def chat():
    data = request.get_json()
    message = data.get('message', '').strip()
    history = data.get('history', [])
    agent_type = data.get('agent', 'general')

    if not message:
        return jsonify({'success': False, 'error': 'Mensaje vacío'}), 400

    result = send_message(message, history=history, agent_type=agent_type)

    if result['success']:
        conv_id = _get_or_create_conversation(agent_type)
        _save_message(conv_id, 'user', message)
        _save_message(conv_id, 'assistant', result['response'], result.get('tokens', 0))

    return jsonify(result)


@ai_bp.route('/classify-cost', methods=['POST'])
@login_required
def api_classify_cost():
    data = request.get_json()
    description = data.get('description', '').strip()
    if not description:
        return jsonify({'success': False, 'error': 'Descripción requerida'}), 400
    result = classify_cost(description)
    return jsonify({'success': 'error' not in result, 'data': result})


@ai_bp.route('/classify-quality', methods=['POST'])
@login_required
def api_classify_quality():
    data = request.get_json()
    name = data.get('activity_name', '').strip()
    desc = data.get('description', '')
    if not name:
        return jsonify({'success': False, 'error': 'Nombre de actividad requerido'}), 400
    result = classify_quality_cost(name, desc)
    return jsonify({'success': 'error' not in result, 'data': result})


@ai_bp.route('/generate-structure', methods=['POST'])
@login_required
def api_generate_structure():
    data = request.get_json()
    description = data.get('description', '').strip()
    sector = data.get('sector', session.get('sector', ''))
    if not description:
        return jsonify({'success': False, 'error': 'Descripción del negocio requerida'}), 400
    result = generate_cost_structure(description, sector)
    return jsonify(result)


@ai_bp.route('/interpret-chart', methods=['POST'])
@login_required
def api_interpret_chart():
    data = request.get_json()
    chart_data = data.get('chart_data', {})
    chart_type = data.get('chart_type', 'barras')
    module = data.get('module', session.get('active_module', ''))
    result = interpret_chart_data(chart_data, chart_type, module)
    return jsonify(result)


@ai_bp.route('/health')
def health():
    return jsonify(health_check())


# ── Generación masiva con IA ───────────────────────────────────────────────

@ai_bp.route('/generate/<string:entity>', methods=['POST'])
@login_required
@company_required
def generate_entity(entity):
    """
    Genera y opcionalmente inserta registros con IA para cualquier entidad.
    entity: resources | activity_centers | activities | cost_objects |
            kardex | quality | process_dept | budget_base | cost_structure
    """
    from models.database import query_db, execute_db

    data        = request.get_json()
    context     = data.get('context', '')
    insert      = data.get('insert', False)
    company_id  = session['company_id']
    period_id   = session.get('period_id')
    sector      = session.get('sector', '')
    company     = session.get('company_name', '')

    # ── Leer BD para contexto enriquecido ────────────────────────────────
    from models.database import query_db as qdb

    def _fmt(rows, keys):
        if not rows: return 'Ninguno registrado aún.'
        return ', '.join(
            ' | '.join(f"{k}={str(r[k])}" for k in keys if r[k])
            for r in rows[:15]
        )

    existing = {
        'resources': _fmt(
            qdb("SELECT code, name, category, monthly_amount FROM resources WHERE company_id=? AND (period_id=? OR period_id IS NULL) ORDER BY id DESC", (company_id, period_id)),
            ['code','name','category','monthly_amount']
        ),
        'centers': _fmt(
            qdb("SELECT code, name, center_type FROM activity_centers WHERE company_id=? ORDER BY id DESC", (company_id,)),
            ['code','name','center_type']
        ),
        'activities': _fmt(
            qdb("SELECT code, name, driver_type FROM activities WHERE company_id=? ORDER BY id DESC", (company_id,)),
            ['code','name','driver_type']
        ),
        'objects': _fmt(
            qdb("SELECT code, name, quantity_month FROM cost_objects WHERE company_id=? AND (period_id=? OR period_id IS NULL) ORDER BY id DESC", (company_id, period_id)),
            ['code','name','quantity_month']
        ),
        'employees': _fmt(
            qdb("SELECT code, full_name, labor_type, basic_salary FROM employees WHERE company_id=? AND is_active=1 ORDER BY id DESC", (company_id,)),
            ['code','full_name','labor_type','basic_salary']
        ),
        'products': _fmt(
            qdb("SELECT code, name, category, sale_price FROM products_services WHERE company_id=? AND is_active=1 ORDER BY id DESC", (company_id,)),
            ['code','name','category','sale_price']
        ),
        'inventory': _fmt(
            qdb("SELECT code, name, current_stock, average_cost FROM inventory_items WHERE company_id=? AND is_active=1 ORDER BY id DESC", (company_id,)),
            ['code','name','current_stock','average_cost']
        ),
        'quality': _fmt(
            qdb("SELECT activity_name, category, monthly_cost FROM quality_costs WHERE company_id=? AND period_id=? ORDER BY id DESC", (company_id, period_id)),
            ['activity_name','category','monthly_cost']
        ),
        'budget_sales': _fmt(
            qdb("SELECT product_name, month, quantity, unit_price FROM budget_sales bs JOIN budgets b ON bs.budget_id=b.id WHERE b.company_id=? AND b.period_id=? ORDER BY bs.id DESC", (company_id, period_id)),
            ['product_name','month','quantity','unit_price']
        ),
    }

    # Determinar último código usado por entidad para continuar la secuencia
    def _last_code(table, col='code'):
        row = qdb(f"SELECT {col} FROM {table} WHERE company_id=? ORDER BY id DESC LIMIT 1", (company_id,), one=True)
        return row[col] if row else None

    last_codes = {
        'resources':         _last_code('resources'),
        'activity_centers':  _last_code('activity_centers'),
        'activities':        _last_code('activities'),
        'cost_objects':      _last_code('cost_objects'),
        'employees':         _last_code('employees'),
        'products':          _last_code('products_services'),
        'inventory_items':   _last_code('inventory_items'),
        'quality_costs':     None,
    }

    def _next_code_hint(entity_key, prefix, num_digits=3):
        last = last_codes.get(entity_key)
        if not last:
            return f"Empieza en {prefix}001"
        # Extraer número del último código
        import re
        m = re.search(r'(\d+)$', last)
        if m:
            n = int(m.group(1)) + 1
            return f"Continúa desde {prefix}{str(n).zfill(num_digits)}"
        return f"Usa prefijo {prefix}"

    # Construir prompt específico por entidad
    prompts = {
        'resources': f"""Eres experto en costos empresariales. Empresa: {company} | Sector: {sector}.
Contexto del usuario: {context}

RECURSOS YA REGISTRADOS EN BD (NO duplicar): {existing['resources']}
{_next_code_hint('resources','REC')}

Genera SOLO los recursos que faltan (complementa lo existente). Responde ÚNICAMENTE con JSON:
{{
  "items": [
    {{"code": "REC001", "name": "Energía eléctrica", "category": "energia", "monthly_amount": 1500.00, "driver_type": "kwh", "notes": "Consumo estimado planta"}},
    ...
  ]
}}
Reglas: no repetir códigos ni nombres ya registrados. Entre 4 y 8 recursos nuevos.
Categorías: energia, personal, depreciacion, materiales, servicios, mantenimiento, seguros, otros
Inductores: kwh, horas_hombre, horas_maquina, m2, m3, unidades, porcentaje, otro""",

        'activity_centers': f"""Experto en costeo ABC. Empresa: {company} | Sector: {sector}.
Contexto: {context}

CENTROS YA REGISTRADOS (NO duplicar): {existing['centers']}
{_next_code_hint('activity_centers','CA')}

Genera centros que faltan. Responde ÚNICAMENTE con JSON:
{{
  "items": [
    {{"code": "CA001", "name": "Centro de Producción Principal", "center_type": "operativo", "notes": "Producción directa"}},
    ...
  ]
}}
3-6 centros nuevos. Tipos: estrategico, operativo, apoyo""",

        'activities': f"""Experto en ABC. Empresa: {company} | Sector: {sector}.
Contexto: {context}

CENTROS DISPONIBLES:
{json.dumps([dict(c) for c in (query_db("SELECT id, code, name FROM activity_centers WHERE company_id=? ORDER BY name", (company_id,)) or [])])}

ACTIVIDADES YA REGISTRADAS (NO duplicar): {existing['activities']}
{_next_code_hint('activities','ACT')}

Genera actividades que faltan. Responde ÚNICAMENTE con JSON:
{{
  "items": [
    {{"code": "ACT001", "name": "Corte de materia prima", "center_id": 1, "driver_type": "horas_maquina", "driver_total": 480, "notes": "Proceso de corte"}},
    ...
  ]
}}
5-10 actividades nuevas distribuidas entre los centros existentes. Usa IDs reales.
Inductores: horas_maquina, horas_hombre, unidades_prod, pedidos, metros, kwh, m3, setup, inspecciones, porcentaje, otro""",

        'cost_objects': f"""Experto en ABC. Empresa: {company} | Sector: {sector}.
Contexto: {context}

PRODUCTOS REGISTRADOS (úsalos como base):
{json.dumps([dict(p) for p in (query_db("SELECT id, code, name FROM products_services WHERE company_id=? AND is_active=1 ORDER BY name", (company_id,)) or [])])}

OBJETOS YA REGISTRADOS (NO duplicar): {existing['objects']}
{_next_code_hint('cost_objects','OC')}

Genera objetos que faltan. Responde ÚNICAMENTE con JSON:
{{
  "items": [
    {{"code": "OC001", "name": "Camisa talla M", "product_id": 1, "quantity_month": 500, "notes": "Producción mensual estimada"}},
    ...
  ]
}}
3-6 objetos nuevos. Vincula a product_id real cuando corresponda.""",

        'kardex': f"""Experto en inventarios. Empresa: {company} | Sector: {sector}.
Contexto: {context}

INVENTARIO ACTUAL (NO duplicar): {existing['inventory']}
PRODUCTOS REGISTRADOS: {existing['products']}
{_next_code_hint('inventory_items','INS')}

Genera ítems de inventario que faltan. Responde ÚNICAMENTE con JSON:
{{
  "items": [
    {{"code": "INS001", "name": "Tela algodón blanca", "category": "insumo", "initial_stock": 500, "initial_cost": 8.50, "valuation_method": "promedio", "safety_stock": 50, "notes": "Principal insumo"}},
    ...
  ]
}}
4-8 ítems nuevos coherentes con el negocio. Categorías: insumo, producto, semielaborado, activo""",

        'quality': f"""Experto en costos de calidad PAF. Empresa: {company} | Sector: {sector}.
Contexto: {context}

ACTIVIDADES YA REGISTRADAS (NO duplicar): {existing['quality']}

Genera actividades PAF que faltan. Responde ÚNICAMENTE con JSON:
{{
  "items": [
    {{"activity_name": "Capacitación en control de calidad", "category": "prevencion", "monthly_cost": 500, "responsible": "Jefe de Producción", "description": "Capacitación mensual al personal"}},
    ...
  ]
}}
6-10 actividades nuevas balanceadas. Categorías: prevencion, evaluacion, falla_interna, falla_externa""",

        'abc_full': f"""Eres experto en costeo ABC. Genera un modelo ABC completo para empresa {sector} - {company}.
Contexto: {context}

Analiza los recursos, centros y actividades ya disponibles. Genera sugerencias de distribución.
Responde SOLO con JSON:
{{
  "resumen": "Descripción del modelo propuesto",
  "recursos_sugeridos": 6,
  "centros_sugeridos": 4,
  "actividades_sugeridas": 8,
  "flujo": "Describe el flujo de distribución de costos",
  "inductores_recomendados": [
    {{"actividad": "Corte", "inductor": "horas_maquina", "razon": "porque..."}},
    ...
  ],
  "pasos": ["Paso 1...", "Paso 2...", "Paso 3..."]
}}""",

        'process_dept': f"""Experto en costos por proceso. Genera departamentos para modelo de proceso de empresa {sector} - {company}.
Contexto: {context}

Responde SOLO con JSON:
{{
  "items": [
    {{
      "name": "Departamento de Tejido",
      "uiipp": 100, "uprod": 900, "uag": 0,
      "utt": 950, "utnt": 0, "uifpp": 50, "up": 0,
      "mat_pct_uiipp": 80, "conv_pct_uiipp": 60,
      "mat_pct_uifpp": 100, "conv_pct_uifpp": 40,
      "cost_mat_prior": 800, "cost_conv_prior": 600,
      "cost_transfer_in": 0,
      "cost_mat_current": 9000, "cost_mod_current": 4500, "cost_cif_current": 1500
    }},
    ...
  ]
}}
Genera 2-4 departamentos con datos coherentes (flujo físico equilibrado).""",

        'budget_base': f"""Experto en presupuestos. Empresa: {company} | Sector: {sector}.
Contexto: {context}

PRODUCTOS disponibles para presupuesto de ventas: {existing['products']}
PERSONAL disponible (para MOD): {existing['employees']}
RECURSOS disponibles (para CIF): {existing['resources']}
VENTAS YA PRESUPUESTADAS (NO duplicar mes/producto): {existing['budget_sales']}

Genera un presupuesto coherente con los datos existentes. Responde ÚNICAMENTE con JSON:
{{
  "ventas": [
    {{"product_name": "Camisa M", "month": 1, "quantity": 500, "unit_price": 85.00}},
    ...
  ],
  "labor": [
    {{"position_name": "Operario MOD", "labor_type": "MOD", "month": 1, "hours_required": 480, "cost_per_hour": 7.03}},
    ...
  ],
  "cif": [
    {{"concept": "Energía eléctrica", "cif_type": "fijo", "month": 1, "amount": 1200}},
    ...
  ]
}}""",

        'cost_structure': f"""Experto en estructuras de costos. Genera una estructura completa para empresa {sector} - {company}.
Contexto: {context}

Responde SOLO con JSON:
{{
  "name": "Estructura Camisa Algodón M",
  "product_service": "Camisa algodón talla M",
  "sale_price": 85.00,
  "monthly_production": 500,
  "categories": [
    {{
      "name": "Materia Prima",
      "category_type": "mp",
      "items": [
        {{"description": "Tela algodón blanca", "unit": "m", "quantity": 1.5, "unit_cost": 9.00, "cost_type": "variable"}},
        ...
      ]
    }},
    {{
      "name": "Mano de Obra Directa",
      "category_type": "mod",
      "items": [
        {{"description": "Operario costura", "unit": "hr", "quantity": 0.5, "unit_cost": 7.03, "cost_type": "variable"}}
      ]
    }},
    {{
      "name": "Costos Indirectos de Fabricación",
      "category_type": "cif",
      "items": [
        {{"description": "Energía eléctrica", "unit": "kwh", "quantity": 0.2, "unit_cost": 0.65, "cost_type": "variable"}}
      ]
    }}
  ]
}}""",

        'employees': f"""Experto en planilla peruana. Empresa: {company} | Sector: {sector}.
Contexto: {context}

PERSONAL YA REGISTRADO (NO duplicar): {existing['employees']}
{_next_code_hint('employees','EMP')}

Genera trabajadores que faltan. Responde ÚNICAMENTE con JSON:
{{"items":[
  {{"code":"EMP001","full_name":"Nombre Apellido","labor_type":"MOD","basic_salary":1200,"available_hours_month":192,"contract_type":"indefinido","notes":"Cargo"}},
  ...
]}}
3-6 trabajadores nuevos. labor_type: MOD, MOI, admin, ventas. Sueldos en soles.""",

        'products': f"""Experto en catálogo de productos. Empresa: {company} | Sector: {sector}.
Contexto: {context}

PRODUCTOS YA REGISTRADOS (NO duplicar): {existing['products']}
{_next_code_hint('products','PROD')}

Genera productos/servicios que faltan. Responde ÚNICAMENTE con JSON:
{{"items":[
  {{"code":"PROD001","name":"Nombre producto","category":"producto","sale_price":85.00,"standard_cost":45.00,"notes":"descripción"}},
  ...
]}}
3-6 productos nuevos. Categorías: producto, servicio, semielaborado. Precios en soles.""",
    }

    if entity not in prompts:
        return jsonify({'success': False, 'error': f'Entidad {entity} no soportada'}), 400

    import json as json_mod

    # Si insert=True y el cliente envía items ya generados, usarlos directamente
    client_items = data.get('items', [])
    if insert and client_items:
        items = client_items
    else:
        # Llamar a la IA para generar
        result = send_message(prompts[entity], agent_type='estructura')

        if not result['success']:
            return jsonify({'success': False, 'error': result['error']})

        # Parsear JSON de la respuesta
        try:
            raw = result['response'].strip()
            if '```' in raw:
                raw = re.sub(r'```json?\s*', '', raw)
                raw = raw.replace('```', '').strip()
            generated = json_mod.loads(raw)

            # abc_full devuelve objeto con resumen/flujo/pasos, no lista items
            if entity == 'abc_full':
                if not insert:
                    return jsonify({'success': True, 'items': generated, 'count': 1})
                items = []
            elif entity in ('budget_base', 'cost_structure'):
                # Estos también devuelven objeto, no lista
                if not insert:
                    return jsonify({'success': True, 'items': generated, 'count': 1})
                items = []
            else:
                items = generated.get('items', [])
                if not items:
                    # Puede que la IA devolvió el array directo sin key 'items'
                    if isinstance(generated, list):
                        items = generated
        except (json_mod.JSONDecodeError, Exception) as e:
            return jsonify({'success': False, 'error': f'IA no devolvió JSON válido: {str(e)}',
                           'raw': result['response'][:500]})

        if not insert:
            return jsonify({'success': True, 'items': items, 'count': len(items)})

    # Insertar en BD
    inserted = 0
    errors_insert = []

    def _num(value, default=0.0):
        """Convierte valores de IA/JS a float, tolerando textos tipo 'S/ 1,200.00'."""
        try:
            if value is None or value == '':
                return default
            if isinstance(value, (int, float)):
                return float(value)
            txt = str(value).strip().replace('S/', '').replace('S', '').replace(',', '')
            return float(txt) if txt else default
        except Exception:
            return default

    def _int(value, default=1):
        try:
            return int(round(_num(value, default)))
        except Exception:
            return default

    def _find_product_id(name, explicit_id=None):
        if explicit_id:
            return explicit_id
        if not name:
            return None
        row = qdb(
            "SELECT id FROM products_services WHERE company_id=? AND LOWER(name)=LOWER(?) LIMIT 1",
            (company_id, str(name).strip()), one=True
        )
        return row['id'] if row else None

    # ── Inserción real de Costos por Proceso generado por IA ─────────────
    # La pantalla mostraba departamentos en preview, pero al insertar no se
    # creaba ningún modelo de proceso ni sus departamentos. Ahora se guarda
    # un modelo completo y se redirige a su edición/resultados.
    if entity == 'process_dept':
        payload = None
        if isinstance(client_items, dict):
            payload = client_items
            departments = payload.get('items') or payload.get('departments') or payload.get('departamentos') or []
        elif isinstance(client_items, list) and len(client_items) == 1 and isinstance(client_items[0], dict) and any(k in client_items[0] for k in ('items', 'departments', 'departamentos')):
            payload = client_items[0]
            departments = payload.get('items') or payload.get('departments') or payload.get('departamentos') or []
        else:
            departments = client_items if isinstance(client_items, list) else items
            payload = {}

        if not departments:
            return jsonify({'success': False, 'error': 'No hay departamentos de proceso para guardar'}), 400

        # Inferir tipo de modelo según los datos generados.
        model_type = (payload.get('model_type') or payload.get('tipo_modelo') or '').strip().lower()
        if model_type not in ('normal', 'agregadas', 'perdidas', 'protecho'):
            has_uag  = any(_num(d.get('uag')) > 0 for d in departments if isinstance(d, dict))
            has_up   = any(_num(d.get('up')) > 0 for d in departments if isinstance(d, dict))
            has_utnt = any(_num(d.get('utnt')) > 0 for d in departments if isinstance(d, dict))
            if has_uag:
                model_type = 'agregadas'
            elif has_up:
                model_type = 'perdidas'
            elif has_utnt:
                model_type = 'protecho'
            else:
                model_type = 'normal'

        name = payload.get('name') or payload.get('nombre') or f"Modelo de Proceso IA - {session.get('period_name', 'Período actual')}"
        product_name = payload.get('product_name') or payload.get('producto') or (context[:120] if context else None)

        mid = execute_db(
            """INSERT INTO process_cost_models
               (company_id, period_id, name, model_type, product_name, status, notes)
               VALUES (?,?,?,?,?,?,?)""",
            (company_id, period_id, name, model_type, product_name,
             'borrador', f"Generado por IA. Contexto: {context[:250]}")
        )

        for order, dept in enumerate(departments, start=1):
            try:
                execute_db(
                    """INSERT INTO process_departments
                       (model_id, dept_order, name,
                        uiipp, uprod, uag, utt, utnt, uifpp, up,
                        mat_pct_uiipp, conv_pct_uiipp, mat_pct_uifpp, conv_pct_uifpp,
                        cost_mat_prior, cost_conv_prior, cost_transfer_in,
                        cost_mat_current, cost_mod_current, cost_cif_current)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (mid, order,
                     dept.get('name') or dept.get('nombre') or f'Departamento {order}',
                     _num(dept.get('uiipp')), _num(dept.get('uprod')),
                     _num(dept.get('uag')), _num(dept.get('utt')),
                     _num(dept.get('utnt')), _num(dept.get('uifpp')),
                     _num(dept.get('up')),
                     _num(dept.get('mat_pct_uiipp')), _num(dept.get('conv_pct_uiipp')),
                     _num(dept.get('mat_pct_uifpp')), _num(dept.get('conv_pct_uifpp')),
                     _num(dept.get('cost_mat_prior')), _num(dept.get('cost_conv_prior')),
                     _num(dept.get('cost_transfer_in')),
                     _num(dept.get('cost_mat_current')), _num(dept.get('cost_mod_current')),
                     _num(dept.get('cost_cif_current')))
                )
                inserted += 1
            except Exception as e:
                errors_insert.append(f"proceso: {e}")

        # Intentar calcular para dejar CU listos. Si hay datos incompletos, igual queda guardado.
        calc_ok = False
        try:
            from services.process_cost_service import calculate_model
            calc = calculate_model(mid)
            calc_ok = bool(calc.get('success'))
        except Exception as e:
            errors_insert.append(f"cálculo: {e}")

        return jsonify({
            'success': True,
            'inserted': inserted,
            'total': len(departments),
            'errors': errors_insert[:3] if errors_insert else [],
            'process_model_id': mid,
            'calculated': calc_ok,
            'redirect': f'/process-costs/{mid}'
        })

    # ── Inserción real de Presupuesto Base generado por IA ───────────────
    # Antes se mostraba el preview, pero al insertar no se creaba ningún
    # presupuesto ni sus subtablas. Por eso al recargar parecía que se borraba.
    if entity == 'budget_base':
        payload = None
        if isinstance(client_items, list) and len(client_items) == 1 and isinstance(client_items[0], dict) and any(k in client_items[0] for k in ('ventas', 'labor', 'cif')):
            payload = client_items[0]
        elif isinstance(client_items, dict):
            payload = client_items
        else:
            # Fallback para versiones anteriores del JS que enviaban filas planas.
            flat = client_items if isinstance(client_items, list) else items
            payload = {
                'ventas': [x for x in flat if str(x.get('_t', '')).lower() in ('venta', 'ventas') or 'product_name' in x],
                'labor':  [x for x in flat if str(x.get('_t', '')).lower() in ('mod', 'labor') or 'position_name' in x],
                'cif':    [x for x in flat if str(x.get('_t', '')).lower() == 'cif' or 'concept' in x],
            }

        name = payload.get('name') or f"Presupuesto IA - {session.get('period_name', 'Período actual')}"
        bid = execute_db(
            "INSERT INTO budgets (company_id, period_id, name, notes) VALUES (?,?,?,?)",
            (company_id, period_id, name, f"Generado por IA. Contexto: {context[:250]}")
        )

        ventas = payload.get('ventas') or payload.get('sales') or []
        labor  = payload.get('labor') or payload.get('mod') or []
        cif    = payload.get('cif') or payload.get('overhead') or []

        for row in ventas:
            try:
                product_name = row.get('product_name') or row.get('producto') or row.get('name') or 'Producto generado por IA'
                qty   = _num(row.get('quantity') or row.get('cantidad'))
                price = _num(row.get('unit_price') or row.get('precio_unitario') or row.get('precio'))
                execute_db(
                    """INSERT INTO budget_sales
                       (budget_id, product_id, product_name, month, quantity, unit_price, total_sales)
                       VALUES (?,?,?,?,?,?,?)""",
                    (bid, _find_product_id(product_name, row.get('product_id')),
                     product_name, _int(row.get('month') or row.get('mes'), 1),
                     qty, price, qty * price)
                )
                inserted += 1
            except Exception as e:
                errors_insert.append(f"ventas: {e}")

        for row in labor:
            try:
                hours = _num(row.get('hours_required') or row.get('horas_requeridas') or row.get('hours'))
                rate  = _num(row.get('cost_per_hour') or row.get('costo_hora') or row.get('rate'))
                execute_db(
                    """INSERT INTO budget_labor
                       (budget_id, employee_id, position_name, labor_type, month,
                        hours_required, cost_per_hour, total_cost)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (bid, row.get('employee_id'),
                     row.get('position_name') or row.get('puesto') or row.get('concept') or 'MOD generado por IA',
                     row.get('labor_type') or 'MOD',
                     _int(row.get('month') or row.get('mes'), 1),
                     hours, rate, hours * rate)
                )
                inserted += 1
            except Exception as e:
                errors_insert.append(f"labor: {e}")

        for row in cif:
            try:
                execute_db(
                    """INSERT INTO budget_cif
                       (budget_id, concept, cif_type, month, amount)
                       VALUES (?,?,?,?,?)""",
                    (bid, row.get('concept') or row.get('concepto') or 'CIF generado por IA',
                     row.get('cif_type') or row.get('tipo') or 'fijo',
                     _int(row.get('month') or row.get('mes'), 1),
                     _num(row.get('amount') or row.get('monto')))
                )
                inserted += 1
            except Exception as e:
                errors_insert.append(f"cif: {e}")

        # Actualiza totales de la tarjeta del presupuesto.
        try:
            from services.budget_service import get_budget_summary
            get_budget_summary(bid)
        except Exception as e:
            errors_insert.append(f"resumen: {e}")

        return jsonify({
            'success': True,
            'inserted': inserted,
            'total': len(ventas) + len(labor) + len(cif),
            'errors': errors_insert[:3] if errors_insert else [],
            'budget_id': bid,
            'redirect': f'/budgets/{bid}'
        })

    # ── Inserción real de Estructura de Costos generada por IA ────────────
    # Antes el backend hacía pass para cost_structure, entonces no se creaban
    # ni la cabecera ni las categorías ni los ítems.
    if entity == 'cost_structure':
        payload = None
        if isinstance(client_items, list) and len(client_items) == 1 and isinstance(client_items[0], dict) and 'categories' in client_items[0]:
            payload = client_items[0]
        elif isinstance(client_items, dict):
            payload = client_items
        else:
            # Fallback para filas planas: agrupar por categoría visual.
            flat = client_items if isinstance(client_items, list) else items
            grouped = {}
            for row in flat:
                cname = row.get('cat') or row.get('category') or 'Costos generados por IA'
                grouped.setdefault(cname, []).append(row)
            payload = {
                'name': 'Estructura generada por IA',
                'product_service': context[:120] if context else 'Producto generado por IA',
                'sale_price': 0,
                'monthly_production': 0,
                'categories': [
                    {'name': cname, 'category_type': '', 'items': rows}
                    for cname, rows in grouped.items()
                ]
            }

        def _category_type(cat):
            raw = (cat.get('category_type') or cat.get('type') or '').strip().lower()
            name = (cat.get('name') or '').strip().lower()
            if raw:
                return raw
            if 'materia' in name or 'prima' in name or name == 'mp':
                return 'mp'
            if 'mano' in name or 'mod' in name or 'obra' in name:
                return 'mod'
            if 'indirect' in name or 'cif' in name:
                return 'cif'
            if 'admin' in name:
                return 'gasto_admin'
            if 'venta' in name:
                return 'gasto_ventas'
            return 'cif'

        from datetime import date
        sid = execute_db(
            """INSERT INTO cost_structures
               (company_id, period_id, name, product_id, product_service,
                structure_date, monthly_production, sale_price, igv_rate,
                desired_margin, origin, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (company_id, period_id,
             payload.get('name') or 'Estructura generada por IA',
             payload.get('product_id') or None,
             payload.get('product_service') or payload.get('producto') or context[:120],
             payload.get('structure_date') or str(date.today()),
             _num(payload.get('monthly_production') or payload.get('produccion_mensual')),
             _num(payload.get('sale_price') or payload.get('precio_venta')),
             _num(payload.get('igv_rate'), 0.18),
             _num(payload.get('desired_margin') or payload.get('margen_deseado')),
             'ia', 'calculado', f"Generado por IA. Contexto: {context[:250]}")
        )

        total_items = 0
        categories = payload.get('categories') or payload.get('categorias') or []
        for cidx, cat in enumerate(categories, start=1):
            try:
                cid = execute_db(
                    "INSERT INTO cost_categories (structure_id, name, category_type, order_index) VALUES (?,?,?,?)",
                    (sid, cat.get('name') or f'Categoría {cidx}', _category_type(cat), cidx)
                )
                for iidx, item in enumerate(cat.get('items') or cat.get('items_costos') or [], start=1):
                    qty = _num(item.get('quantity') or item.get('cantidad'))
                    unit_cost = _num(item.get('unit_cost') or item.get('costo_unitario'))
                    total = _num(item.get('total_cost') or item.get('total'), qty * unit_cost)
                    execute_db(
                        """INSERT INTO cost_items
                           (category_id, description, cost_type, unit, quantity,
                            unit_cost, total_cost, source_cost, notes, order_index)
                           VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (cid,
                         item.get('description') or item.get('descripcion') or item.get('name') or 'Ítem generado por IA',
                         item.get('cost_type') or item.get('tipo_costo') or 'variable',
                         item.get('unit') or item.get('unidad') or '',
                         qty, unit_cost, total, 'ia', item.get('notes') or item.get('notas'), iidx)
                    )
                    inserted += 1
                    total_items += 1
            except Exception as e:
                errors_insert.append(f"estructura: {e}")

        return jsonify({
            'success': True,
            'inserted': inserted,
            'total': total_items,
            'errors': errors_insert[:3] if errors_insert else [],
            'structure_id': sid,
            'redirect': f'/structures/{sid}'
        })

    for item in items:
        try:
            if entity == 'resources':
                execute_db(
                    "INSERT OR IGNORE INTO resources (company_id, period_id, code, name, category, monthly_amount, annual_amount, driver_type, notes) VALUES (?,?,?,?,?,?,?,?,?)",
                    (company_id, period_id, item.get('code',''), item.get('name',''),
                     item.get('category','otros'), float(item.get('monthly_amount',0)),
                     float(item.get('monthly_amount',0))*12,
                     item.get('driver_type'), item.get('notes'))
                )
            elif entity == 'activity_centers':
                execute_db(
                    "INSERT OR IGNORE INTO activity_centers (company_id, period_id, code, name, center_type, notes) VALUES (?,?,?,?,?,?)",
                    (company_id, period_id, item.get('code',''), item.get('name',''),
                     item.get('center_type','operativo'), item.get('notes'))
                )
            elif entity == 'activities':
                execute_db(
                    "INSERT OR IGNORE INTO activities (company_id, center_id, code, name, driver_type, driver_total, notes) VALUES (?,?,?,?,?,?,?)",
                    (company_id, item.get('center_id',1), item.get('code',''), item.get('name',''),
                     item.get('driver_type'), float(item.get('driver_total',0)), item.get('notes'))
                )
            elif entity == 'cost_objects':
                execute_db(
                    "INSERT OR IGNORE INTO cost_objects (company_id, period_id, code, name, product_id, quantity_month, notes) VALUES (?,?,?,?,?,?,?)",
                    (company_id, period_id, item.get('code',''), item.get('name',''),
                     item.get('product_id'), float(item.get('quantity_month',0)), item.get('notes'))
                )
            elif entity == 'kardex':
                from datetime import date
                iid = execute_db(
                    "INSERT OR IGNORE INTO inventory_items (company_id, code, name, category, current_stock, average_cost, safety_stock, valuation_method, is_active) VALUES (?,?,?,?,?,?,?,?,1)",
                    (company_id, item.get('code',''), item.get('name',''),
                     item.get('category','insumo'),
                     float(item.get('initial_stock',0)),
                     float(item.get('initial_cost',0)),
                     float(item.get('safety_stock',0)),
                     item.get('valuation_method','promedio'))
                )
                if iid and float(item.get('initial_stock',0)) > 0:
                    execute_db(
                        "INSERT INTO kardex_movements (inventory_item_id, movement_date, movement_type, quantity, unit_cost, total_cost, stock_after, average_cost_after, reference) VALUES (?,?,?,?,?,?,?,?,?)",
                        (iid, str(date.today()), 'entrada',
                         float(item.get('initial_stock',0)),
                         float(item.get('initial_cost',0)),
                         float(item.get('initial_stock',0)) * float(item.get('initial_cost',0)),
                         float(item.get('initial_stock',0)),
                         float(item.get('initial_cost',0)),
                         'Saldo inicial (generado por IA)')
                    )
            elif entity == 'quality':
                monthly = float(item.get('monthly_cost',0))
                execute_db(
                    "INSERT INTO quality_costs (company_id, period_id, activity_name, description, category, responsible, monthly_cost, annual_cost, ai_classified) VALUES (?,?,?,?,?,?,?,?,1)",
                    (company_id, period_id, item.get('activity_name',''), item.get('description',''),
                     item.get('category','prevencion'), item.get('responsible',''),
                     monthly, monthly*12)
                )
            elif entity == 'employees':
                basic = float(item.get('basic_salary', 0))
                hours = float(item.get('available_hours_month', 192))
                grat  = round(basic / 6, 2)
                cts   = round(basic * 7 / 72, 2)
                ess   = round(basic * 0.09, 2)
                total = round(basic + grat + cts + ess, 2)
                execute_db(
                    'INSERT OR IGNORE INTO employees '
                    '(company_id, code, full_name, basic_salary, '
                    'gratification_monthly, cts_monthly, essalud, '
                    'total_monthly_cost, cost_per_hour, '
                    'available_hours_month, labor_type, contract_type, is_active, in_payroll) '
                    'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1,1)',
                    (company_id,
                     item.get('code', ''), item.get('full_name', ''),
                     basic, grat, cts, ess, total,
                     round(total / hours, 4) if hours else 0,
                     hours, item.get('labor_type', 'MOD'),
                     item.get('contract_type', 'indefinido'))
                )
            elif entity == 'products':
                execute_db(
                    'INSERT OR IGNORE INTO products_services '
                    '(company_id, code, name, category, sale_price, standard_cost, is_active) '
                    'VALUES (?,?,?,?,?,?,1)',
                    (company_id,
                     item.get('code', ''), item.get('name', ''),
                     item.get('category', 'producto'),
                     float(item.get('sale_price', 0)),
                     float(item.get('standard_cost', 0)))
                )
            elif entity in ('abc_full', 'budget_base', 'cost_structure'):
                # Estos tipos generan análisis/guía, no inserción directa simple
                # El frontend mostrará el preview y el usuario decidirá cómo continuar
                pass
            inserted += 1
        except Exception as e:
            errors_insert.append(str(e))

    return jsonify({
        'success': True,
        'inserted': inserted,
        'total': len(items),
        'errors': errors_insert[:3] if errors_insert else [],
        'items': items
    })


import re, json


# ── Upload imagen ───────────────────────────────────────────────────────────

@ai_bp.route('/upload/image', methods=['POST'])
@login_required
def upload_image():
    """Sube una imagen y retorna la ruta."""
    import os
    from werkzeug.utils import secure_filename

    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No se envió imagen'}), 400

    file  = request.files['image']
    if not file.filename:
        return jsonify({'success': False, 'error': 'Nombre de archivo vacío'}), 400

    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in ('png', 'jpg', 'jpeg', 'webp', 'gif'):
        return jsonify({'success': False, 'error': 'Formato no permitido'}), 400

    import uuid
    filename = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, filename))

    return jsonify({'success': True, 'path': f'/static/uploads/{filename}'})


# ── Asignaciones ABC automáticas con IA ───────────────────────────────────

@ai_bp.route('/abc-assign/<int:mid>', methods=['POST'])
@login_required
@company_required
def abc_auto_assign(mid):
    """
    Genera y guarda automáticamente las 3 asignaciones del ABC:
    Recursos→Centros, Centros→Actividades, Actividades→Objetos
    """
    company_id = session['company_id']
    period_id  = session.get('period_id')
    sector     = session.get('sector', '')
    company    = session.get('company_name', '')

    from models.database import query_db as qdb
    from services.abc_service import (save_resource_allocation,
                                       save_center_allocation,
                                       save_object_allocation,
                                       distribute_resources_to_centers,
                                       distribute_centers_to_activities,
                                       distribute_activities_to_objects)

    # Verificar modelo
    model = qdb("SELECT * FROM abc_models WHERE id=? AND company_id=?",
                (mid, company_id), one=True)
    if not model:
        return jsonify({'success': False, 'error': 'Modelo no encontrado'}), 404

    # Leer datos existentes
    resources   = qdb("SELECT id, code, name, category, monthly_amount FROM resources WHERE company_id=? AND (period_id=? OR period_id IS NULL)", (company_id, period_id)) or []
    centers     = qdb("SELECT id, code, name, center_type FROM activity_centers WHERE company_id=?", (company_id,)) or []
    activities  = qdb("SELECT id, code, name, center_id, driver_type, driver_total FROM activities WHERE company_id=?", (company_id,)) or []
    objects     = qdb("SELECT id, code, name, quantity_month FROM cost_objects WHERE company_id=? AND (period_id=? OR period_id IS NULL)", (company_id, period_id)) or []

    if not resources or not centers or not activities or not objects:
        return jsonify({'success': False,
                        'error': 'Necesitas tener Recursos, Centros, Actividades y Objetos registrados antes de asignar.'})

    # Construir prompt para la IA
    prompt = f"""Eres experto en costeo ABC. Empresa: {company} | Sector: {sector}

Genera las asignaciones de los 3 pasos del modelo ABC. Usa SOLO los IDs que te doy.

RECURSOS disponibles:
{json.dumps([dict(r) for r in resources], ensure_ascii=False)}

CENTROS disponibles:
{json.dumps([dict(c) for c in centers], ensure_ascii=False)}

ACTIVIDADES disponibles (ya tienen center_id asignado):
{json.dumps([dict(a) for a in activities], ensure_ascii=False)}

OBJETOS DE COSTO:
{json.dumps([dict(o) for o in objects], ensure_ascii=False)}

Responde ÚNICAMENTE con JSON válido:
{{
  "paso1": [
    {{"resource_id": 1, "center_id": 2, "driver_qty": 500, "razon": "por qué este recurso va a este centro"}},
    ...
  ],
  "paso2": [
    {{"center_id": 2, "activity_id": 3, "driver_qty": 480, "razon": "..."}},
    ...
  ],
  "paso3": [
    {{"activity_id": 3, "object_id": 4, "driver_qty": 200, "razon": "..."}},
    ...
  ]
}}

Reglas:
- Cada recurso debe asignarse a al menos 1 centro
- Cada actividad debe asignarse a al menos 1 objeto
- Los driver_qty deben ser coherentes con las actividades del sector
- Usa los IDs exactos de las listas de arriba"""

    result = send_message(prompt, agent_type='estructura')
    if not result['success']:
        return jsonify({'success': False, 'error': result['error']})

    try:
        raw = result['response'].strip()
        if '```' in raw:
            raw = re.sub(r'```json?\s*', '', raw)
            raw = raw.replace('```', '').strip()
        asignaciones = json.loads(raw)
    except Exception as e:
        return jsonify({'success': False, 'error': f'IA no devolvió JSON válido: {str(e)}',
                        'raw': result['response'][:300]})

    # Guardar asignaciones
    saved = {'paso1': 0, 'paso2': 0, 'paso3': 0}
    errors = []

    for item in asignaciones.get('paso1', []):
        try:
            save_resource_allocation(mid, item['resource_id'], item['center_id'], item['driver_qty'])
            saved['paso1'] += 1
        except Exception as e:
            errors.append(f'paso1: {e}')

    distribute_resources_to_centers(mid)

    for item in asignaciones.get('paso2', []):
        try:
            save_center_allocation(mid, item['center_id'], item['activity_id'], item['driver_qty'])
            saved['paso2'] += 1
        except Exception as e:
            errors.append(f'paso2: {e}')

    distribute_centers_to_activities(mid)

    for item in asignaciones.get('paso3', []):
        try:
            save_object_allocation(mid, item['activity_id'], item['object_id'], item['driver_qty'])
            saved['paso3'] += 1
        except Exception as e:
            errors.append(f'paso3: {e}')

    distribute_activities_to_objects(mid)

    return jsonify({
        'success':  True,
        'saved':    saved,
        'errors':   errors[:5],
        'message':  f"Asignaciones guardadas: {saved['paso1']} recursos→centros, {saved['paso2']} centros→actividades, {saved['paso3']} actividades→objetos"
    })
