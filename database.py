# database.py
import os
import time
import mysql.connector
from mysql.connector import Error

def env(*names, default=None):
    """Devuelve el primer valor existente entre múltiples nombres de variable."""
    for name in names:
        v = os.getenv(name)
        if v not in (None, ""):
            return v
    return default

def get_db_config():
    return {
        "host": env("MYSQL_HOST", "MYSQLHOST", "DB_HOST", default="127.0.0.1"),
        "user": env("MYSQL_USER", "MYSQLUSER", "DB_USER", default="root"),
        "password": env("MYSQL_PASSWORD", "MYSQLPASSWORD", "DB_PASSWORD", default=""),
        "database": env("MYSQL_DATABASE", "MYSQLDATABASE", "DB_NAME", default=""),
        "port": int(env("MYSQL_PORT", "MYSQLPORT", "DB_PORT", default=3306))
    }

def get_connection(retries=5, delay=3):
    cfg = get_db_config()
    last_err = None

    for attempt in range(1, retries + 1):
        try:
            conn = mysql.connector.connect(
                host=cfg["host"],
                user=cfg["user"],
                password=cfg["password"],
                database=cfg["database"],
                port=cfg["port"],
                autocommit=True
            )
            if conn.is_connected():
                print("✅ Conectado a MySQL correctamente")
                return conn

        except Error as e:
            last_err = e
            print(f"[DB] intento {attempt}/{retries} fallido: {e}. Reintentando en {delay}s...")
            time.sleep(delay)

    raise ConnectionError(
        f"No se pudo conectar a MySQL después de {retries} intentos. Error: {last_err}"
    )

