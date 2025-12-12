# database.py
import os
import time
import mysql.connector
from mysql.connector import Error

def get_db_config():
    return {
        "host": os.getenv("MYSQL_HOST", os.getenv("MYSQLHOST", "127.0.0.1")),
        "user": os.getenv("MYSQL_USER", os.getenv("MYSQLUSER", "root")),
        "password": os.getenv("MYSQL_PASSWORD", os.getenv("MYSQLPASSWORD", "")),
        "database": os.getenv("MYSQL_DATABASE", os.getenv("MYSQLDATABASE", "")),
        "port": int(os.getenv("MYSQL_PORT", os.getenv("MYSQLPORT", 3306)))
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
