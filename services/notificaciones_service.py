from datetime import datetime, timedelta
from database import get_connection as get_db
import mysql.connector

def generar_notificaciones():
    try:
        # Conexión a la base de datos
        db = get_db()  # 🔄 Conexión centralizada
        cursor = db.cursor(dictionary=True)

        # Días de alerta para vencimientos
        dias_alerta = [15, 7, 1]

        for dias in dias_alerta:
            fecha_objetivo = (datetime.now() + timedelta(days=dias)).date()

            # ✅ Cambiamos 'documentos' por 'documentos_empresa'
            cursor.execute("""
                SELECT id, nombre, nit_empresa
                FROM documentos_empresa
                WHERE fecha_vencimiento = %s
            """, (fecha_objetivo,))
            documentos = cursor.fetchall()

            for documento in documentos:
                # Verificar si ya existe una notificación para ese documento y día
                cursor.execute("""
                    SELECT id FROM notificaciones
                    WHERE documento_id = %s AND dias_antes = %s
                """, (documento['id'], dias))
                existe = cursor.fetchone()

                if not existe:
                    cursor.execute("""
                        INSERT INTO notificaciones (documento_id, fecha_envio, dias_antes, enviada_a)
                        VALUES (%s, NOW(), %s, %s)
                    """, (documento['id'], dias, 2))  # 2 = Administrador

                    print(f"✅ Notificación generada para '{documento['nombre']}' ({dias} días antes del vencimiento)")

        db.commit()
        cursor.close()
        db.close()

        print("🔔 Generación de notificaciones completada correctamente.")

    except mysql.connector.Error as err:
        print(f"⚠️ Error generando notificaciones: {err}")
