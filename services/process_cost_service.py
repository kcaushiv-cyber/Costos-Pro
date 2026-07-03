"""
Motor de Costos por Proceso — Costos Pro v5
4 modelos según notación Dr. Lujan Campos (FIIS-UNI):
  1. Normal          — sin pérdidas, sin unidades agregadas
  2. Agregadas       — con UAg (unidades agregadas en proceso)
  3. Perdidas        — con UP (unidades perdidas / merma)
  4. PROTECHO        — con unidades terminadas no transferidas (UTNT)

Notación estándar:
  UIIPP  — Unidades iniciales en proceso al principio del período
  UPROD  — Unidades iniciadas/recibidas en el período
  UAg    — Unidades agregadas durante el proceso
  UTT    — Unidades terminadas y transferidas
  UTNT   — Unidades terminadas no transferidas
  UIFPP  — Unidades finales en proceso al final del período
  UP     — Unidades perdidas (merma)
  UE     — Unidades equivalentes
"""

from models.database import query_db, execute_db


def _safe(v):
    return float(v) if v else 0.0


# ── Verificación del flujo físico ─────────────────────────────────────────

def verify_physical_flow(dept: dict, model_type: str) -> dict:
    """
    Verifica que: Unidades por Contabilizar = Unidades Contabilizadas
    Returns dict con los totales y si hay error.
    """
    uiipp = _safe(dept.get('uiipp'))
    uprod = _safe(dept.get('uprod'))
    uag   = _safe(dept.get('uag'))
    utt   = _safe(dept.get('utt'))
    utnt  = _safe(dept.get('utnt'))
    uifpp = _safe(dept.get('uifpp'))
    up    = _safe(dept.get('up'))

    # Unidades por contabilizar (entradas)
    por_contabilizar = uiipp + uprod + uag

    # Unidades contabilizadas (salidas)
    contabilizadas = utt + utnt + uifpp + up

    balance = round(por_contabilizar - contabilizadas, 4)
    ok = abs(balance) < 0.001

    return {
        'uiipp': uiipp, 'uprod': uprod, 'uag': uag,
        'utt': utt, 'utnt': utnt, 'uifpp': uifpp, 'up': up,
        'por_contabilizar': por_contabilizar,
        'contabilizadas': contabilizadas,
        'balance': balance,
        'ok': ok,
        'error': None if ok else f'Desequilibrio: {balance:+.4f} unidades',
    }


# ── Cálculo de Unidades Equivalentes ──────────────────────────────────────

def calc_ue(dept: dict, model_type: str) -> dict:
    """
    Calcula UE de materiales y conversión según el modelo.
    Fórmulas UNI:
      UE_mat  = UTT + UTNT + UIFPP×%_mat_uifpp  - UIIPP×%_mat_uiipp
      UE_conv = UTT + UTNT + UIFPP×%_conv_uifpp - UIIPP×%_conv_uiipp
    En modelos con pérdidas las UP se restan de UTT antes de calcular.
    """
    uiipp  = _safe(dept.get('uiipp'))
    uprod  = _safe(dept.get('uprod'))
    utt    = _safe(dept.get('utt'))
    utnt   = _safe(dept.get('utnt'))
    uifpp  = _safe(dept.get('uifpp'))
    up     = _safe(dept.get('up'))

    mat_uiipp  = _safe(dept.get('mat_pct_uiipp'))  / 100
    conv_uiipp = _safe(dept.get('conv_pct_uiipp')) / 100
    mat_uifpp  = _safe(dept.get('mat_pct_uifpp'))  / 100
    conv_uifpp = _safe(dept.get('conv_pct_uifpp')) / 100

    # Base de UTT para UE (en modelos con pérdidas, UP absorbe su propio costo)
    base_utt = utt - up if model_type == 'perdidas' else utt

    ue_mat  = base_utt + utnt + uifpp * mat_uifpp  - uiipp * mat_uiipp
    ue_conv = base_utt + utnt + uifpp * conv_uifpp - uiipp * conv_uiipp

    return {
        'ue_mat':  round(max(ue_mat,  0), 4),
        'ue_conv': round(max(ue_conv, 0), 4),
    }


# ── Cálculo de Costos Unitarios ────────────────────────────────────────────

def calc_unit_costs(dept: dict, ue: dict) -> dict:
    """
    Calcula CU de materiales y conversión.
    CU_mat  = (Costo_mat_anterior + Costo_mat_actual)  / UE_mat
    CU_conv = (Costo_conv_anterior + Costo_conv_actual) / UE_conv
    CU_total = CU_mat + CU_conv
    Nota: en departamentos 2+ se agrega el costo transferido del dpto anterior.
    """
    cost_mat  = _safe(dept.get('cost_mat_prior'))  + _safe(dept.get('cost_mat_current'))
    cost_conv = (_safe(dept.get('cost_conv_prior')) +
                 _safe(dept.get('cost_mod_current')) +
                 _safe(dept.get('cost_cif_current')))
    cost_transfer = _safe(dept.get('cost_transfer_in'))

    ue_mat  = ue['ue_mat']
    ue_conv = ue['ue_conv']

    cu_mat  = cost_mat  / ue_mat  if ue_mat  > 0 else 0
    cu_conv = cost_conv / ue_conv if ue_conv > 0 else 0
    cu_transfer = cost_transfer / (ue_mat + ue_conv) if (ue_mat + ue_conv) > 0 else 0

    cu_total = cu_mat + cu_conv + (cu_transfer if cost_transfer > 0 else 0)

    return {
        'cost_mat':      round(cost_mat,  2),
        'cost_conv':     round(cost_conv, 2),
        'cost_transfer': round(cost_transfer, 2),
        'cu_mat':        round(cu_mat,      4),
        'cu_conv':       round(cu_conv,     4),
        'cu_transfer':   round(cu_transfer, 4),
        'cu_total':      round(cu_total,    4),
    }


# ── Asignación de costos a las salidas ────────────────────────────────────

def assign_costs(dept: dict, ue: dict, cu: dict, model_type: str) -> dict:
    """
    Asigna el costo total calculado a cada destino:
      - UTT  (transferidas al siguiente dpto o al almacén)
      - UTNT (terminadas que quedan en este dpto)
      - UIFPP (en proceso al cierre)
      - UP   (unidades perdidas — solo en modelo 'perdidas')
    """
    utt    = _safe(dept.get('utt'))
    utnt   = _safe(dept.get('utnt'))
    uifpp  = _safe(dept.get('uifpp'))
    up     = _safe(dept.get('up'))
    mat_uifpp  = _safe(dept.get('mat_pct_uifpp'))  / 100
    conv_uifpp = _safe(dept.get('conv_pct_uifpp')) / 100

    cu_mat   = cu['cu_mat']
    cu_conv  = cu['cu_conv']
    cu_total = cu['cu_total']

    # Costo UTT (precio pleno)
    costo_utt = utt * cu_total

    # Costo UTNT
    costo_utnt = utnt * cu_total

    # Costo UIFPP (ponderado por % de avance)
    costo_uifpp_mat  = uifpp * mat_uifpp  * cu_mat
    costo_uifpp_conv = uifpp * conv_uifpp * cu_conv
    costo_uifpp      = costo_uifpp_mat + costo_uifpp_conv

    # Costo UP (en modelos con pérdidas se prorratea entre UTT)
    costo_up = 0.0
    if model_type == 'perdidas' and up > 0:
        costo_up = up * cu_total
        # Se distribuye al costo de UTT
        costo_utt += costo_up

    total_asignado = costo_utt + costo_utnt + costo_uifpp

    return {
        'costo_utt':    round(costo_utt,    2),
        'costo_utnt':   round(costo_utnt,   2),
        'costo_uifpp':  round(costo_uifpp,  2),
        'costo_up':     round(costo_up,     2),
        'total_asignado': round(total_asignado, 2),
        'costo_unit_utt':  round(costo_utt / utt  if utt  > 0 else 0, 4),
        'costo_unit_utnt': round(costo_utnt / utnt if utnt > 0 else 0, 4),
    }


# ── Cálculo completo de un modelo ─────────────────────────────────────────

def calculate_model(model_id: int) -> dict:
    """
    Calcula todos los departamentos de un modelo de costos por proceso.
    Retorna lista de resultados por departamento.
    """
    model = query_db("SELECT * FROM process_cost_models WHERE id=?", (model_id,), one=True)
    if not model:
        return {'success': False, 'error': 'Modelo no encontrado'}

    departments = query_db(
        "SELECT * FROM process_departments WHERE model_id=? ORDER BY dept_order",
        (model_id,)
    )
    if not departments:
        return {'success': False, 'error': 'Sin departamentos definidos'}

    model_type = model['model_type']
    results    = []
    prev_transfer_cost = 0.0  # Costo transferido del dpto anterior

    for dept in departments:
        dept_dict = dict(dept)

        # Agregar costo transferido del departamento anterior
        if dept['dept_order'] > 1:
            dept_dict['cost_transfer_in'] = prev_transfer_cost

        # 1. Verificar flujo físico
        flow = verify_physical_flow(dept_dict, model_type)

        # 2. Calcular UE
        ue = calc_ue(dept_dict, model_type)

        # 3. Calcular costos unitarios
        cu = calc_unit_costs(dept_dict, ue)

        # 4. Asignar costos a salidas
        asign = assign_costs(dept_dict, ue, cu, model_type)

        # Guardar en BD
        execute_db(
            """UPDATE process_departments SET
               ue_mat=?, ue_conv=?,
               cu_mat=?, cu_conv=?, cu_total=?
               WHERE id=?""",
            (ue['ue_mat'], ue['ue_conv'],
             cu['cu_mat'], cu['cu_conv'], cu['cu_total'],
             dept['id'])
        )

        result = {
            'dept_id':    dept['id'],
            'dept_order': dept['dept_order'],
            'name':       dept['name'],
            'flow':       flow,
            'ue':         ue,
            'cu':         cu,
            'asign':      asign,
        }
        results.append(result)

        # El costo transferido al siguiente dpto es el costo de las UTT
        prev_transfer_cost = asign['costo_utt']

    # Marcar modelo como calculado
    execute_db(
        "UPDATE process_cost_models SET status='calculado', calculated_at=CURRENT_TIMESTAMP WHERE id=?",
        (model_id,)
    )

    return {'success': True, 'model_type': model_type, 'results': results}


def get_model_with_departments(model_id: int) -> dict:
    model = query_db("SELECT * FROM process_cost_models WHERE id=?", (model_id,), one=True)
    if not model:
        return None
    depts = query_db(
        "SELECT * FROM process_departments WHERE model_id=? ORDER BY dept_order",
        (model_id,)
    )
    return {'model': dict(model), 'departments': [dict(d) for d in depts]}
