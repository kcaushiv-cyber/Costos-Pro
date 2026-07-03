"""
Servicio de Presupuestos — Costos Pro v5
Basado en 2025_2_CCP_PROBLEMA_DE_PRESUPUESTO.xlsx y
2019_1_UNI_CP_SOLUCION_PRESUPUESTO_EMPRESA_MANUFACTURERA.xlsx
"""
from models.database import query_db, execute_db


def _safe(v):
    return float(v) if v else 0.0


def get_budget_summary(budget_id: int) -> dict:
    """Calcula los totales del presupuesto desde sus subsecciones."""
    sales = query_db(
        "SELECT SUM(total_sales) as total FROM budget_sales WHERE budget_id=?",
        (budget_id,), one=True
    )
    labor = query_db(
        "SELECT SUM(total_cost) as total FROM budget_labor WHERE budget_id=?",
        (budget_id,), one=True
    )
    cif = query_db(
        "SELECT SUM(amount) as total FROM budget_cif WHERE budget_id=?",
        (budget_id,), one=True
    )
    production = query_db(
        "SELECT SUM(required_production) as total FROM budget_production WHERE budget_id=?",
        (budget_id,), one=True
    )

    total_sales  = _safe(sales['total'] if sales else 0)
    total_labor  = _safe(labor['total'] if labor else 0)
    total_cif    = _safe(cif['total']   if cif   else 0)
    total_prod   = _safe(production['total'] if production else 0)

    # Costo de ventas estimado = labor + CIF (simplificado sin MP)
    total_cost   = total_labor + total_cif
    gross_profit = total_sales - total_cost
    net_income   = gross_profit  # sin impuestos en este modelo

    # Actualizar budget
    execute_db(
        """UPDATE budgets SET
           total_sales=?, total_production_cost=?,
           gross_profit=?, net_income=?
           WHERE id=?""",
        (total_sales, total_cost, gross_profit, net_income, budget_id)
    )

    return {
        'total_sales':    round(total_sales, 2),
        'total_labor':    round(total_labor, 2),
        'total_cif':      round(total_cif,   2),
        'total_cost':     round(total_cost,  2),
        'gross_profit':   round(gross_profit, 2),
        'net_income':     round(net_income,   2),
        'margin_pct':     round((gross_profit / total_sales * 100) if total_sales else 0, 1),
        'total_prod_units': round(total_prod, 0),
    }


def calculate_cashflow(budget_id: int) -> list:
    """
    Genera el flujo de caja mensual (12 meses) a partir de
    ventas, labor, CIF y servicio de deuda registrados.
    Retorna lista de 12 dicts con los saldos mensuales.
    """
    # Limpiar cashflow anterior
    execute_db("DELETE FROM budget_cashflow WHERE budget_id=?", (budget_id,))

    prev_balance = 0.0
    rows = []

    for month in range(1, 13):
        # Ingresos: ventas del mes
        sales = query_db(
            "SELECT SUM(total_sales) as s FROM budget_sales WHERE budget_id=? AND month=?",
            (budget_id, month), one=True
        )
        cash_sales = _safe(sales['s'] if sales else 0)

        # Egresos: labor del mes
        labor = query_db(
            "SELECT SUM(total_cost) as s FROM budget_labor WHERE budget_id=? AND month=?",
            (budget_id, month), one=True
        )
        labor_out = _safe(labor['s'] if labor else 0)

        # CIF del mes
        cif = query_db(
            "SELECT SUM(amount) as s FROM budget_cif WHERE budget_id=? AND month=?",
            (budget_id, month), one=True
        )
        cif_out = _safe(cif['s'] if cif else 0)

        # Deuda del mes
        debt = query_db(
            "SELECT SUM(fee) as s FROM budget_debt_service WHERE budget_id=? AND month=?",
            (budget_id, month), one=True
        )
        debt_out = _safe(debt['s'] if debt else 0)

        total_income  = cash_sales
        total_outflow = labor_out + cif_out + debt_out
        net_cashflow  = total_income - total_outflow
        ending_bal    = prev_balance + net_cashflow

        cf_id = execute_db(
            """INSERT INTO budget_cashflow
               (budget_id, month, cash_sales, total_income,
                labor, cif_cash, loan_principal,
                total_outflow, net_cashflow,
                beginning_balance, ending_balance)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (budget_id, month,
             cash_sales, total_income,
             labor_out, cif_out, debt_out,
             total_outflow, net_cashflow,
             prev_balance, ending_bal)
        )

        rows.append({
            'month':             month,
            'cash_sales':        round(cash_sales, 2),
            'total_income':      round(total_income, 2),
            'labor':             round(labor_out, 2),
            'cif_cash':          round(cif_out, 2),
            'debt':              round(debt_out, 2),
            'total_outflow':     round(total_outflow, 2),
            'net_cashflow':      round(net_cashflow, 2),
            'beginning_balance': round(prev_balance, 2),
            'ending_balance':    round(ending_bal, 2),
        })
        prev_balance = ending_bal

    return rows


def calculate_debt_service(budget_id: int, concept: str,
                           loan_amount: float, annual_rate: float,
                           months: int) -> list:
    """
    Calcula la tabla de amortización de un préstamo (cuotas constantes).
    Método francés: cuota = PV × [r(1+r)^n / ((1+r)^n - 1)]
    """
    monthly_rate = annual_rate / 12
    if monthly_rate > 0:
        fee = loan_amount * (monthly_rate * (1 + monthly_rate) ** months) / \
              ((1 + monthly_rate) ** months - 1)
    else:
        fee = loan_amount / months

    balance  = loan_amount
    rows = []

    # Limpiar entradas previas de este concepto
    execute_db(
        "DELETE FROM budget_debt_service WHERE budget_id=? AND concept=?",
        (budget_id, concept)
    )

    for m in range(1, months + 1):
        interest  = balance * monthly_rate
        principal = fee - interest
        balance   = max(balance - principal, 0)

        execute_db(
            """INSERT INTO budget_debt_service
               (budget_id, concept, loan_amount, annual_rate, months,
                month, principal, interest, fee, balance)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (budget_id, concept, loan_amount, annual_rate, months,
             m, round(principal, 2), round(interest, 2),
             round(fee, 2), round(balance, 2))
        )
        rows.append({
            'month':     m,
            'principal': round(principal, 2),
            'interest':  round(interest,  2),
            'fee':       round(fee, 2),
            'balance':   round(balance, 2),
        })

    return rows
