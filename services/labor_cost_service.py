"""
Servicio de cálculo de costos de personal y mano de obra.
Fórmulas según legislación laboral peruana.
"""

def calculate_employee_costs(
    basic_salary: float,
    bonus: float = 0,
    family_allowance: float = 0,
    has_essalud: bool = True,
    has_sctr: bool = False,
    sctr_rate: float = 0.0065,
    available_hours: float = 192.0,
    other_benefits: float = 0
) -> dict:
    """
    Calcula el costo mensual total de un empleado en planilla peruana.

    Gratificación: 2 sueldos al año → 1/6 mensualizado
    CTS: 1 sueldo + 1/6 de gratificaciones al año → mensualizado
    Essalud: 9% del sueldo básico
    SCTR: tasa variable según actividad (defecto 0.65%)
    """
    # Gratificación mensualizada = sueldo / 6
    gratification_monthly = basic_salary / 6.0

    # CTS mensualizada = (sueldo + 1/6 gratificación) / 12
    cts_monthly = (basic_salary + (basic_salary / 6.0)) / 12.0

    # Essalud = 9% del básico
    essalud = basic_salary * 0.09 if has_essalud else 0.0

    # SCTR sobre remuneración asegurable
    sctr = basic_salary * sctr_rate if has_sctr else 0.0

    # Costo mensual total
    total = (
        basic_salary
        + bonus
        + family_allowance
        + gratification_monthly
        + cts_monthly
        + essalud
        + sctr
        + other_benefits
    )

    # Costo por hora
    cost_per_hour = total / available_hours if available_hours > 0 else 0.0

    return {
        'basic_salary': round(basic_salary, 2),
        'bonus': round(bonus, 2),
        'family_allowance': round(family_allowance, 2),
        'gratification_monthly': round(gratification_monthly, 2),
        'cts_monthly': round(cts_monthly, 2),
        'essalud': round(essalud, 2),
        'sctr': round(sctr, 2),
        'other_benefits': round(other_benefits, 2),
        'total_monthly_cost': round(total, 2),
        'cost_per_hour': round(cost_per_hour, 4),
        'available_hours': available_hours,
    }


def calculate_team_costs(employees: list) -> dict:
    """
    Calcula totales de costos para un equipo de empleados.
    employees: lista de dicts con campos de employees table.
    """
    total_mod = 0.0
    total_moi = 0.0
    total_admin = 0.0
    total_ventas = 0.0
    total_all = 0.0
    count_active = 0

    for emp in employees:
        if not emp.get('is_active'):
            continue
        cost = emp.get('total_monthly_cost', 0) or 0
        labor_type = emp.get('labor_type', 'MOD')
        total_all += cost
        count_active += 1

        if labor_type == 'MOD':
            total_mod += cost
        elif labor_type == 'MOI':
            total_moi += cost
        elif labor_type == 'admin':
            total_admin += cost
        elif labor_type == 'ventas':
            total_ventas += cost

    return {
        'total_mod': round(total_mod, 2),
        'total_moi': round(total_moi, 2),
        'total_admin': round(total_admin, 2),
        'total_ventas': round(total_ventas, 2),
        'total_all': round(total_all, 2),
        'count_active': count_active,
        'pct_mod': round((total_mod / total_all * 100) if total_all else 0, 1),
        'pct_moi': round((total_moi / total_all * 100) if total_all else 0, 1),
    }


def calculate_hours_utilization(employees: list) -> list:
    """
    Calcula utilización de horas disponibles vs asignadas por empleado.
    """
    result = []
    for emp in employees:
        available = emp.get('available_hours_month', 192) or 192
        assigned = emp.get('assigned_hours_month', 0) or 0
        utilization = (assigned / available * 100) if available > 0 else 0
        result.append({
            'id': emp['id'],
            'full_name': emp['full_name'],
            'available_hours': available,
            'assigned_hours': assigned,
            'free_hours': round(available - assigned, 1),
            'utilization_pct': round(utilization, 1),
            'cost_per_hour': emp.get('cost_per_hour', 0),
            'cost_assigned': round(assigned * (emp.get('cost_per_hour', 0) or 0), 2),
        })
    return result
