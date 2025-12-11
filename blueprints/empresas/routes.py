import os
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session, jsonify, send_from_directory, abort, current_app
)
from werkzeug.utils import secure_filename
import mysql.connector
from extensions import get_db
from utils.permisos import requiere_roles

empresas_bp = Blueprint('empresas', __name__, url_prefix='/empresas')


UPLOAD_CERT_FOLDER = os.path.join("static", "uploads", "empresas")
UPLOAD_LOGO_FOLDER = os.path.join("static", "uploads", "logos")

os.makedirs(UPLOAD_CERT_FOLDER, exist_ok=True)
os.makedirs(UPLOAD_LOGO_FOLDER, exist_ok=True)


# ------------------------------
# Ruta: Registro empresa
# ------------------------------
@empresas_bp.route('/registro-empresa', methods=['POST'])
@requiere_roles("Super Administrador", "Administrador")
def registro_empresa():
    try:
        nit = request.form.get('nit_empresa')
        nombre = request.form.get('nombre')
        estado = request.form.get('estado') or "Activa"

        certificado = request.files.get('certificado_representacion')
        certificado_url = None

        UPLOAD_FOLDER = os.path.join(current_app.root_path, "static", "uploads", "empresas")
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        if certificado and certificado.filename:
            nombre_cert = secure_filename(certificado.filename)
            nombre_guardado = f"{nit}_cert_{nombre_cert}"
            certificado.save(os.path.join(UPLOAD_FOLDER, nombre_guardado))
            # Guardamos SOLO el nombre del archivo en la BD
            certificado_url = nombre_guardado


        connection = get_db()
        cursor = connection.cursor()

        # Revisar si ya existe la empresa
        cursor.execute("SELECT nit_empresa FROM empresas WHERE nit_empresa = %s", (nit,))
        if cursor.fetchone():
            return {"message": "La empresa con ese NIT ya está registrada", "status": "error"}, 400

        # Calcular nuevo id manualmente
        cursor.execute("SELECT MAX(id) FROM empresas")
        max_id = cursor.fetchone()[0] or 0
        nuevo_id = max_id + 1

        correo = request.form.get('correo') or ""
        telefono = request.form.get('telefono') or ""
        direccion = request.form.get('direccion') or ""
        representante = request.form.get('representante_legal') or ""
        cedula = request.form.get('cedula_representante') or ""
        cargo = request.form.get('cargo') or ""
        actividad = request.form.get('actividad') or ""
        codigo_ciiu = request.form.get('codigo_ciiu') or ""
        observaciones = request.form.get('observaciones') or ""


        cursor.execute("""
            INSERT INTO empresas (
                id, nit_empresa, nombre, correo, telefono, direccion,
                representante_legal, cedula_representante, cargo,
                actividad, codigo_ciiu, observaciones, estado, certificado_representacion
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            nuevo_id, nit, nombre, correo, telefono, direccion,
            representante, cedula, cargo, actividad, codigo_ciiu,
            observaciones, estado, certificado_url
        ))


        connection.commit()
        return {"message": "Empresa registrada correctamente", "status": "success"}

    except Exception as e:
        print("❌ Error en registro_empresa:", e)
        return {"message": str(e), "status": "error"}, 400


# ------------------------------
# Ruta: Listar empresas
# ------------------------------
@empresas_bp.route('/')
@requiere_roles("Super Administrador", "Administrador")
def listar_empresas():
    print("➡️ Entrando a ruta /empresas")
    if 'usuario' not in session:
        print("⚠️ Usuario no autenticado, redirigiendo a login")
        return redirect(url_for('auth.iniciar_sesion'))

    empresas_list = []
    empresas_opciones = []

    try:
        connection = get_db()
        cursor = connection.cursor(dictionary=True)

        # Parámetros de búsqueda y filtrado
        buscar_nombre = request.args.get('nombre', '')
        buscar_nit = request.args.get('nit', '')
        filtrar_estado = request.args.get('estado', '')

        # Parámetros de paginación
        pagina = int(request.args.get('pagina', 1))
        per_page = 10
        offset = (pagina - 1) * per_page

        print(f"🔎 Filtros recibidos -> nombre: '{buscar_nombre}', nit: '{buscar_nit}', estado: '{filtrar_estado}', página: {pagina}")

        # Query base: ahora traemos **todos los campos necesarios** para el modal
        query = """
            SELECT 
                nit_empresa,
                nombre,
                nombre_comercial,
                correo,
                telefono,
                direccion,
                representante_legal,
                cedula_representante,
                cargo,
                actividad,
                codigo_ciiu,
                observaciones,
                certificado_representacion,
                logo,
                estado
            FROM empresas
            WHERE 1=1
        """

        params = []

        if buscar_nombre:
            query += " AND nombre LIKE %s"
            params.append(f"%{buscar_nombre}%")
        if buscar_nit:
            query += " AND nit_empresa LIKE %s"
            params.append(f"%{buscar_nit}%")
        if filtrar_estado and filtrar_estado != 'Todos los estados':
            query += " AND estado = %s"
            params.append(filtrar_estado)

        # Contar el total de empresas
        count_query = "SELECT COUNT(*) AS total FROM (" + query + ") AS sub"
        cursor.execute(count_query, params)
        total_empresas = cursor.fetchone()["total"]

        # Añadir paginación
        query += " ORDER BY nombre LIMIT %s OFFSET %s"
        params.extend([per_page, offset])

        print(f"📌 Ejecutando query: {query} | Parámetros: {params}")
        cursor.execute(query, params)
        empresas_list = cursor.fetchall()
        print(f"✅ Empresas encontradas: {len(empresas_list)}")

        # Obtener opciones para filtro
        cursor.execute("SELECT DISTINCT nombre FROM empresas ORDER BY nombre")
        empresas_opciones = cursor.fetchall()

        # Calcular total de páginas
        total_paginas = (total_empresas + per_page - 1) // per_page

        # Obtener info de usuario
        cursor.execute("""
            SELECT u.nombre_completo, r.nombre AS rol
            FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            WHERE u.id = %s
        """, (session['usuario_id'],))
        usuario = cursor.fetchone()
        print(f"👤 Usuario actual: {usuario}")

        # Debug: imprimir todas las empresas
        for e in empresas_list:
            print(f"🏢 Empresa: {e}")

    except Exception as e:
        print(f"❌ Error al consultar empresas: {e}")
        flash("Error al cargar las empresas", "error")
        empresas_list = []
        empresas_opciones = []
        total_paginas = 1
        pagina = 1

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

    return render_template( 
        "empresas.html",
        usuario_actual=usuario,
        empresas=empresas_list,
        empresas_opciones=empresas_opciones,
        buscar_nombre=buscar_nombre,
        buscar_nit=buscar_nit,
        filtrar_estado=filtrar_estado,
        pagina=pagina,
        total_paginas=total_paginas
    )


# ------------------------------
# Ruta cambiar estado de empresa
# ------------------------------
@empresas_bp.route("/cambiar_estado/<nit>/<nuevo_estado>", methods=["POST"])
@requiere_roles("Super Administrador", "Administrador")
def cambiar_estado_empresa(nit, nuevo_estado):
    print(f"🔄 Cambiando estado de empresa NIT {nit} a {nuevo_estado}")
    try:
        connection = get_db()
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE empresas SET estado = %s WHERE nit_empresa = %s",
            (nuevo_estado, nit)
        )
        connection.commit()
        cursor.close()
        connection.close()
        print("✅ Estado actualizado correctamente")
        flash("Estado actualizado correctamente", "success")
    except Exception as e:
        print(f"❌ Error al cambiar estado: {e}")
        flash("Error al cambiar estado de la empresa", "error")

    return redirect(url_for("empresas.listar_empresas"))


# ------------------------------
# Ruta: Editar empresa (acepta /editar/<nit> y /editar_empresa/<nit>)
# ------------------------------
@empresas_bp.route('/empresas/editar/<nit_empresa>', methods=['POST'])
@requiere_roles("Super Administrador", "Administrador")
def editar_empresa(nit_empresa):
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    conexion = None
    cursor = None
    try:
        conexion = get_db()
        cursor = conexion.cursor(dictionary=True)

        # 🔹 Traer rol del usuario
        cursor.execute("""
            SELECT r.nombre AS rol
            FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            WHERE u.id = %s
        """, (session['usuario_id'],))
        user_info = cursor.fetchone()
        rol = user_info['rol'] if user_info else None
        print(f"👤 Rol del usuario: {rol}")

        # 🔹 Capturar datos del formulario
        data = request.form.to_dict()
        print(f"📩 Datos recibidos: {data}")

        logo = request.files.get('logo')
        certificado = request.files.get('certificado_representacion')
        UPLOAD_FOLDER = os.path.join(current_app.root_path, 'static', 'uploads', 'empresas')
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        logo_url = None
        certificado_url = None
        if logo and logo.filename:
            logo_filename = secure_filename(f"{nit_empresa}_logo_{logo.filename}")
            logo.save(os.path.join(UPLOAD_FOLDER, logo_filename))
            logo_url = logo_filename

        if certificado and certificado.filename:
            cert_filename = secure_filename(f"{nit_empresa}_cert_{certificado.filename}")
            certificado.save(os.path.join(UPLOAD_FOLDER, cert_filename))
            certificado_url = cert_filename

        # ---------------------------
        # Campos permitidos según rol
        # ---------------------------
        campos_super = [
            'nombre', 'nombre_comercial', 'correo', 'telefono', 'direccion',
            'representante_legal', 'cedula_representante', 'cargo',
            'actividad', 'codigo_ciiu', 'observaciones'
        ]
        campos_admin = ['correo', 'telefono', 'direccion', 'observaciones']

        campos_permitidos = campos_super if rol == 'Super Administrador' else campos_admin

        # ---------------------------
        # Construir UPDATE dinámico
        # ---------------------------
        updates = []
        values = []

        for campo in campos_permitidos:
            if campo in data:
                updates.append(f"{campo} = %s")
                values.append(data.get(campo))

        # Agregar archivos solo si hay cambios
        if logo_url:
            updates.append("logo = %s")
            values.append(logo_url)
        if certificado_url:
            updates.append("certificado_representacion = %s")
            values.append(certificado_url)

        values.append(nit_empresa)
        query = f"UPDATE empresas SET {', '.join(updates)} WHERE nit_empresa = %s"
        cursor.execute(query, values)
        conexion.commit()

        print(f"✅ Empresa {nit_empresa} actualizada correctamente.")
        flash(f"Empresa {nit_empresa} actualizada correctamente.", "success")
        return jsonify({'success': True})

    except Exception as e:
        print("❌ Error al editar empresa:", e)
        # No mostrar detalles técnicos al usuario
        flash("Error al actualizar la empresa", "danger")
        return jsonify({'success': False, 'error': 'Error al actualizar la empresa'})

    finally:
        if cursor: cursor.close()
        if conexion: conexion.close()



@empresas_bp.route('/certificados/<nombre_archivo>')
@requiere_roles("Super Administrador", "Administrador")
def ver_certificado(nombre_archivo):
    carpeta = os.path.join(current_app.root_path, 'static', 'uploads', 'empresas')
    ruta = os.path.join(carpeta, nombre_archivo)

    if not os.path.exists(ruta):
        abort(404, description=f"Archivo no encontrado: {ruta}")

    return send_from_directory(carpeta, nombre_archivo)

@empresas_bp.route('/api/empresas', methods=['GET'])
def api_empresas():
    print("➡️ Entrando a /api/empresas")  # Log en consola
     
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="gestusSG"
        )
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT nit_empresa, nombre, correo, telefono, estado 
            FROM empresas 
            ORDER BY nombre
        """)
        empresas = cursor.fetchall()

        # 🔎 Mostrar datos en consola para depuración
        print(f"📊 Empresas encontradas: {len(empresas)}")
        for e in empresas:
            print(f" - {e['nit_empresa']} | {e['nombre']} | {e['estado']}")

        return jsonify({'empresas': empresas})

    except mysql.connector.Error as e:
        print(f"❌ Error en /api/empresas: {e}")
        return jsonify({'error': str(e)}), 500

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

