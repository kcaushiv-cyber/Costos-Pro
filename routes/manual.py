from flask import Blueprint, render_template, session
from routes.dashboard import login_required

manual_bp = Blueprint('manual', __name__)

@manual_bp.route('/manual')
@login_required
def index():
    session['active_module'] = 'manual'
    return render_template('manual/index.html')
