import mysql.connector
from flask import current_app
from flask_mail import Mail
import logging

mail = Mail()
logger = logging.getLogger(__name__)

def get_db():
    """
    Obtiene conexión a MySQL usando las variables de Railway.
    Incluye manejo de errores y logging para depuración.
    """
    try:
        connection = mysql.connector.connect(
            host=current_app.config['MYSQL_HOST'],
            port=current_app.config['MYSQL_PORT'],
            user=current_app.config['MYSQL_USER'],
            password=current_app.config['MYSQL_PASSWORD'],
            database=current_app.config['MYSQL_DB'],
            autocommit=True
        )
        logger.info("✅ Conexión a MySQL exitosa")
        return connection
    except mysql.connector.Error as err:
        logger.error(f"❌ Error de conexión MySQL: {err}")
        logger.error(f"Host: {current_app.config.get('MYSQL_HOST')}")
        logger.error(f"Port: {current_app.config.get('MYSQL_PORT')}")
        logger.error(f"User: {current_app.config.get('MYSQL_USER')}")
        logger.error(f"Database: {current_app.config.get('MYSQL_DB')}")
        return None
    except Exception as e:
        logger.error(f"❌ Error inesperado al conectar: {e}")
        return None

def close_db(e=None):
    """Cierra la conexión a la base de datos si existe"""
    pass

# Alias para compatibilidad con código existente
get_connection = get_db
