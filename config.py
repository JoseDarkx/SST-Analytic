import os
import mysql.connector   # 👈 Importamos mysql.connector para la conexión


class Config:
    # Configuración de base de datos MySQL
    DB_CONFIG = {
        "host": "localhost",
        "user": "root",
        "password": "",
        "database": "gestussg"
    }
    
    # Configuración básica de Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'tu-clave-secreta-muy-segura-aqui'
    
    # Configuraciones para URL building
    SERVER_NAME = None
    APPLICATION_ROOT = '/'
    PREFERRED_URL_SCHEME = 'http'
    
    # Configuración de SQLAlchemy (no la usas por ahora, pero la dejamos)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'mysql+mysqlconnector://root:@localhost/gestussg'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configuraciones adicionales
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = 'uploads'
    
    # Configuración de mail
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    # ✅ CORREGIDO: Usar las variables correctamente
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'josepberdugo3@gmail.com'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'tzdv lrcv qqgs rpwt'
    MAIL_DEFAULT_SENDER = ('Sistema SST', 'josepberdugo3@gmail.com')

# -----------------------------------
# 🔹 Función global para obtener conexión MySQL
# -----------------------------------
def get_db():
    """
    Crea y retorna una conexión a la base de datos MySQL
    usando la configuración de Config.DB_CONFIG
    """
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        return connection
    except mysql.connector.Error as err:
        print(f"❌ Error al conectar con la base de datos: {err}")
        raise