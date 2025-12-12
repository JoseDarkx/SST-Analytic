# app.py - Archivo principal corregido
from __init__ import create_app
from flask import render_template, session, Blueprint
from flask_moment import Moment
import os





# Crear aplicación
app = create_app()

moment = Moment(app)

# ✅ INYECTAR ROL EN TODAS LAS PLANTILLAS
@app.context_processor
def inject_rol():
    return dict(rol=session.get('rol', 'Usuario'))
    # Esto permite usar {{ rol }} en el HTML sin pasarlo manualmente


# RUTA PRINCIPAL
@app.route('/')
def index():
    return render_template('index.html')


# Rutas adicionales si no están en blueprints
@app.route('/home')
def home():
    return render_template('index.html')


# Ruta de dashboard sin prefijo (alternativa)
@app.route('/dashboard')
def dashboard_redirect():
    from flask import redirect, url_for
    return redirect(url_for('auth.dashboard'))


# Redirects para rutas que cambiaron de ubicación
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


if __name__ == '__main__':
    print("🚀 Iniciando servidor Flask...")
    print("📍 Rutas disponibles:")
    print("   • http://127.0.0.1:5000/ (Página principal)")
    print("   • http://127.0.0.1:5000/auth/dashboard (Dashboard)")
    print("   • http://127.0.0.1:5000/auth/iniciar-sesion (Login)")
    
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
