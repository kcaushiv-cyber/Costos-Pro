import os
import json
import logging
import requests
from flask import session
from models.database import query_db

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 10000

# ── System prompts por agente ──────────────────────────────────────────────

AGENT_PROMPTS = {
    'general': (
        "Eres el asistente inteligente de Costos Pro, sistema ERP académico/profesional de gestión de costos. "
        "Ayudas con: uso del sistema, fórmulas de costos, interpretación de resultados, clasificación de costos, "
        "estructura de costos ABC, costos por proceso, presupuestos y costos de calidad. "
        "Responde en español, de forma clara, concisa y profesional. "
        "Si te dan contexto del sistema (empresa, módulo, datos), úsalo para personalizar tu respuesta."
    ),
    'estructura': (
        "Eres un especialista en diseño de sistemas de costos empresariales. "
        "Cuando el usuario describe su negocio, debes generar una propuesta estructurada en JSON con: "
        "recursos (código, nombre, monto mensual estimado, inductor), "
        "centros_de_actividad (código, nombre, tipo), "
        "actividades (código, nombre, centro, inductor), "
        "objetos_de_costo (código, nombre, cantidad_mes estimada). "
        "Responde SOLO con JSON válido, sin texto adicional. "
        "Adapta la propuesta al sector indicado."
    ),
    'clasificador': (
        "Eres un experto en clasificación de costos empresariales. "
        "Dado un costo o gasto, clasifícalo respondiendo en JSON con: "
        "tipo_primario (MP|MOD|CIF|gasto_admin|gasto_ventas|gasto_financiero), "
        "tipo_fijo_variable (fijo|variable|semivariable), "
        "tipo_directo_indirecto (directo|indirecto), "
        "modulo_sistema (recursos|personal|inventario|estructura), "
        "explicacion (breve, 1 oración). "
        "Responde SOLO con JSON válido."
    ),
    'calidad': (
        "Eres un experto en costos de calidad ISO 9001 y modelo PAF. "
        "Cuando el usuario describe una actividad, responde ÚNICAMENTE con JSON válido, "
        "sin texto adicional, sin markdown, sin explicaciones fuera del JSON. "
        "Formato exacto: "
        '{"categoria":"prevencion","explicacion":"...","pct_ventas_tipico":"0.5%-1.5%","recomendacion":"reforzar"} '
        "Categorías válidas: prevencion, evaluacion, falla_interna, falla_externa, no_aplica. "
        "Responde SOLO con JSON válido."
    ),
    'presupuestos': (
        "Eres un especialista en presupuestos empresariales y análisis financiero. "
        "Ayudas a proyectar ventas, interpretar el Estado de Ganancias y Pérdidas proyectado, "
        "analizar flujos de caja, calcular VAN/TIR e interpretar variaciones entre períodos. "
        "Responde en español con explicaciones claras y orientadas a la toma de decisiones gerenciales. "
        "Usa el contexto financiero proporcionado para dar respuestas específicas."
    ),
    'abc': (
        "Eres un experto en el sistema de Costeo Basado en Actividades (ABC). "
        "Ayudas a: sugerir inductores coherentes para cada actividad, detectar inductores mal planteados, "
        "explicar por qué el costo ABC difiere del tradicional, identificar objetos de costo "
        "que absorben costos indirectos desproporcionadamente. "
        "Usa siempre la notación: Recursos→Centros de Actividad→Actividades→Objetos de Costo. "
        "Responde en español con lenguaje técnico pero accesible."
    ),
    'proceso': (
        "Eres un experto en Costos por Proceso con los 4 modelos: Normal, Unidades Agregadas, "
        "Unidades Perdidas y PROTECHO. "
        "Conoces la notación exacta: UIIPP, UPROD, UAg, UTT, UTNT, UIFPP, UP. "
        "Verificas siempre que: Unidades por Contabilizar = Unidades Contabilizadas. "
        "Explicas el flujo físico, el plan de cantidades, las unidades equivalentes (UE) "
        "y el costo unitario paso a paso. "
        "Responde en español con el rigor técnico del profesor Dr. Luis Alberto Lujan Campos."
    ),
    'graficos': (
        "Eres un analista financiero experto en interpretación de datos y gráficos empresariales. "
        "Dado un conjunto de datos de un gráfico, genera interpretaciones gerenciales concretas: "
        "identifica concentraciones, outliers, tendencias y distribuciones atípicas. "
        "Sugiere acciones concretas basadas en los datos. "
        "Usa lenguaje directo y orientado a decisiones. Responde en español."
    ),
    'reportes': (
        "Eres un consultor gerencial especialista en análisis de costos empresariales. "
        "Genera reportes narrativos ejecutivos con: análisis de rentabilidad, "
        "comentarios sobre estructura de costos, identificación de riesgos financieros, "
        "comparación con período anterior, y recomendaciones de decisión concretas. "
        "Usa un tono profesional y ejecutivo. Responde en español."
    ),
    'manual': (
        "Eres el asistente del Manual de Usuario de Costos Pro. "
        "Respondes preguntas sobre cómo usar el sistema: cómo registrar datos, "
        "qué hace cada botón, cuál es el flujo de trabajo correcto, "
        "cómo navegar entre módulos y cómo interpretar los resultados. "
        "Siempre guías al usuario paso a paso. "
        "Si preguntan sobre un concepto técnico, explícalo brevemente y luego indica "
        "dónde encontrarlo en el sistema. Responde en español."
    ),
}


def _get_api_key():
    key = os.getenv('ANTHROPIC_API_KEY', '')
    if not key:
        raise ValueError("ANTHROPIC_API_KEY no configurada en .env")
    return key


def build_context(agent_type='general'):
    """
    Construye un contexto resumido y seguro para enviar a la IA.
    Nunca envía la BD completa — solo datos relevantes para el agente.
    """
    company_id = session.get('company_id')
    period_id = session.get('period_id')
    ctx = {
        'empresa': session.get('company_name', 'No seleccionada'),
        'sector': session.get('sector', ''),
        'periodo': session.get('period_name', ''),
        'modulo_activo': session.get('active_module', 'dashboard'),
    }

    if not company_id:
        return ctx

    if agent_type in ('abc', 'graficos', 'reportes'):
        resources = query_db(
            "SELECT code, name, monthly_amount FROM resources WHERE company_id=? AND period_id=? LIMIT 10",
            (company_id, period_id)
        )
        ctx['recursos'] = [dict(r) for r in resources] if resources else []

        centers = query_db(
            "SELECT code, name, total_cost_monthly FROM activity_centers WHERE company_id=? AND period_id=? LIMIT 10",
            (company_id, period_id)
        )
        ctx['centros'] = [dict(c) for c in centers] if centers else []

    if agent_type in ('presupuestos', 'reportes'):
        budget = query_db(
            "SELECT name, total_sales, total_production_cost, gross_profit, net_income FROM budgets WHERE company_id=? AND period_id=? LIMIT 1",
            (company_id, period_id), one=True
        )
        ctx['presupuesto'] = dict(budget) if budget else {}

    if agent_type in ('general', 'reportes'):
        emp_count = query_db(
            "SELECT COUNT(*) as n, SUM(total_monthly_cost) as total FROM employees WHERE company_id=? AND is_active=1",
            (company_id,), one=True
        )
        ctx['personal'] = {
            'total': emp_count['n'] if emp_count else 0,
            'costo_mensual': emp_count['total'] if emp_count and emp_count['total'] else 0
        }

    return ctx


def send_message(message: str, history: list = None, agent_type: str = 'general') -> dict:
    """Envía un mensaje al agente especificado y retorna la respuesta."""
    try:
        api_key = _get_api_key()
        system_prompt = AGENT_PROMPTS.get(agent_type, AGENT_PROMPTS['general'])

        # Agregar contexto del sistema al prompt
        ctx = build_context(agent_type)
        context_str = json.dumps(ctx, ensure_ascii=False)
        system_with_context = f"{system_prompt}\n\nContexto actual del sistema:\n{context_str}"

        # Construir historial de mensajes
        messages = []
        if history:
            for item in history[-10:]:  # máximo 10 mensajes de historial
                role = item.get('role', 'user')
                content = item.get('content', '')
                if role in ('user', 'assistant') and content:
                    messages.append({'role': role, 'content': content})

        messages.append({'role': 'user', 'content': message})

        response = requests.post(
            ANTHROPIC_API_URL,
            headers={
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            json={
                'model': MODEL,
                'max_tokens': MAX_TOKENS,
                'system': system_with_context,
                'messages': messages,
            },
            timeout=120,
        )

        if response.status_code == 200:
            data = response.json()
            text = data['content'][0]['text']
            tokens = data.get('usage', {}).get('output_tokens', 0)
            return {'success': True, 'response': text, 'tokens': tokens, 'error': None}
        else:
            err = f"Error API: {response.status_code} - {response.text[:200]}"
            logger.error(err)
            return {'success': False, 'response': None, 'error': err}

    except ValueError as e:
        return {'success': False, 'response': None, 'error': str(e)}
    except Exception as e:
        logger.error(f"Error claude_service: {e}")
        return {'success': False, 'response': None, 'error': 'Error de conexión con la IA'}


def classify_cost(description: str, company_id: int = None) -> dict:
    """Clasifica un costo usando el agente clasificador."""
    result = send_message(
        f"Clasifica este costo: {description}",
        agent_type='clasificador'
    )
    if result['success']:
        try:
            return json.loads(result['response'])
        except json.JSONDecodeError:
            return {'error': 'Respuesta inválida del clasificador'}
    return {'error': result['error']}


def classify_quality_cost(activity_name: str, description: str = '') -> dict:
    """Clasifica una actividad en categorías de costos de calidad."""
    msg = f"Actividad: {activity_name}"
    if description:
        msg += f"\nDescripción: {description}"
    result = send_message(msg, agent_type='calidad')
    if result['success']:
        try:
            return json.loads(result['response'])
        except json.JSONDecodeError:
            return {'error': 'Respuesta inválida del clasificador'}
    return {'error': result['error']}


def generate_cost_structure(business_description: str, sector: str) -> dict:
    """Genera estructura de costos sugerida para un negocio."""
    msg = f"Sector: {sector}\nDescripción del negocio: {business_description}"
    result = send_message(msg, agent_type='estructura')
    if result['success']:
        try:
            return {'success': True, 'data': json.loads(result['response'])}
        except json.JSONDecodeError:
            return {'success': False, 'error': 'Respuesta no es JSON válido'}
    return {'success': False, 'error': result['error']}


def interpret_chart_data(chart_data: dict, chart_type: str, module: str) -> dict:
    """Interpreta datos de un gráfico y genera análisis gerencial."""
    msg = (
        f"Módulo: {module}\n"
        f"Tipo de gráfico: {chart_type}\n"
        f"Datos: {json.dumps(chart_data, ensure_ascii=False)}"
    )
    result = send_message(msg, agent_type='graficos')
    return result


def health_check() -> dict:
    try:
        _get_api_key()
        return {'status': 'ok', 'model': MODEL, 'ready': True}
    except Exception as e:
        return {'status': 'error', 'message': str(e), 'ready': False}


# Alias para compatibilidad con código que use el nombre antiguo
claude_service = type('ClaudeService', (), {
    'send_message': staticmethod(send_message),
    'health_check': staticmethod(health_check),
})()
