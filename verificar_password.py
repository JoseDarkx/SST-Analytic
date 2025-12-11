# resetear_password.py
import mysql.connector
from werkzeug.security import generate_password_hash

conexion = mysql.connector.connect(host="localhost", user="root", password="", database="gestussg")
cursor = conexion.cursor()

usuario = input("Usuario a resetear: ").strip()
nueva = input("Nueva contraseña: ").strip()

hashed = generate_password_hash(nueva)  # por defecto pbkdf2:sha256
cursor.execute("UPDATE usuarios SET contraseña = %s WHERE usuario = %s", (hashed, usuario))
conexion.commit()

print("Contraseña actualizada.")
cursor.close()
conexion.close()