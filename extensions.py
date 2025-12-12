# extensions.py - Versión corregida con manejo de errores
import mysql.connector
from flask import g 
from config import Config
from flask_mail import Mail

def get_db():
    """Obtener conexión a base de datos con manejo de errores"""
    if 'db' not in g:
        try:
            # Intentar usar DB_CONFIG si existe
            if hasattr(Config, 'DB_CONFIG'):
                g.db = get_db()  # 🔄 Conexión centralizada
            elif hasattr(Config, 'DB_CONFIG_ENV'):
                g.db = get_db()  # 🔄 Conexión centralizada
            else:
                # Configuración por defecto si no existe
                g.db = get_db()  # 🔄 Conexión centralizada
            print("✅ Conexión a BD establecida")
        except mysql.connector.Error as err:
            print(f"❌ Error de conexión a BD: {err}")
            # En lugar de fallar, devolver None y manejar en las rutas
            g.db = None
        except Exception as e:
            print(f"❌ Error general de BD: {e}")
            g.db = None
    
    return g.db

mail = Mail()

def close_db(error=None):
    """Cerrar conexión a base de datos"""
    db = g.pop('db', None)
    if db is not None:
        try:
            db.close()
        except:
            pass

# Función helper para rutas que necesiten BD
def require_db():
    """Decorator o función para verificar conexión BD"""
    db = get_db()
    if db is None:
        from flask import jsonify, render_template_string
        error_template = '''
        <h1>Error de Base de Datos</h1>
        <p>No se pudo conectar a la base de datos.</p>
        <p>Por favor verifica:</p>
        <ul>
            <li>MySQL está ejecutándose</li>
            <li>Credenciales en config.py son correctas</li>
            <li>La base de datos existe</li>
        </ul>
        <a href="/">Volver al inicio</a>
        '''
        return render_template_string(error_template), 500
    return db

# Función para inicializar BD si no existe
def init_database():
    """Crear base de datos si no existe"""
    import mysql.connector

    try:
        print("🔄 Iniciando verificación de base de datos...")

        # 🔧 Conexión inicial SIN seleccionar base de datos
        conn = get_connection()

        cursor = conn.cursor()

        # Nombre de la BD
        db_name = "railway"

        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        print(f"✅ Base de datos {db_name} verificada/creada")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"⚠️ Error al crear/verificar la BD: {e}")
        return False
