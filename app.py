# app.py - Archivo principal correcto para Railway

from __init__ import create_app
from flask import render_template, session
from flask_moment import Moment

# Crear aplicación
app = create_app()
moment = Moment(app)

# ---------------------------
# 🔹 Inyectar variable "rol"
# ---------------------------
@app.context_processor
def inject_rol():
    return dict(rol=session.get('rol', 'Usuario'))

@app.route("/health")
def health():
    return "OK"


# ---------------------------
# 🔹 Rutas públicas
# ---------------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/home')
def home():
    return render_template('index.html')

# ---------------------------
# 🔹 Redirecciones
# ---------------------------
@app.route('/dashboard')
def dashboard_redirect():
    from flask import redirect, url_for
    return redirect(url_for('auth.dashboard'))

@app.route('/evaluaciones_medicas')
def redirect_evaluaciones():
    from flask import redirect, url_for
    return redirect(url_for('evaluaciones_medicas.evaluaciones_medicas'))

@app.route('/control_epp')
def redirect_control_epp():
    from flask import redirect, url_for
    return redirect(url_for('epp.control_epp'))

@app.route('/agregar_evaluacion')
def redirect_agregar_evaluacion():
    from flask import redirect, url_for
    return redirect(url_for('evaluaciones_medicas.agregar_evaluaciones'))

# 🚫 IMPORTANTE:
# NO usar app.run() en Railway — Gunicorn lo iniciará automáticamente.
