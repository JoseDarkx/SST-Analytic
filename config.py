import os
from config import get_db
import mysql.connector


class Config:
    # -----------------------------------
    # 🔹 Configuración de base de datos MySQL desde Railway
    # -----------------------------------
    DB_CONFIG = {
        "host": os.getenv("MYSQLHOST"),
        "user": os.getenv("MYSQLUSER"),
        "password": os.getenv("MYSQLPASSWORD"),
        "database": os.getenv("MYSQLDATABASE"),
        "port": int(os.getenv("MYSQLPORT", 3306))
    }

    # Configuración básica de Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'tu-clave-secreta-muy-segura-aqui'
    
    SERVER_NAME = None
    APPLICATION_ROOT = '/'
    PREFERRED_URL_SCHEME = 'http'
    
    # Configuración SQLAlchemy (no la usas, pero queda limpia)
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+mysqlconnector://{os.getenv('MYSQLUSER')}:{os.getenv('MYSQLPASSWORD')}"
        f"@{os.getenv('MYSQLHOST')}:{os.getenv('MYSQLPORT')}/{os.getenv('MYSQLDATABASE')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = 'uploads'

    # Configuración de correo
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'josepberdugo3@gmail.com'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'tzdv lrcv qqgs rpwt'
    MAIL_DEFAULT_SENDER = ('Sistema SST', 'josepberdugo3@gmail.com')

# -----------------------------------
# 🔹 Función global para obtener conexión MySQL
# -----------------------------------
def get_db():
    """
    Crea y retorna una conexión MySQL usando Railway.
    """
    try:
        connection = mysql.connector.connect(
            host=os.getenv("MYSQLHOST"),
            user=os.getenv("MYSQLUSER"),
            password=os.getenv("MYSQLPASSWORD"),
            database=os.getenv("MYSQLDATABASE"),
            port=int(os.getenv("MYSQLPORT", 3306))
        )
        return connection
    except mysql.connector.Error as err:
        print(f"❌ Error al conectar con la base de datos: {err}")
        raise
