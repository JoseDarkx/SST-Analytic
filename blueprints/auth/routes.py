from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import get_connection as get_db
from datetime import datetime, timedelta
from werkzeug.security import  check_password_hash
import mysql.connector

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


# --------------------------------------
# RUTA: Inicio de sesión (/iniciar-sesion)
# --------------------------------------
@auth_bp.route('/iniciar-sesion', methods=['GET', 'POST'])
def iniciar_sesion():
    if request.method == 'POST':
        nit_empresa = request.form['nit_empresa']
        usuario = request.form['usuario']
        contraseña = request.form['contraseña']
        print(f"➡️ Intento de login -> NIT: {nit_empresa}, Usuario: {usuario}")

        conexion = get_db()  # 🔄 Conexión centralizada
        cursor = conexion.cursor(dictionary=True)

        # 🔹 Traer usuario con rol y estado
        cursor.execute("""
            SELECT u.*, r.nombre AS rol
            FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            WHERE u.usuario = %s AND u.nit_empresa = %s
        """, (usuario, nit_empresa))
        user = cursor.fetchone()
        print(f"🔍 Resultado de la consulta -> {user}")

        # 🔹 Usuario no encontrado
        if not user:
            flash("❌ Usuario o contraseña incorrectos.", "danger")
            print("❌ Usuario no encontrado en la BD")
            cursor.close()
            conexion.close()
            return render_template('login.html')

        # 🔹 Estado del usuario
        if user.get("estado"):
            if user["estado"].lower() == "bloqueado":
                flash("🚫 Usuario bloqueado por Admin.", "danger")
                print("🚫 Usuario bloqueado por administrador.")
                cursor.close()
                conexion.close()
                return render_template("login.html")

            if user["estado"].lower() != "activo":
                flash("⚠️ Tu cuenta está desactivada. Contacta con el administrador.", "warning")
                print(f"🚫 Usuario con estado no permitido -> {user['estado']}")
                cursor.close()
                conexion.close()
                return render_template("login.html")

        # 🔹 Bloqueo temporal
        if user.get("bloqueo_hasta") and user["bloqueo_hasta"] > datetime.now():
            flash("⏳ Cuenta bloqueada temporalmente. Intenta más tarde.", "danger")
            print(f"⏳ Usuario bloqueado hasta {user['bloqueo_hasta']}")
            cursor.close()
            conexion.close()
            return render_template("login.html")

        # 🔹 Validar contraseña
        if check_password_hash(user['contraseña'], contraseña):
            cursor.execute("""
                UPDATE usuarios 
                SET intentos_fallidos = 0, bloqueo_hasta = NULL
                WHERE id = %s
            """, (user["id"],))
            conexion.commit()
            print("✅ Contraseña correcta. Intentos reiniciados.")

            # Guardar sesión
            session['usuario_id'] = user['id']
            session['usuario'] = user['usuario']
            session['nit_empresa'] = user['nit_empresa']
            session['rol'] = user['rol']
            session['rol_id'] = user['rol_id']
            session['nombre_completo'] = user.get('nombre_completo', 'Usuario')

            flash("✅ Inicio de sesión exitoso.", "success")
            print(f"👤 Usuario en sesión -> ID: {user['id']}, Usuario: {user['usuario']}, Rol: {user['rol']}")

            cursor.close()
            conexion.close()
            return redirect(url_for('auth.dashboard'))
        else:
            # 🔹 Contraseña incorrecta
            intentos = (user.get('intentos_fallidos') or 0) + 1
            bloqueo_hasta = None
            print(f"⚠️ Contraseña incorrecta. Intentos acumulados: {intentos}")

            if intentos >= 3:
                bloqueo_hasta = datetime.now() + timedelta(minutes=5)
                flash("🚫 Demasiados intentos fallidos. Cuenta bloqueada por 5 minutos.", "danger")
                print(f"🚫 Usuario bloqueado hasta {bloqueo_hasta}")
            else:
                flash(f"⚠️ Credenciales incorrectas. Intento {intentos}/3.", "warning")

            cursor.execute("""
                UPDATE usuarios
                SET intentos_fallidos = %s, bloqueo_hasta = %s
                WHERE id = %s
            """, (intentos, bloqueo_hasta, user["id"]))
            conexion.commit()
            print("📌 Intentos fallidos actualizados.")

            cursor.close()
            conexion.close()
            return render_template("login.html")

    print("📄 Cargando página de login...")
    return render_template('login.html')




@auth_bp.route('/cerrar_sesion')
def cerrar_sesion():
    session.clear()  # 🔹 limpia la sesión
    flash("Has cerrado sesión correctamente", "success")
    return redirect(url_for('auth.iniciar_sesion'))


# --------------------------------------
# RUTA: Dashboard principal (/dashboard)
# --------------------------------------
@auth_bp.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    # Conexión a la base de datos
    conexion = get_db()  # 🔄 Conexión centralizada
    cursor = conexion.cursor(dictionary=True)

    # Obtener datos del usuario logueado
    cursor.execute("""
        SELECT u.nombre_completo, r.nombre AS rol, u.nit_empresa
        FROM usuarios u
        JOIN roles r ON u.rol_id = r.id
        WHERE u.id = %s
    """, (session['usuario_id'],))
    usuario = cursor.fetchone()
    rol = usuario['rol']
    nit_usuario = usuario['nit_empresa']

    # Determinar si es Super Administrador
    es_super_admin = rol == 'Super Administrador'

    # Obtener nit seleccionado
    if es_super_admin:
        nit_seleccionado = request.args.get('nit_empresa')
        # Empresas activas para el filtro
        cursor.execute("SELECT nit_empresa, nombre FROM empresas WHERE estado = 'Activa'")
        empresas = cursor.fetchall()
        empresa_usuario = None
    else:
        nit_seleccionado = nit_usuario
        empresas = []
        # Obtener nombre de la empresa del usuario
        cursor.execute("SELECT nombre FROM empresas WHERE nit_empresa = %s AND estado = 'Activa'", (nit_usuario,))
        empresa_usuario = cursor.fetchone()
        if empresa_usuario:
            empresa_usuario = empresa_usuario['nombre']

    # Total de empresas (solo para Super Admin)
    if es_super_admin:
        cursor.execute("SELECT COUNT(*) AS total_empresas FROM empresas WHERE estado = 'Activa'")
        total_empresas = cursor.fetchone()['total_empresas']
    else:
        total_empresas = None  # No mostrar para otros roles

    # Total de evaluaciones (filtradas por empresa)
    cursor.execute("""
        SELECT COUNT(*) AS total_evaluaciones
        FROM evaluaciones e
        JOIN capacitaciones c ON e.capacitacion_id = c.id
        WHERE c.nit_empresa = %s
    """, (nit_seleccionado,))
    total_evaluaciones = cursor.fetchone()['total_evaluaciones']

    # Total de capacitaciones (filtradas)
    cursor.execute("""
        SELECT COUNT(*) AS total_capacitaciones
        FROM capacitaciones
        WHERE nit_empresa = %s
    """, (nit_seleccionado,))
    total_capacitaciones = cursor.fetchone()['total_capacitaciones']

    # Incidentes por tipo (filtrados)
    cursor.execute("""
        SELECT i.tipo, COUNT(*) AS cantidad
        FROM incidentes i
        WHERE i.nit_empresa = %s
        GROUP BY i.tipo
    """, (nit_seleccionado,))
    incidentes_por_tipo = cursor.fetchall()
    incidentes_labels = [i['tipo'] for i in incidentes_por_tipo]
    incidentes_data = [i['cantidad'] for i in incidentes_por_tipo]

    # Documentos por estado (filtrados)
    cursor.execute("""
        SELECT d.estado, COUNT(*) AS cantidad
        FROM documentos_empresa d
        WHERE d.nit_empresa = %s
        GROUP BY d.estado
    """, (nit_seleccionado,))
    documentos_por_estado = cursor.fetchall()
    documentos_labels = [d['estado'] for d in documentos_por_estado]
    documentos_data = [d['cantidad'] for d in documentos_por_estado]

    # Cerrar conexión
    cursor.close()
    conexion.close()

    # Renderizar plantilla
    return render_template(
        'dashboard.html',
        usuario_actual=usuario,
        total_empresas=total_empresas,
        total_evaluaciones=total_evaluaciones,
        total_capacitaciones=total_capacitaciones,
        incidentes_por_tipo=incidentes_por_tipo,
        documentos_por_estado=documentos_por_estado,
        empresas=empresas,
        nit_seleccionado=nit_seleccionado,
        es_super_admin=es_super_admin,
        empresa_usuario=empresa_usuario,
        incidentes_labels=incidentes_labels,
        incidentes_data=incidentes_data,
        documentos_labels=documentos_labels,
        documentos_data=documentos_data
    )

@auth_bp.route('/api/notificaciones')
def api_notificaciones():
    if 'usuario_id' not in session:
        return {"error": "No autenticado"}, 401

    rol_id = session.get('rol_id')
    nit_empresa = session.get('nit_empresa')
    # ✅ Permitir solo Super Administrador (1) y Administrador (2)
    if rol_id not in [1, 2]:
        return {"error": "Sin permisos"}, 403

    db = get_db()  # 🔄 Conexión centralizada
    cursor = db.cursor(dictionary=True)

    # 🔹 Consulta según rol
    consulta = """
        SELECT 
            n.id, 
            n.fecha_envio, 
            n.dias_antes,
            d.nombre AS documento_nombre,
            d.nit_empresa,
            d.fecha_vencimiento
        FROM notificaciones n
        INNER JOIN documentos_empresa d ON n.documento_id = d.id
    """

    if rol_id == 2:  # Administrador: solo su empresa
        consulta += " WHERE d.nit_empresa = %s ORDER BY n.fecha_envio DESC"
        cursor.execute(consulta, (nit_empresa,))
    else:  # Super Administrador: todas
        consulta += " ORDER BY n.fecha_envio DESC"
        cursor.execute(consulta)

    notificaciones = cursor.fetchall()

    cursor.close()
    db.close()

    return {"notificaciones": notificaciones}, 200


# --------------------------------------
# VISTA: Notificaciones
# --------------------------------------
@auth_bp.route('/notificaciones')
def notificaciones_view():
    if 'usuario_id' not in session:
        return redirect(url_for('auth.iniciar_sesion'))

    rol_id = session.get('rol_id')

    # Permitir solo Super Administrador (1) y Administrador (2)
    if rol_id not in [1, 2]:
        flash("No tienes permisos para ver esta página.", "danger")
        return redirect(url_for('auth.dashboard'))

    return render_template('notificaciones.html')

@auth_bp.route('/api/usuario_actual')
def api_usuario_actual():
    if 'usuario_id' not in session:
        return {"error": "No autenticado"}, 401

    usuario_id = session.get('usuario_id')
    nombre = session.get('nombre_completo', 'Usuario')
    rol_id = session.get('rol_id')
    empresa = session.get('nombre_empresa', '')

    # Traducir el rol_id a nombre legible
    roles = {
        1: "Super Administrador",
        2: "Administrador",
        3: "Empleado"
    }
    rol_nombre = roles.get(rol_id, "Desconocido")

    return {
        "usuario_id": usuario_id,
        "nombre_completo": nombre,
        "rol": rol_nombre,
        "empresa": empresa
    }, 200
