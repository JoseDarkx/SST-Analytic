from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash
from extensions import get_db, mail
from flask_mail import Message
import secrets
from datetime import datetime, timedelta
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

recuperacion_bp = Blueprint('recuperacion', __name__)

# ========================================
# RUTA: Solicitar recuperación de contraseña
# ========================================
@recuperacion_bp.route('/recuperar_contraseña', methods=['GET', 'POST'])
def recuperar_contraseña():
    conexion = get_db()
    cursor = conexion.cursor(dictionary=True)

    if request.method == "POST":
        nit = request.form.get("nit_empresa", "").strip()
        correo = request.form.get("correo", "").strip().lower()

        # Validación básica
        if not nit or not correo:
            flash("Por favor, complete todos los campos", "danger")
            cursor.close()
            return redirect(url_for("recuperacion.recuperar_contraseña"))

        try:
            # Verificar si el usuario existe
            cursor.execute(
                "SELECT * FROM usuarios WHERE correo = %s AND nit_empresa = %s",
                (correo, nit)
            )
            usuario = cursor.fetchone()

            if usuario:
                # Generar token temporal válido por 1 hora
                token = secrets.token_urlsafe(32)
                expiracion = datetime.now() + timedelta(hours=1)

                # Eliminar tokens anteriores del mismo correo
                cursor.execute(
                    "DELETE FROM recuperacion_tokens WHERE correo = %s",
                    (correo,)
                )

                # Guardar nuevo token en BD
                cursor.execute(
                    "INSERT INTO recuperacion_tokens (correo, token, fecha_expiracion, usado) VALUES (%s, %s, %s, FALSE)",
                    (correo, token, expiracion)
                )

                # Verificar si ya existe una solicitud pendiente
                cursor.execute(
                    "SELECT id FROM recuperacion_contraseña WHERE nit_empresa = %s AND correo = %s AND estado = 'Pendiente'",
                    (nit, correo)
                )
                solicitud_existente = cursor.fetchone()

                if not solicitud_existente:
                    # Guardar solicitud para admin
                    cursor.execute(
                        "INSERT INTO recuperacion_contraseña (nit_empresa, correo, fecha_solicitud, estado) "
                        "VALUES (%s, %s, NOW(), 'Pendiente')",
                        (nit, correo)
                    )

                conexion.commit()

                # Enviar correo con enlace de recuperación
                try:
                    enlace = url_for('recuperacion.cambiar_contraseña', token=token, _external=True)
                    
                    msg = Message(
                        subject="🔐 Recuperación de Contraseña - Sistema SST",
                        recipients=[correo]
                    )
                    
                    msg.html = f"""
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #2c3e50;">Recuperación de Contraseña</h2>
                        <p>Hola <strong>{usuario['nombre_completo']}</strong>,</p>
                        <p>Hemos recibido una solicitud para restablecer tu contraseña.</p>
                        <p>Haz clic en el siguiente botón para crear una nueva contraseña:</p>
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{enlace}" style="background-color: #3498db; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">
                                Restablecer Contraseña
                            </a>
                        </div>
                        <p><strong>⚠️ Importante:</strong> Este enlace expira en 1 hora por seguridad.</p>
                        <p>Si no solicitaste este cambio, puedes ignorar este correo.</p>
                        <hr style="margin: 30px 0;">
                        <p style="color: #7f8c8d; font-size: 12px;">Sistema de Gestión SST</p>
                    </div>
                    """
                    
                    mail.send(msg)
                    flash("✅ Se ha enviado un correo con el enlace para restablecer tu contraseña", "success")
                    logger.info(f"Correo de recuperación enviado a {correo}")
                    
                except Exception as mail_error:
                    logger.error(f"Error enviando correo: {mail_error}")
                    flash("❌ Error al enviar el correo. Contacta al administrador.", "danger")
            else:
                flash("❌ No se encontró un usuario con ese NIT y correo", "danger")
                logger.warning(f"Intento de recuperación fallido para NIT: {nit}, Correo: {correo}")

        except Exception as e:
            conexion.rollback()
            logger.error(f"Error en recuperación de contraseña: {e}")
            flash("❌ Error interno del servidor. Contacta al administrador.", "danger")
            
        finally:
            cursor.close()
            return redirect(url_for("recuperacion.recuperar_contraseña"))

    # GET request - renderizar template
    cursor.close()
    return render_template("recuperar_contraseña.html")


# ========================================
# RUTA: Cambiar contraseña vía token
# ========================================
@recuperacion_bp.route('/cambiar_contraseña/<token>', methods=['GET', 'POST'])
def cambiar_contraseña(token):
    conexion = get_db()
    cursor = conexion.cursor(dictionary=True)
    
    try:
        # Verificar token válido y no usado
        cursor.execute(
            "SELECT * FROM recuperacion_tokens WHERE token = %s AND usado = FALSE AND fecha_expiracion > NOW()",
            (token,)
        )
        registro = cursor.fetchone()

        if not registro:
            flash("❌ El enlace es inválido o ha expirado", "danger")
            cursor.close()
            return redirect(url_for('recuperacion.recuperar_contraseña'))

        if request.method == "POST":
            nueva_password = request.form.get("nueva_contraseña", "").strip()
            confirmar_password = request.form.get("confirmar_contraseña", "").strip()

            # Validaciones
            if not nueva_password or not confirmar_password:
                flash("❌ Por favor, complete todos los campos", "danger")
                return render_template("cambiar_contraseña.html", token=token)

            if nueva_password != confirmar_password:
                flash("❌ Las contraseñas no coinciden", "danger")
                return render_template("cambiar_contraseña.html", token=token)

            if len(nueva_password) < 6:
                flash("❌ La contraseña debe tener al menos 6 caracteres", "danger")
                return render_template("cambiar_contraseña.html", token=token)

            # Hash de la nueva contraseña
            nueva_contrasena_hash = generate_password_hash(nueva_password)

            # Actualizar contraseña del usuario
            cursor.execute(
                "UPDATE usuarios SET contraseña = %s WHERE correo = %s",
                (nueva_contrasena_hash, registro['correo'])
            )

            # Marcar token como usado
            cursor.execute(
                "UPDATE recuperacion_tokens SET usado = TRUE WHERE id = %s",
                (registro['id'],)
            )

            # Marcar solicitud admin como atendida por usuario
            cursor.execute(
                "UPDATE recuperacion_contraseña "
                "SET estado = 'Atendida', fecha_atencion = NOW() "
                "WHERE correo = %s AND estado = 'Pendiente'",
                (registro['correo'],)
            )

            
            conexion.commit()

            flash("✅ Contraseña actualizada correctamente", "success")
            logger.info(f"Contraseña actualizada para usuario: {registro['correo']}")
            cursor.close()
            return redirect(url_for('auth.iniciar_sesion'))

    except Exception as e:
        conexion.rollback()
        print("Error al cambiar contraseña:", e)   # 👈 Esto te dirá el error real en consola
        logger.error(f"Error al cambiar contraseña: {e}")
        flash("❌ Error interno del servidor", "danger")
        cursor.close()
        return redirect(url_for('recuperacion.recuperar_contraseña'))

    # GET request - mostrar formulario
    cursor.close()
    return render_template("cambiar_contraseña.html", token=token)


# ========================================
# RUTA: Panel de solicitudes para Admin
# ========================================
@recuperacion_bp.route('/solicitudes_contrasena', methods=['GET', 'POST'])
def solicitudes_contrasena():
    """Panel de solicitudes de recuperación de contraseña - Solo Admin/Super Admin"""

    # --- Verificar sesión ---
    usuario_id = session.get('usuario_id')
    if not usuario_id:
        logger.warning("Intento de acceso sin sesión a /solicitudes_contrasena")
        flash("❌ Debe iniciar sesión para acceder", "danger")
        return redirect(url_for('auth.iniciar_sesion'))

    conexion = get_db()
    cursor = conexion.cursor(dictionary=True)

    try:
        # --- Obtener datos del usuario actual ---
        cursor.execute("""
            SELECT u.nombre_completo, r.nombre AS rol
            FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            WHERE u.id = %s
        """, (usuario_id,))
        usuario = cursor.fetchone()

        if not usuario:
            logger.error(f"Usuario con ID {usuario_id} no encontrado en BD")
            flash("❌ Usuario no encontrado", "danger")
            return redirect(url_for('auth.iniciar_sesion'))

        # --- Verificar permisos de admin (case-insensitive y múltiples nombres posibles) ---
        rol_usuario = usuario['rol'].strip().lower()
        roles_admin = ['admin', 'super admin', 'super administrador']  # todos los valores válidos de admin

        if rol_usuario not in roles_admin:
            logger.warning(f"Usuario {usuario['nombre_completo']} con rol '{usuario['rol']}' sin permisos intentando acceder a solicitudes")
            flash("❌ No tiene permisos para acceder a esta sección", "danger")
            # Renderizamos dashboard con mensaje, evitando redirect recursivo
            return render_template('dashboard.html', usuario_actual=usuario, mensaje="No tienes permisos para solicitudes de contraseña")

        # --- Procesar formulario POST (admin cambia contraseña) ---
        if request.method == 'POST':
            solicitud_id = request.form.get('solicitud_id')
            nueva_contrasena = request.form.get('nueva_contrasena', '').strip()

            if not nueva_contrasena or len(nueva_contrasena) < 6:
                flash("❌ La contraseña debe tener al menos 6 caracteres", "danger")
            else:
                cursor.execute("SELECT correo FROM recuperacion_contraseña WHERE id = %s", (solicitud_id,))
                solicitud = cursor.fetchone()

                if solicitud:
                    correo = solicitud['correo']
                    nueva_contrasena_hash = generate_password_hash(nueva_contrasena)

                    cursor.execute(
                        "UPDATE usuarios SET contraseña = %s WHERE correo = %s",
                        (nueva_contrasena_hash, correo)
                    )
                    cursor.execute(
                        "UPDATE recuperacion_contraseña SET estado = 'Atendida', fecha_atencion = NOW() WHERE id = %s",
                        (solicitud_id,)
                    )
                    conexion.commit()
                    flash(f"✅ Contraseña actualizada para {correo}", "success")
                    logger.info(f"Admin {usuario['nombre_completo']} cambió contraseña para {correo}")
                else:
                    flash("❌ Solicitud no encontrada", "danger")

        # --- Obtener todas las solicitudes ---
        cursor.execute("""
            SELECT r.*, u.nombre_completo 
            FROM recuperacion_contraseña r
            LEFT JOIN usuarios u ON r.correo = u.correo
            ORDER BY r.fecha_solicitud DESC
        """)
        solicitudes = cursor.fetchall()

    except Exception as e:
        logger.error(f"Error en solicitudes_contrasena: {e}")
        flash("❌ Error al cargar las solicitudes", "danger")
        solicitudes = []

    finally:
        cursor.close()

    # Renderizar template de solicitudes con info del usuario
    return render_template('solicitudes_contrasena.html', solicitudes=solicitudes, usuario_actual=usuario)



# ========================================
# API: Listar solicitudes de recuperación
# ========================================
@recuperacion_bp.route('/api/recuperar_contraseña', methods=['GET'])
def api_listar_recuperacion():
    conexion = None
    cursor = None
    try:
        print(">>> Entró al endpoint GET /api/recuperar_contraseña")

        # Conexión a la base de datos
        conexion = get_db()
        cursor = conexion.cursor(dictionary=True)
        print(">>> Conexión establecida con la BD")

        # Traer todas las solicitudes
        cursor.execute("""
            SELECT id, nit_empresa, correo, fecha_solicitud, estado
            FROM recuperacion_contraseña
            ORDER BY fecha_solicitud DESC
        """)
        solicitudes = cursor.fetchall()
        print(f">>> Solicitudes encontradas: {len(solicitudes)}")

        # Mostrar en consola
        for i, solicitud in enumerate(solicitudes, start=1):
            print(f" {i}. NIT: {solicitud['nit_empresa']} | "
                f"Correo: {solicitud['correo']} | "
                f"Fecha: {solicitud['fecha_solicitud']} | "
                f"Estado: {solicitud['estado']}")

        if not solicitudes:
            return jsonify({"status": "success", "data": [], "message": "No hay solicitudes registradas"}), 200

        return jsonify({"status": "success", "data": solicitudes}), 200

    except Exception as e:
        print(f"❌ ERROR en API GET recuperar_contraseña: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
            print(">>> Cursor cerrado en API GET recuperar_contraseña")
        if conexion:
            conexion.close()
            print(">>> Conexión cerrada en API GET recuperar_contraseña")