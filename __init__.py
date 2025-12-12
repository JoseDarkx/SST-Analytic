from flask import Flask
from config import Config
from extensions import close_db, mail

# Importar Blueprints
from blueprints.auth.routes import auth_bp
from blueprints.usuarios.routes import usuarios_bp
from blueprints.evaluaciones_medicas.routes import evaluaciones_medicas_bp
from blueprints.empresas.routes import empresas_bp
from blueprints.capacitaciones.routes import capacitaciones_bp
from blueprints.documentos.routes import documentos_bp
from blueprints.recuperacion.routes import recuperacion_bp
from blueprints.epp.routes import epp_bp
from blueprints.inventario_epp.routes import inventario_bp
from blueprints.incidentes.routes import incidentes_bp
from blueprints.formatos.routes import formatos_globales_bp
from blueprints.normativas.routes import normativas_bp
from blueprints.planes_accion.routes import planes_accion_bp
from services.notificaciones_service import generar_notificaciones


def create_app():
    app = Flask(__name__, template_folder='templates')
    app.config.from_object(Config)

    mail.init_app(app)

    # Registrar blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(evaluaciones_medicas_bp)
    app.register_blueprint(empresas_bp)
    app.register_blueprint(capacitaciones_bp, url_prefix='/capacitaciones')
    app.register_blueprint(documentos_bp)
    app.register_blueprint(recuperacion_bp)
    app.register_blueprint(epp_bp)
    app.register_blueprint(inventario_bp)
    app.register_blueprint(incidentes_bp)
    app.register_blueprint(formatos_globales_bp)
    app.register_blueprint(normativas_bp)
    app.register_blueprint(planes_accion_bp)

    app.teardown_appcontext(close_db)

    with app.app_context():
        try:
            generar_notificaciones()
            print("✅ Notificaciones generadas al iniciar la aplicación.")
        except Exception as e:
            print(f"⚠️ Error generando notificaciones: {e}")

    return app
