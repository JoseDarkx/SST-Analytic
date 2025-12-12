# routes/usuarios.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
from werkzeug.security import generate_password_hash


usuarios_bp = Blueprint("usuarios", __name__)

# --------------------------------------------------------------
# RUTA: Registro de usuario
# --------------------------------------------------------------
@usuarios_bp.route('/registrarse', methods=['GET', 'POST'])
def registrarse():
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
                
                return redirect(url_for('usuarios.registrarse'))

            # Insertar nuevo usuario
            cursor.execute("""
                INSERT INTO usuarios (nombre_completo, correo, usuario, contraseña, estado, nit_empresa, rol_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (nombre_completo, correo, usuario, contraseña, estado, nit_empresa, rol_id))
            connection.commit()
            print(">>> Usuario registrado exitosamente")

            flash("Usuario registrado exitosamente.", "success")
            return redirect(url_for('usuarios.registrarse'))

        except mysql.connector.Error as e:
            print(f">>> ERROR registrando usuario: {e}")
            flash("Error al registrar usuario", "error")
            if 'connection' in locals():
                connection.rollback()
            return redirect(url_for('usuarios.registrarse'))

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
        return render_template('registerUsu.html', roles=roles, empresas=empresas)

    except mysql.connector.Error as e:
        print(f">>> ERROR cargando roles/empresas: {e}")
        return render_template('registerUsu.html', roles=[], empresas=[])

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
def usuarios():
    nombre = request.args.get('nombre', '')
    nit = request.args.get('nit', '')
    documento = request.args.get('documento', '')

    usuario = None

    try:
        connection = get_db()  # 🔄 Conexión centralizada
        cursor = connection.cursor(dictionary=True)

        # Obtener datos del usuario actual
        cursor.execute("""
            SELECT u.id, u.nombre_completo, r.nombre AS rol
            FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            WHERE u.id = %s
        """, (session.get('usuario_id'),))
        usuario = cursor.fetchone()


        # Consulta principal
        query = """
            SELECT u.id, u.nombre_completo, u.correo, u.usuario, u.contraseña, u.estado,
            e.nombre AS nombre_empresa,
            r.nombre AS nombre_rol
            FROM usuarios u
            LEFT JOIN empresas e ON u.nit_empresa = e.nit_empresa
            LEFT JOIN roles r ON u.rol_id = r.id
            WHERE 1=1
        """
        params = []

        if nombre:
            query += " AND u.nombre_completo LIKE %s"
            params.append(f"%{nombre}%")
        if nit:
            query += " AND u.nit_empresa LIKE %s"
            params.append(f"%{nit}%")
        if documento:
            query += " AND u.usuario LIKE %s"
            params.append(f"%{documento}%")

        query += " ORDER BY u.nombre_completo ASC"
        cursor.execute(query, params)
        usuarios = cursor.fetchall()
        
        

    except mysql.connector.Error as e:
        print(f"ERROR listando usuarios: {e}")
        usuarios = []
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()
            

    # PASAR usuario_actual a la plantilla
    return render_template('usuarios.html', usuarios=usuarios, usuario_actual=usuario)




# --------------------------------------------------------------
# RUTA: Cambiar estado (/cambiar_estado/<id>) GET
# --------------------------------------------------------------
@usuarios_bp.route('/cambiar_estado/<int:id>')
def cambiar_estado(id):
    if 'usuario' not in session:
        return redirect(url_for('iniciar_sesion'))

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
def editar_usuario(id):
    try:
        print(f">>> Entró al endpoint /editar_usuario/{id}")

        conexion = get_db()  # 🔄 Conexión centralizada
        cursor = conexion.cursor(dictionary=True)
        print(">>> Conexión establecida con la BD")

        if request.method == "GET":
            cursor.execute("SELECT * FROM usuarios WHERE id = %s", (id,))
            usuario = cursor.fetchone()
            print(">>> Usuario obtenido:", usuario)

            cursor.execute("SELECT nit_empresa, nombre FROM empresas")
            empresas = cursor.fetchall()
            print(f">>> Empresas obtenidas: {len(empresas)}")

            cursor.execute("SELECT id, nombre FROM roles")
            roles = cursor.fetchall()
            print(f">>> Roles obtenidos: {len(roles)}")

            return render_template("editar_usuario.html", usuario=usuario, empresas=empresas, roles=roles)

        if request.method == "POST":
            nombre_completo = request.form.get("nombre_completo")
            correo = request.form.get("correo")
            usuario_nombre = request.form.get("usuario")
            estado = request.form.get("estado")
            # Aunque deshabilitaste empresa y rol, igual los envías en campos ocultos
            nit_empresa = request.form.get("nit_empresa")
            rol_id = request.form.get("rol_id")
                
            query = """
                UPDATE usuarios
                SET nombre_completo=%s, correo=%s, usuario=%s, estado=%s
                WHERE id=%s
            """
            cursor.execute(query, (nombre_completo, correo, usuario_nombre, estado, id))
            conexion.commit()
            flash("Usuario actualizado correctamente", "success")
            return redirect(url_for("usuarios.usuarios"))

    except mysql.connector.Error as e:
        print(f">>> ERROR en /editar_usuario/{id}: {e}")
        flash("Error al editar el usuario.", "error")
        return redirect(url_for("usuarios.usuarios"))
    finally:
        if 'cursor' in locals():
            cursor.close()
            print(">>> Cursor cerrado")
        if 'conexion' in locals():
            conexion.close()
            print(">>> Conexión cerrada")

# --------------------------------------------------------------
# RUTA: Eliminar usuario (/eliminar_usuario/<id>) GET
# --------------------------------------------------------------
@usuarios_bp.route('/eliminar_usuario/<int:id>')
def eliminar_usuario(id):
    if 'usuario' not in session:
        return redirect(url_for('iniciar_sesion'))

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
