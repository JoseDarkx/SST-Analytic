# routes/usuarios.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
from werkzeug.security import generate_password_hash
from utils.permisos import  requiere_roles


usuarios_bp = Blueprint("usuarios", __name__)

# --------------------------------------------------------------
# RUTA: Registro de usuario
# --------------------------------------------------------------
@usuarios_bp.route('/registrarse', methods=['GET', 'POST'])
@requiere_roles("Super Administrador", "Administrador")
def registrarse():
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))
    
    if request.method == 'POST':
        try:
            print(">>> Entró al endpoint /registerUsu [POST]")

            connection = get_db()  # 🔄 Conexión centralizada
            cursor = connection.cursor(dictionary=True)
            print(">>> Conexión establecida con la BD")
            
            

            # Datos del formulario
            nombre_completo = request.form.get('nombre_completo')
            correo = request.form.get('correo')
            usuario = request.form.get('usuario')
            contraseña = generate_password_hash(request.form.get('contraseña'))
            nit_empresa = request.form.get('nit_empresa')
            estado = request.form.get('estado')
            rol_id = request.form.get('rol_id')

            print(f">>> Datos recibidos: {nombre_completo}, {correo}, {usuario}, empresa={nit_empresa}, rol={rol_id}")

            # Verificar si ya existe el usuario o el correo
            cursor.execute("SELECT * FROM usuarios WHERE correo = %s OR usuario = %s", (correo, usuario))
            existente = cursor.fetchone()
            print(">>> Usuario existente:", existente)

            if existente:
                if usuario == existente['usuario'] and correo == existente['correo']:
                    flash("Este usuario y correo ya fueron registrados anteriormente.", "error")
                elif correo == existente['correo']:
                    flash("Este correo ya fue registrado anteriormente.", "error")
                elif usuario == existente['usuario']:
                    flash("Este usuario ya fue registrado anteriormente.", "error")
                
                return redirect(url_for('usuarios.usuarios'))
            
            cursor.execute("SELECT nit_empresa, nombre FROM empresas WHERE estado='Activa' ORDER BY nombre")
            empresas = cursor.fetchall()

            # Insertar nuevo usuario
            cursor.execute("""
                INSERT INTO usuarios (nombre_completo, correo, usuario, contraseña, estado, nit_empresa, rol_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (nombre_completo, correo, usuario, contraseña, estado, nit_empresa, rol_id))
            connection.commit()
            print(">>> Usuario registrado exitosamente")

            flash("Usuario registrado exitosamente.", "success")
            return redirect(url_for('usuarios.usuarios'))

        except mysql.connector.Error as e:
            print(f">>> ERROR registrando usuario: {e}")
            flash("Error al registrar usuario", "error")
            if 'connection' in locals():
                connection.rollback()
            return redirect(url_for('usuarios.usuarios'))

        finally:
            if 'cursor' in locals():
                cursor.close()
                print(">>> Cursor cerrado")
            if 'connection' in locals():
                connection.close()
                print(">>> Conexión cerrada")

    # Si es GET, cargamos roles y empresas
    try:
        print(">>> Entró al endpoint /registerUsu [GET]")

        connection = get_db()  # 🔄 Conexión centralizada
        cursor = connection.cursor(dictionary=True)
        print(">>> Conexión establecida con la BD")

        cursor.execute("SELECT id, nombre FROM roles")
        roles = cursor.fetchall()
        print(f">>> Roles obtenidos: {len(roles)}")

        cursor.execute("SELECT nit_empresa, nombre FROM empresas")
        empresas = cursor.fetchall()
        print(f">>> Empresas obtenidas: {len(empresas)}")

        # Renderiza tu template
        return render_template('usuarios/usuarios.html', roles=roles, empresas=empresas)

    except mysql.connector.Error as e:
        print(f">>> ERROR cargando roles/empresas: {e}")
        return render_template('usuarios.html', roles=[], empresas=[])

    finally:
        if 'cursor' in locals():
            cursor.close()
            print(">>> Cursor cerrado")
        if 'connection' in locals():
            connection.close()
            print(">>> Conexión cerrada")

# --------------------------------------------------------------
# RUTA: Listado de usuarios con búsqueda
# --------------------------------------------------------------
@usuarios_bp.route('/usuarios', methods=['GET'])
@requiere_roles("Super Administrador", "Administrador")
def usuarios():
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))
    
    nombre = request.args.get('nombre', '')
    nit = request.args.get('nit', '')
    documento = request.args.get('documento', '')
    pagina_actual = int(request.args.get('pagina', 1))
    registros_por_pagina = 10  

    usuario = None
    roles = []
    empresas = []

    try:
        connection = get_db()  # 🔄 Conexión centralizada
        cursor = connection.cursor(dictionary=True)

        # Datos del usuario actual
        cursor.execute("""
            SELECT u.id, u.nombre_completo, r.nombre AS rol
            FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            WHERE u.id = %s
        """, (session.get('usuario_id'),))
        usuario = cursor.fetchone()

        # Consultar roles y empresas (para el modal)
        cursor.execute("SELECT id, nombre FROM roles")
        roles = cursor.fetchall()

        cursor.execute("SELECT nit_empresa, nombre FROM empresas WHERE estado = 'Activa'")
        empresas = cursor.fetchall()

        # Calcular total de registros
        query_count = """
            SELECT COUNT(*) as total
            FROM usuarios u
            LEFT JOIN empresas e ON u.nit_empresa = e.nit_empresa
            LEFT JOIN roles r ON u.rol_id = r.id
            WHERE 1=1
        """
        params = []
        if nombre:
            query_count += " AND u.nombre_completo LIKE %s"
            params.append(f"%{nombre}%")
        if nit:
            query_count += " AND u.nit_empresa LIKE %s"
            params.append(f"%{nit}%")
        if documento:
            query_count += " AND u.usuario LIKE %s"
            params.append(f"%{documento}%")

        cursor.execute(query_count, params)
        total_usuarios = cursor.fetchone()['total']

        # Consultar usuarios con paginación
        offset = (pagina_actual - 1) * registros_por_pagina
        query = """
            SELECT u.id, u.nombre_completo, u.correo, u.usuario, u.contraseña, u.estado,
                   e.nombre AS nombre_empresa,
                   r.nombre AS nombre_rol
            FROM usuarios u
            LEFT JOIN empresas e ON u.nit_empresa = e.nit_empresa
            LEFT JOIN roles r ON u.rol_id = r.id
            WHERE 1=1
        """
        params2 = params.copy()
        if nombre:
            query += " AND u.nombre_completo LIKE %s"
        if nit:
            query += " AND u.nit_empresa LIKE %s"
        if documento:
            query += " AND u.usuario LIKE %s"
        query += " ORDER BY u.nombre_completo ASC LIMIT %s OFFSET %s"
        params2.extend([registros_por_pagina, offset])

        cursor.execute(query, params2)
        usuarios = cursor.fetchall()
        total_paginas = (total_usuarios + registros_por_pagina - 1) // registros_por_pagina

    except mysql.connector.Error as e:
        print(f"ERROR listando usuarios: {e}")
        usuarios = []
        total_paginas = 1
        pagina_actual = 1
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

    # 🔹 Ahora enviamos roles y empresas al template
    return render_template(
        'usuarios.html',
        usuarios=usuarios,
        usuario_actual=usuario,
        pagina_actual=pagina_actual,
        total_paginas=total_paginas,
        nombre=nombre,
        nit=nit,
        documento=documento,
        roles=roles,
        empresas=empresas
    )


# --------------------------------------------------------------
# RUTA: Cambiar estado (/cambiar_estado/<id>) GET
# --------------------------------------------------------------
@usuarios_bp.route('/cambiar_estado/<int:id>')
@requiere_roles("Super Administrador", "Administrador")
def cambiar_estado(id):
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    try:
        print(f">>> Entró al endpoint /cambiar_estado/{id}")

        conexion = get_db()  # 🔄 Conexión centralizada
        cur = conexion.cursor(dictionary=True)
        print(">>> Conexión establecida con la BD")

        cur.execute("SELECT estado FROM usuarios WHERE id=%s", (id,))
        row = cur.fetchone()
        print(">>> Estado actual:", row)

        if not row:
            flash("Usuario no encontrado.", "error")
            return redirect(url_for('usuarios.usuarios'))

        nuevo = 'Bloqueado' if row['estado'] == 'Activo' else 'Activo'
        cur.execute("UPDATE usuarios SET estado=%s WHERE id=%s", (nuevo, id))
        conexion.commit()
        print(f">>> Estado cambiado a {nuevo}")

        flash(f"Estado actualizado a {nuevo}.", "info")
        return redirect(url_for('usuarios.usuarios'))

    except mysql.connector.Error as e:
        conexion.rollback()
        print(f">>> ERROR en /cambiar_estado/{id}: {e}")
        flash("Error al cambiar el estado.", "error")
        return redirect(url_for('usuarios.usuarios'))
    finally:
        if 'cur' in locals():
            cur.close()
            print(">>> Cursor cerrado")
        if 'conexion' in locals():
            conexion.close()
            print(">>> Conexión cerrada")

# --------------------------------------------------------------
# RUTA: Editar Usuario (/editar_usuario/<id>) GET / POST
# --------------------------------------------------------------
@usuarios_bp.route('/editar_usuario/<int:id>', methods=['GET', 'POST'])
@requiere_roles("Super Administrador", "Administrador")
def editar_usuario(id):
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    conexion = None
    cursor = None
    try:
        conexion = get_db()  # 🔄 Conexión centralizada
        cursor = conexion.cursor(dictionary=True)
        print(f">>> Conexión establecida para editar usuario {id}")

        if request.method == "GET":
            # Obtener datos del usuario
            cursor.execute("SELECT * FROM usuarios WHERE id = %s", (id,))
            usuario = cursor.fetchone()

            # Cargar empresas y roles
            cursor.execute("SELECT nit_empresa, nombre FROM empresas")
            empresas = cursor.fetchall()

            cursor.execute("SELECT id, nombre FROM roles")
            roles = cursor.fetchall()

            return render_template("usuarios/usuarios.html", usuario=usuario, empresas=empresas, roles=roles)

        if request.method == "POST":
            data = request.form
            rol_actual = session.get('rol_nombre')
            print(f">>> Rol del usuario actual: {rol_actual}")
            print(f">>> Datos recibidos: {dict(data)}")

            # ---------------------------
            # Campos editables por rol
            # ---------------------------
            campos_super_admin = ['nombre_completo', 'correo', 'usuario', 'estado', 'nit_empresa', 'rol_id']
            campos_admin = ['nombre_completo', 'correo', 'usuario', 'estado']

            # Determinar qué campos se pueden actualizar según el rol
            campos_permitidos = campos_super_admin if rol_actual == "Super Administrador" else campos_admin

            # Construcción de UPDATE dinámico
            updates = []
            values = []
            for campo in campos_permitidos:
                if campo in data:
                    updates.append(f"{campo} = %s")
                    values.append(data.get(campo))

            if updates:
                query = f"UPDATE usuarios SET {', '.join(updates)} WHERE id = %s"
                values.append(id)
                print("🔧 Ejecutando query:", query, values)
                cursor.execute(query, values)
                conexion.commit()
                print("✅ Usuario actualizado correctamente")

            flash("Usuario actualizado correctamente", "success")
            return redirect(url_for("usuarios.usuarios"))

    except mysql.connector.Error as e:
        if conexion:
            conexion.rollback()
        print(f"❌ Error al editar usuario: {e}")
        flash("Error al editar el usuario.", "error")
        return redirect(url_for("usuarios.usuarios"))

    finally:
        if cursor: cursor.close()
        if conexion: conexion.close()
        print(">>> Conexión cerrada")


# --------------------------------------------------------------
# RUTA: Eliminar usuario (/eliminar_usuario/<id>) GET
# --------------------------------------------------------------
@usuarios_bp.route('/eliminar_usuario/<int:id>')
@requiere_roles("Super Administrador")
def eliminar_usuario(id):
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    try:
        print(f">>> Entró al endpoint /eliminar_usuario/{id}")

        conexion = get_db()  # 🔄 Conexión centralizada
        cur = conexion.cursor()
        print(">>> Conexión establecida con la BD")

        cur.execute("DELETE FROM usuarios WHERE id=%s", (id,))
        conexion.commit()
        print(">>> Usuario eliminado correctamente")

        flash("Usuario eliminado correctamente.", "danger")
        return redirect(url_for('usuarios.usuarios'))

    except mysql.connector.Error as e:
        conexion.rollback()
        print(f">>> ERROR en /eliminar_usuario/{id}: {e}")
        flash("Error al eliminar el usuario (revisa llaves foráneas).", "error")
        return redirect(url_for('usuarios.usuarios'))
    finally:
        if 'cur' in locals():
            cur.close()
            print(">>> Cursor cerrado")
        if 'conexion' in locals():
            conexion.close()
            print(">>> Conexión cerrada")


# ============================================================
# API: Listar Usuarios
# ============================================================
@usuarios_bp.route('/api/usuarios', methods=['GET'])
def api_listar_usuarios():
    conexion = None
    cursor = None
    try:
        print(">>> Entró al endpoint GET /api/usuarios")

        # Conexión a la BD
        conexion = get_db()  # 🔄 Conexión centralizada
        cursor = conexion.cursor(dictionary=True)
        print(">>> Conexión establecida con la BD")

        # Consulta de usuarios (puedes ajustar campos si lo necesitas)
        cursor.execute("""
            SELECT u.id, u.nombre_completo, u.correo, u.usuario, 
                u.estado, u.nit_empresa, r.nombre AS rol
            FROM usuarios u
            LEFT JOIN roles r ON u.rol_id = r.id
            ORDER BY u.id ASC
        """)
        usuarios = cursor.fetchall()
        print(f">>> Usuarios encontrados: {len(usuarios)}")

        # Mostrar en consola uno por uno
        for i, u in enumerate(usuarios, start=1):
            print(f" {i}. {u['nombre_completo']} | Usuario: {u['usuario']} "
                f"| Correo: {u['correo']} | Rol: {u['rol']} | Estado: {u['estado']}")

        if not usuarios:
            return jsonify({"status": "success", "data": [], "message": "No hay usuarios registrados"}), 200

        return jsonify({"status": "success", "data": usuarios}), 200

    except mysql.connector.Error as e:
        print(f"❌ ERROR en API GET /api/usuarios: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
            print(">>> Cursor cerrado en GET /api/usuarios")
        if conexion:
            conexion.close()
            print(">>> Conexión cerrada en GET /api/usuarios")
