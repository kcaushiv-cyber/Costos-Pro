from flask_mail import Message
from flask import current_app


def _get_app_url():
    """Retorna la URL base del sistema desde config."""
    try:
        return current_app.config.get('APP_URL', 'http://localhost:5001')
    except Exception:
        return 'http://localhost:5001'


def _get_sender():
    """Retorna el sender configurado o el username como fallback."""
    sender = current_app.config.get('MAIL_DEFAULT_SENDER') or              current_app.config.get('MAIL_USERNAME') or ''
    name   = current_app.config.get('MAIL_SENDER_NAME', 'Costos Pro')
    if sender and '@' in sender:
        return (name, sender)
    return sender

# ── Paleta corporativa Costos Pro ──────────────────────────────────────────
_CSS = """
    body { font-family:'Segoe UI',Arial,sans-serif; background:#FFF8F1; margin:0; padding:0; }
    .wrap { max-width:600px; margin:30px auto; background:#ffffff; border-radius:14px;
            overflow:hidden; box-shadow:0 4px 24px rgba(249,115,22,0.12); }
    .header { background:linear-gradient(135deg,#1F2937 0%,#374151 100%);
              padding:36px 40px; text-align:center; border-bottom:4px solid #F97316; }
    .header .logo { font-size:28px; font-weight:800; color:#F97316; letter-spacing:-0.5px; }
    .header .logo span { color:#ffffff; }
    .header p { color:rgba(255,255,255,0.7); margin:6px 0 0; font-size:14px; }
    .body { padding:36px 40px; }
    .body h2 { color:#1F2937; font-size:20px; margin:0 0 12px; }
    .body p  { color:#4B5563; line-height:1.7; margin:10px 0; font-size:14px; }
    .alert-box { background:#FFF7ED; border-left:4px solid #F97316;
                 border-radius:0 8px 8px 0; padding:16px 20px; margin:20px 0; }
    .alert-box.danger { background:#FEF2F2; border-left-color:#DC2626; }
    .alert-box .label { font-size:11px; font-weight:700; text-transform:uppercase;
                        letter-spacing:0.08em; color:#F97316; margin-bottom:6px; }
    .alert-box.danger .label { color:#DC2626; }
    .kpi-row { display:flex; gap:12px; margin:20px 0; flex-wrap:wrap; }
    .kpi { flex:1; min-width:120px; background:#FFF8F1; border:1px solid #FED7AA;
           border-radius:10px; padding:14px 16px; text-align:center; }
    .kpi .val { font-size:22px; font-weight:800; color:#F97316; }
    .kpi .lbl { font-size:11px; color:#9CA3AF; margin-top:3px; }
    .kpi.danger .val { color:#DC2626; }
    .kpi.danger { border-color:#FECACA; background:#FEF2F2; }
    .btn { display:inline-block; background:#F97316; color:#ffffff !important;
           padding:12px 28px; border-radius:8px; text-decoration:none;
           font-weight:700; font-size:14px; margin-top:16px; }
    .divider { border:none; border-top:1px solid #E5E7EB; margin:24px 0; }
    .footer { background:#1F2937; padding:20px 40px; text-align:center;
              color:rgba(255,255,255,0.5); font-size:12px; }
    .footer strong { color:#F97316; }
"""


def _base_html(content: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>{_CSS}</style></head>
<body>
<div class="wrap">
  <div class="header">
    <div class="logo">Costos<span>Pro</span></div>
    <p>Sistema de Gestión de Costos Empresariales</p>
  </div>
  <div class="body">{content}</div>
  <div class="footer">
    © 2025 <strong>Costos Pro</strong> — Sistema de Costos Empresariales · Perú<br>
    Este mensaje fue generado automáticamente, por favor no responder.
  </div>
</div>
</body></html>"""


# ── Bienvenida ─────────────────────────────────────────────────────────────

def send_welcome_email(mail, user_email: str, full_name: str, business_name: str) -> bool:
    try:
        msg = Message(
            subject="¡Bienvenido/a a Costos Pro! 🚀",
            recipients=[user_email],
            sender=_get_sender()
        )
        msg.html = _base_html(f"""
<h2>¡Bienvenido/a, {full_name}!</h2>
<p>Tu cuenta ha sido creada exitosamente. Ya puedes comenzar a gestionar los costos de
<strong>{business_name}</strong> con ayuda de inteligencia artificial.</p>

<div class="alert-box">
  <div class="label">📋 Datos de tu cuenta</div>
  👤 <strong>Usuario:</strong> {full_name}<br>
  📧 <strong>Correo:</strong> {user_email}<br>
  🏢 <strong>Empresa:</strong> {business_name}
</div>

<p>Con Costos Pro podrás:</p>
<p>✅ Crear estructuras de costos con ayuda de IA<br>
✅ Gestionar tu Kardex con control de stock mínimo<br>
✅ Calcular costos ABC, por proceso y presupuestos<br>
✅ Exportar reportes ejecutivos a Excel y PDF</p>

<a href="{_get_app_url()}" class="btn">Ir al sistema →</a>
""")
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Error enviando email de bienvenida: {e}")
        return False


# ── Recuperación de contraseña ─────────────────────────────────────────────

def send_password_reset_email(mail, user_email: str, full_name: str, reset_link: str) -> bool:
    try:
        msg = Message(
            subject="Recupera tu contraseña — Costos Pro",
            recipients=[user_email],
            sender=_get_sender()
        )
        msg.html = _base_html(f"""
<h2>Recuperación de contraseña</h2>
<p>Hola <strong>{full_name}</strong>, recibimos una solicitud para restablecer tu contraseña.</p>

<div class="alert-box">
  <div class="label">🔐 Enlace de recuperación</div>
  Haz clic en el botón para crear una nueva contraseña.<br>
  Este enlace expira en <strong>1 hora</strong>.
</div>

<a href="{reset_link}" class="btn">Restablecer contraseña →</a>

<hr class="divider">
<p style="font-size:13px;color:#9CA3AF">Si no solicitaste este cambio, ignora este mensaje.
Tu contraseña actual seguirá siendo la misma.</p>
""")
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Error enviando email de recuperación: {e}")
        return False


# ── Alerta stock bajo mínimo ───────────────────────────────────────────────

def send_low_stock_email(mail, to_email: str, full_name: str, company_name: str,
                          item_code: str, item_name: str,
                          current_stock: float, safety_stock: float,
                          unit: str = 'uds') -> bool:
    try:
        deficit = safety_stock - current_stock
        msg = Message(
            subject=f"⚠ Alerta de stock bajo — {item_name} | {company_name}",
            recipients=[to_email],
            sender=_get_sender()
        )
        msg.html = _base_html(f"""
<h2>⚠ Alerta: Stock bajo mínimo</h2>
<p>Hola <strong>{full_name}</strong>, el ítem <strong>{item_name}</strong> de
<strong>{company_name}</strong> está por debajo del stock de seguridad.</p>

<div class="kpi-row">
  <div class="kpi danger">
    <div class="val">{current_stock:g}</div>
    <div class="lbl">Stock actual ({unit})</div>
  </div>
  <div class="kpi">
    <div class="val" style="color:#6B7280">{safety_stock:g}</div>
    <div class="lbl">Stock mínimo ({unit})</div>
  </div>
  <div class="kpi danger">
    <div class="val">{deficit:g}</div>
    <div class="lbl">Déficit ({unit})</div>
  </div>
</div>

<div class="alert-box danger">
  <div class="label">📦 Detalle del ítem</div>
  <strong>Código:</strong> {item_code}<br>
  <strong>Nombre:</strong> {item_name}<br>
  <strong>Stock actual:</strong> {current_stock:g} {unit}<br>
  <strong>Stock mínimo:</strong> {safety_stock:g} {unit}<br>
  <strong>Necesitas reponer:</strong> al menos {deficit:g} {unit}
</div>

<p>Se recomienda realizar un pedido de reposición lo antes posible para
evitar interrupciones en la producción.</p>

<a href="{_get_app_url()}/kardex" class="btn">Ver Kardex →</a>
""")
        mail.send(msg)
        current_app.logger.info(f"Alerta stock enviada: {item_name} → {to_email}")
        return True
    except Exception as e:
        current_app.logger.error(f"Error enviando alerta stock: {e}")
        return False


# ── Invitación a empresa ───────────────────────────────────────────────────

def send_invite_email(mail, to_email: str, full_name: str, company_name: str,
                       inviter_name: str, role: str, is_new_user: bool = False,
                       password: str = None) -> bool:
    roles_es = {
        'admin':  'Administrador — acceso total',
        'editor': 'Editor — puede crear y editar',
        'viewer': 'Solo lectura — solo visualización',
        'custom': 'Personalizado',
    }
    role_label = roles_es.get(role, role)
    cred_block = ""
    if is_new_user and password:
        cred_block = f"""
<div class="alert-box" style="margin-top:16px">
  <div class="label">🔐 Tus credenciales de acceso</div>
  📧 <strong>Correo:</strong> {to_email}<br>
  🔑 <strong>Contraseña:</strong> {password}<br>
  <small style="color:#9CA3AF">Cambia tu contraseña después del primer ingreso.</small>
</div>"""

    try:
        msg = Message(
            subject=f"Te invitaron a {company_name} en Costos Pro 🎉",
            recipients=[to_email],
            sender=_get_sender()
        )
        msg.html = _base_html(f"""
<h2>¡Tienes acceso a {company_name}!</h2>
<p>Hola <strong>{full_name}</strong>, <strong>{inviter_name}</strong> te ha invitado
a colaborar en <strong>{company_name}</strong> usando Costos Pro.</p>

<div class="alert-box">
  <div class="label">🏢 Detalles del acceso</div>
  <strong>Empresa:</strong> {company_name}<br>
  <strong>Tu rol:</strong> {role_label}<br>
  <strong>Invitado por:</strong> {inviter_name}
</div>
{cred_block}
<p>Al iniciar sesión verás automáticamente la empresa <strong>{company_name}</strong>
con los módulos que el administrador te habilitó.</p>

<a href="{_get_app_url()}/login" class="btn">Ingresar al sistema →</a>

<hr class="divider">
<p style="font-size:13px;color:#9CA3AF">Si no esperabas esta invitación, ignora este mensaje.</p>
""")
        mail.send(msg)
        return True
    except Exception as e:
        import logging
        logging.error(f"Error enviando correo de invitación: {e}")
        return False
