# app.py - Archivo principal corregido
from __init__ import create_app
from flask import render_template, session, Blueprint
from flask_moment import Moment
import os





# Crear aplicación
app = create_app()

moment = Moment(app)
# app.py - Archivo principal corregido y listo para Railway
from __init__ import create_app
from flask import render_template, session
from flask_moment import Moment
import os

# Crear aplicación
app = create_app()
moment = Moment(app)

# INYECTAR ROL EN TODAS LAS PLANTILLAS
@app.context_processor
def inject_rol():
    return dict(rol=session.get('rol', 'Usuario'))

# RUTA PRINCIPAL
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/home')
def home():
    return render_template('index.html')

# Redirecciones
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

# 🔥 IMPORTANTE PARA RAILWAY:
# NO usar Flask dev server (app.run)
# Gunicorn arrancará la app automáticamente desde el Procfile
