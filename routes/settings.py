from flask import Blueprint, render_template, session, request, jsonify
from routes.dashboard import login_required

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/settings')
@login_required
def index():
    session['active_module'] = 'settings'
    return render_template('settings/index.html')

@settings_bp.route('/settings/voice', methods=['POST'])
@login_required
def save_voice():
    data = request.get_json()
    session['voice_enabled'] = data.get('enabled', True)
    session['voice_speed'] = data.get('speed', 1.0)
    session['voice_volume'] = data.get('volume', 0.8)
    return jsonify({'success': True})


@settings_bp.route('/settings/test-email', methods=['POST'])
@login_required
def test_email():
    """Envía un correo de prueba para verificar la configuración SMTP."""
    from flask import current_app, jsonify
    from flask_mail import Mail, Message
    try:
        mail = current_app.extensions.get('mail')
        username = current_app.config.get('MAIL_USERNAME', '')
        if not username:
            return jsonify({'success': False, 'error': 'MAIL_USERNAME no configurado en .env'})

        from utils.email_utils import _get_sender
        msg = Message(
            subject='✅ Prueba de correo — Costos Pro',
            recipients=[username],
            sender=_get_sender(),
            html=f"""<div style="font-family:Arial;padding:20px;background:#FFF8F1">
                <h2 style="color:#F97316">¡Correo funcionando! ✅</h2>
                <p>El sistema de correos de <strong>Costos Pro</strong> está configurado correctamente.</p>
                <p style="color:#6B7280;font-size:12px">Servidor: {current_app.config.get('MAIL_SERVER')}:{current_app.config.get('MAIL_PORT')}</p>
            </div>"""
        )
        mail.send(msg)
        return jsonify({'success': True, 'message': f'Correo enviado a {username}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
