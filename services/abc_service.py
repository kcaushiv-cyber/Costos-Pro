"""
Motor de cálculo ABC — Costos Pro v5
Lógica basada en el Excel 2024_1__UNI_COSTOS_ABC_TEXTIL.xlsx
Ruta: Recursos → Centros de Actividad → Actividades → Objetos de Costo
"""
from models.database import query_db, execute_db


def _safe(v):
    return float(v) if v else 0.0


# ── NIVEL 1→2: Recursos → Centros de Actividad ────────────────────────────

def distribute_resources_to_centers(model_id: int) -> dict:
    """
    Lee las asignaciones Resource→Center del modelo ABC
    y calcula los montos distribuidos.
    Retorna resumen por centro.
    """
    allocs = query_db(
        """SELECT ara.*, r.monthly_amount, r.code as res_code,
                  ac.code as center_code, ac.name as center_name
           FROM abc_resource_allocations ara
           JOIN resources r ON ara.resource_id = r.id
           JOIN activity_centers ac ON ara.center_id = ac.id
           WHERE ara.abc_model_id = ?""",
        (model_id,)
    )

    center_totals = {}
    for a in allocs:
        cid = a['center_id']
        amt = _safe(a['allocated_amount'])
        if cid not in center_totals:
            center_totals[cid] = {
                'center_id': cid,
                'center_name': a['center_name'],
                'total': 0.0,
            }
        center_totals[cid]['total'] += amt

    # Actualizar total en activity_centers
    for cid, data in center_totals.items():
        execute_db(
            "UPDATE activity_centers SET total_cost_monthly=? WHERE id=?",
            (data['total'], cid)
        )

    return center_totals


# ── NIVEL 2→3: Centros → Actividades ──────────────────────────────────────

def distribute_centers_to_activities(model_id: int) -> dict:
    allocs = query_db(
        """SELECT aca.*, ac.total_cost_monthly as center_total,
                  a.code as act_code, a.name as act_name
           FROM abc_center_allocations aca
           JOIN activity_centers ac ON aca.center_id = ac.id
           JOIN activities a ON aca.activity_id = a.id
           WHERE aca.abc_model_id = ?""",
        (model_id,)
    )

    act_totals = {}
    for a in allocs:
        aid = a['activity_id']
        amt = _safe(a['allocated_amount'])
        if aid not in act_totals:
            act_totals[aid] = {'activity_id': aid, 'name': a['act_name'], 'total': 0.0}
        act_totals[aid]['total'] += amt

    for aid, data in act_totals.items():
        execute_db("UPDATE activities SET total_cost=? WHERE id=?",
                   (data['total'], aid))

    return act_totals


# ── NIVEL 3→4: Actividades → Objetos de Costo ─────────────────────────────

def distribute_activities_to_objects(model_id: int) -> dict:
    allocs = query_db(
        """SELECT aoa.*, a.total_cost as act_total,
                  co.name as obj_name
           FROM abc_object_allocations aoa
           JOIN activities a ON aoa.activity_id = a.id
           JOIN cost_objects co ON aoa.cost_object_id = co.id
           WHERE aoa.abc_model_id = ?""",
        (model_id,)
    )

    obj_totals = {}
    for a in allocs:
        oid = a['cost_object_id']
        amt = _safe(a['allocated_amount'])
        if oid not in obj_totals:
            obj_totals[oid] = {'cost_object_id': oid, 'name': a['obj_name'], 'total': 0.0}
        obj_totals[oid]['total'] += amt

    return obj_totals


# ── CÁLCULO FINAL: estructura de costos por objeto ─────────────────────────

def calculate_abc_results(model_id: int) -> list:
    """
    Calcula el resultado final ABC para cada objeto de costo.
    Incluye: costo producción + gastos + margen + IGV → precio de venta.
    """
    model = query_db("SELECT * FROM abc_models WHERE id=?", (model_id,), one=True)
    if not model:
        return []

    # Mantener los montos de todos los niveles sincronizados antes de calcular.
    recalculate_model_allocations(model_id)

    # Limpiar resultados anteriores para evitar resultados obsoletos si se eliminaron asignaciones.
    execute_db("DELETE FROM abc_results WHERE abc_model_id=?", (model_id,))

    # Antes de recalcular, limpiar el costo ABC visible de los objetos del período.
    # Así la pantalla Objetos de Costo no muestra valores antiguos si una asignación se eliminó.
    execute_db(
        """UPDATE cost_objects
           SET unit_cost_abc=0
           WHERE company_id=? AND (period_id=? OR period_id IS NULL)""",
        (model['company_id'], model['period_id'])
    )

    # Obtener costos de producción por objeto
    obj_prod = distribute_activities_to_objects(model_id)

    # Obtener objetos con cantidad y precio
    objects = query_db(
        """SELECT co.*, ps.sale_price as catalog_price
           FROM cost_objects co
           LEFT JOIN products_services ps ON co.product_id = ps.id
           WHERE co.id IN ({})""".format(
            ','.join(str(k) for k in obj_prod.keys()) if obj_prod else '0'
        )
    )

    # Total producción para prorratear gastos
    total_prod = sum(d['total'] for d in obj_prod.values())
    admin_pct  = _safe(model['admin_expense'])
    sales_pct  = _safe(model['sales_expense'])
    fin_pct    = _safe(model['financial_expense'])
    margin_pct = _safe(model['desired_margin'])
    igv_rate   = 0.18

    results = []
    for obj in [dict(o) for o in objects]:
        oid       = obj['id']
        qty       = _safe(obj['quantity_month']) or 1
        prod_cost = obj_prod.get(oid, {}).get('total', 0.0)

        # Prorrateo de gastos indirectos sobre costo de producción
        admin_amt = prod_cost * (admin_pct / 100)
        sales_amt = prod_cost * (sales_pct / 100)
        fin_amt   = prod_cost * (fin_pct   / 100)
        total     = prod_cost + admin_amt + sales_amt + fin_amt

        # Precio de venta con margen e IGV
        margin_amt  = total * (margin_pct / 100)
        sale_value  = total + margin_amt
        igv_amt     = sale_value * igv_rate
        sale_price  = sale_value + igv_amt

        unit_cost_abc = total / qty if qty else 0
        unit_cost_trad = _safe(obj.get('unit_cost_traditional') or obj.get('catalog_price') or 0)

        # Upsert en abc_results
        existing = query_db(
            "SELECT id FROM abc_results WHERE abc_model_id=? AND cost_object_id=?",
            (model_id, oid), one=True
        )
        data = (prod_cost, admin_amt, sales_amt, fin_amt,
                total, margin_amt, sale_value, igv_amt,
                sale_price, unit_cost_abc, unit_cost_trad)

        if existing:
            execute_db(
                """UPDATE abc_results SET
                   production_cost=?, admin_expense_allocated=?, sales_expense_allocated=?,
                   financial_expense_allocated=?, total_cost=?, margin_amount=?,
                   sale_value=?, igv_amount=?, sale_price=?,
                   unit_cost_abc=?, unit_cost_traditional=?
                   WHERE id=?""",
                (*data, existing['id'])
            )
        else:
            execute_db(
                """INSERT INTO abc_results
                   (abc_model_id, cost_object_id,
                    production_cost, admin_expense_allocated, sales_expense_allocated,
                    financial_expense_allocated, total_cost, margin_amount,
                    sale_value, igv_amount, sale_price,
                    unit_cost_abc, unit_cost_traditional)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (model_id, oid, *data)
            )

        # Sincronizar la tabla maestra para que /cost-objects muestre el costo ABC calculado.
        execute_db(
            """UPDATE cost_objects
               SET unit_cost_abc=?, unit_cost_traditional=?
               WHERE id=?""",
            (unit_cost_abc, unit_cost_trad, oid)
        )

        results.append({
            'object_id':     oid,
            'name':          obj['name'],
            'quantity':      qty,
            'production_cost': prod_cost,
            'admin_expense': admin_amt,
            'sales_expense': sales_amt,
            'fin_expense':   fin_amt,
            'total_cost':    total,
            'margin_amount': margin_amt,
            'sale_value':    sale_value,
            'igv_amount':    igv_amt,
            'sale_price':    sale_price,
            'unit_cost_abc': unit_cost_abc,
            'unit_cost_traditional': unit_cost_trad,
            'diff_pct': ((unit_cost_abc - unit_cost_trad) / unit_cost_trad * 100) if unit_cost_trad else 0,
        })

    # Marcar modelo como calculado
    execute_db("UPDATE abc_models SET status='calculado', calculated_at=CURRENT_TIMESTAMP WHERE id=?",
               (model_id,))

    return results


# ── Helpers para tablas de distribución ───────────────────────────────────

def save_resource_allocation(model_id, resource_id, center_id, driver_qty):
    """Guarda o actualiza una asignación Recurso→Centro."""
    resource = query_db("SELECT monthly_amount FROM resources WHERE id=?",
                        (resource_id,), one=True)
    if not resource:
        return False

    # Calcular total del inductor para este recurso en el modelo
    all_allocs = query_db(
        "SELECT SUM(driver_quantity) as total FROM abc_resource_allocations WHERE abc_model_id=? AND resource_id=?",
        (model_id, resource_id), one=True
    )
    current_total = _safe(all_allocs['total']) if all_allocs else 0

    # Obtener asignación existente para no duplicar
    existing = query_db(
        "SELECT id, driver_quantity FROM abc_resource_allocations WHERE abc_model_id=? AND resource_id=? AND center_id=?",
        (model_id, resource_id, center_id), one=True
    )
    old_qty = _safe(existing['driver_quantity']) if existing else 0
    new_total_driver = current_total - old_qty + _safe(driver_qty)

    allocated = 0.0
    driver_pct = 0.0
    if new_total_driver > 0:
        driver_pct = _safe(driver_qty) / new_total_driver * 100
        allocated  = _safe(resource['monthly_amount']) * driver_pct / 100

    if existing:
        execute_db(
            "UPDATE abc_resource_allocations SET driver_quantity=?, driver_percentage=?, allocated_amount=? WHERE id=?",
            (_safe(driver_qty), driver_pct, allocated, existing['id'])
        )
    else:
        execute_db(
            """INSERT INTO abc_resource_allocations
               (abc_model_id, resource_id, center_id, driver_quantity, driver_percentage, allocated_amount)
               VALUES (?,?,?,?,?,?)""",
            (model_id, resource_id, center_id, _safe(driver_qty), driver_pct, allocated)
        )

    # Recalcular porcentajes de todas las asignaciones de este recurso
    _recalculate_resource_alloc(model_id, resource_id)
    return True


def save_center_allocation(model_id, center_id, activity_id, driver_qty):
    # Asegura que el centro tenga su costo actualizado antes de calcular %
    _refresh_center_total(model_id, center_id)

    existing = query_db(
        "SELECT id FROM abc_center_allocations WHERE abc_model_id=? AND center_id=? AND activity_id=?",
        (model_id, center_id, activity_id), one=True
    )
    if existing:
        execute_db(
            "UPDATE abc_center_allocations SET driver_quantity=? WHERE id=?",
            (_safe(driver_qty), existing['id'])
        )
    else:
        execute_db(
            """INSERT INTO abc_center_allocations
               (abc_model_id, center_id, activity_id, driver_quantity, driver_percentage, allocated_amount)
               VALUES (?,?,?,?,0,0)""",
            (model_id, center_id, activity_id, _safe(driver_qty))
        )
    _recalculate_center_alloc(model_id, center_id)
    return True


def save_object_allocation(model_id, activity_id, cost_object_id, driver_qty):
    # Asegura que la actividad tenga su costo actualizado antes de calcular %
    _refresh_activity_total(model_id, activity_id)

    existing = query_db(
        "SELECT id FROM abc_object_allocations WHERE abc_model_id=? AND activity_id=? AND cost_object_id=?",
        (model_id, activity_id, cost_object_id), one=True
    )
    if existing:
        execute_db(
            "UPDATE abc_object_allocations SET driver_quantity=? WHERE id=?",
            (_safe(driver_qty), existing['id'])
        )
    else:
        execute_db(
            """INSERT INTO abc_object_allocations
               (abc_model_id, activity_id, cost_object_id, driver_quantity, driver_percentage, allocated_amount)
               VALUES (?,?,?,?,0,0)""",
            (model_id, activity_id, cost_object_id, _safe(driver_qty))
        )
    _recalculate_object_alloc(model_id, activity_id)
    return True


def _recalculate_resource_alloc(model_id, resource_id):
    """Recalcula % y monto de todas las filas de un recurso en el modelo."""
    resource = query_db("SELECT monthly_amount FROM resources WHERE id=?",
                        (resource_id,), one=True)
    if not resource:
        return
    allocs = query_db(
        "SELECT id, driver_quantity FROM abc_resource_allocations WHERE abc_model_id=? AND resource_id=?",
        (model_id, resource_id)
    )
    total_driver = sum(_safe(a['driver_quantity']) for a in allocs)
    if total_driver == 0:
        return
    monthly = _safe(resource['monthly_amount'])
    for a in allocs:
        pct = _safe(a['driver_quantity']) / total_driver * 100
        amt = monthly * pct / 100
        execute_db(
            "UPDATE abc_resource_allocations SET driver_percentage=?, allocated_amount=? WHERE id=?",
            (pct, amt, a['id'])
        )


def _recalculate_center_alloc(model_id, center_id):
    center = query_db("SELECT total_cost_monthly FROM activity_centers WHERE id=?",
                      (center_id,), one=True)
    if not center:
        return
    allocs = query_db(
        "SELECT id, driver_quantity FROM abc_center_allocations WHERE abc_model_id=? AND center_id=?",
        (model_id, center_id)
    )
    total_driver = sum(_safe(a['driver_quantity']) for a in allocs)
    if total_driver == 0:
        return
    monthly = _safe(center['total_cost_monthly'])
    for a in allocs:
        pct = _safe(a['driver_quantity']) / total_driver * 100
        amt = monthly * pct / 100
        execute_db(
            "UPDATE abc_center_allocations SET driver_percentage=?, allocated_amount=? WHERE id=?",
            (pct, amt, a['id'])
        )


def _recalculate_object_alloc(model_id, activity_id):
    activity = query_db("SELECT total_cost FROM activities WHERE id=?",
                        (activity_id,), one=True)
    if not activity:
        return
    allocs = query_db(
        "SELECT id, driver_quantity FROM abc_object_allocations WHERE abc_model_id=? AND activity_id=?",
        (model_id, activity_id)
    )
    total_driver = sum(_safe(a['driver_quantity']) for a in allocs)
    if total_driver == 0:
        return
    act_cost = _safe(activity['total_cost'])
    for a in allocs:
        pct = _safe(a['driver_quantity']) / total_driver * 100
        amt = act_cost * pct / 100
        execute_db(
            "UPDATE abc_object_allocations SET driver_percentage=?, allocated_amount=? WHERE id=?",
            (pct, amt, a['id'])
        )



def _refresh_center_total(model_id, center_id):
    """Actualiza el costo mensual de un centro con lo asignado en el modelo."""
    row = query_db(
        """SELECT SUM(allocated_amount) as total
           FROM abc_resource_allocations
           WHERE abc_model_id=? AND center_id=?""",
        (model_id, center_id), one=True
    )
    execute_db(
        "UPDATE activity_centers SET total_cost_monthly=? WHERE id=?",
        (_safe(row['total']) if row else 0.0, center_id)
    )


def _refresh_activity_total(model_id, activity_id):
    """Actualiza el costo de una actividad con lo asignado desde centros."""
    row = query_db(
        """SELECT SUM(allocated_amount) as total
           FROM abc_center_allocations
           WHERE abc_model_id=? AND activity_id=?""",
        (model_id, activity_id), one=True
    )
    execute_db(
        "UPDATE activities SET total_cost=? WHERE id=?",
        (_safe(row['total']) if row else 0.0, activity_id)
    )


def _recalculate_all_center_allocs(model_id):
    centers = query_db(
        "SELECT DISTINCT center_id FROM abc_center_allocations WHERE abc_model_id=?",
        (model_id,)
    )
    for c in centers:
        _recalculate_center_alloc(model_id, c['center_id'])


def _recalculate_all_object_allocs(model_id):
    activities = query_db(
        "SELECT DISTINCT activity_id FROM abc_object_allocations WHERE abc_model_id=?",
        (model_id,)
    )
    for a in activities:
        _recalculate_object_alloc(model_id, a['activity_id'])


def recalculate_model_allocations(model_id):
    """Recalcula porcentajes/montos guardados en los 3 niveles del modelo."""
    distribute_resources_to_centers(model_id)
    _recalculate_all_center_allocs(model_id)
    distribute_centers_to_activities(model_id)
    _recalculate_all_object_allocs(model_id)
    return True


def delete_resource_allocation(model_id, allocation_id):
    alloc = query_db(
        """SELECT id, resource_id, center_id
           FROM abc_resource_allocations
           WHERE id=? AND abc_model_id=?""",
        (allocation_id, model_id), one=True
    )
    if not alloc:
        return False
    resource_id = alloc['resource_id']
    center_id = alloc['center_id']
    execute_db("DELETE FROM abc_resource_allocations WHERE id=?", (allocation_id,))
    _recalculate_resource_alloc(model_id, resource_id)
    distribute_resources_to_centers(model_id)
    _refresh_center_total(model_id, center_id)
    recalculate_model_allocations(model_id)
    return True


def delete_center_allocation(model_id, allocation_id):
    alloc = query_db(
        """SELECT id, center_id, activity_id
           FROM abc_center_allocations
           WHERE id=? AND abc_model_id=?""",
        (allocation_id, model_id), one=True
    )
    if not alloc:
        return False
    center_id = alloc['center_id']
    activity_id = alloc['activity_id']
    execute_db("DELETE FROM abc_center_allocations WHERE id=?", (allocation_id,))
    _recalculate_center_alloc(model_id, center_id)
    distribute_centers_to_activities(model_id)
    _refresh_activity_total(model_id, activity_id)
    _recalculate_object_alloc(model_id, activity_id)
    return True


def delete_object_allocation(model_id, allocation_id):
    alloc = query_db(
        """SELECT id, activity_id, cost_object_id
           FROM abc_object_allocations
           WHERE id=? AND abc_model_id=?""",
        (allocation_id, model_id), one=True
    )
    if not alloc:
        return False
    activity_id = alloc['activity_id']
    object_id = alloc['cost_object_id']
    execute_db("DELETE FROM abc_object_allocations WHERE id=?", (allocation_id,))
    _recalculate_object_alloc(model_id, activity_id)
    execute_db("DELETE FROM abc_results WHERE abc_model_id=? AND cost_object_id=?", (model_id, object_id))
    return True

def get_model_summary(model_id: int) -> dict:
    """Resumen rápido del estado del modelo ABC."""
    res_count = query_db(
        "SELECT COUNT(DISTINCT resource_id) as n FROM abc_resource_allocations WHERE abc_model_id=?",
        (model_id,), one=True
    )
    cen_count = query_db(
        "SELECT COUNT(DISTINCT center_id) as n FROM abc_center_allocations WHERE abc_model_id=?",
        (model_id,), one=True
    )
    act_count = query_db(
        "SELECT COUNT(DISTINCT activity_id) as n FROM abc_object_allocations WHERE abc_model_id=?",
        (model_id,), one=True
    )
    obj_count = query_db(
        "SELECT COUNT(*) as n FROM abc_results WHERE abc_model_id=?",
        (model_id,), one=True
    )
    return {
        'resources_assigned': res_count['n'] if res_count else 0,
        'centers_assigned':   cen_count['n'] if cen_count else 0,
        'activities_assigned':act_count['n'] if act_count else 0,
        'objects_calculated': obj_count['n'] if obj_count else 0,
    }
