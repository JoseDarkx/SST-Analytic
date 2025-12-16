from flask import Blueprint, current_app, render_template, request, redirect, send_from_directory, url_for, flash, jsonify,session
from extensions import get_db
from werkzeug.utils import secure_filename
from utils.permisos import requiere_roles
import os
import mysql.connector
from datetime import datetime, date

# ======================= Blueprint =======================
planes_accion_bp = Blueprint('planes_accion', __name__, url_prefix='/planes_accion')

# ======================= Conexión a la Base de Datos =======================
def conectar_bd():
    return get_db()  # 🔄 Conexión centralizada

# ======================= Listar Planes con Paginación =======================
@planes_accion_bp.route('/')
def listar_planes():
    conexion = conectar_bd()
    cursor = conexion.cursor(dictionary=True)
    hoy = date.today().strftime('%Y-%m-%d')

    # Obtener filtro de búsqueda y paginación
    filtro = request.args.get('buscar', '').strip()
    pagina_actual = int(request.args.get('page', 1))
    limite = 10
    offset = (pagina_actual - 1) * limite

    # Base de la consulta con joins
    consulta_base = """
        FROM planes_accion pa
        LEFT JOIN personal p ON pa.responsable_id = p.id
        LEFT JOIN hallazgos h ON pa.hallazgo_id = h.id
        LEFT JOIN empresas e ON h.nit_empresa = e.nit_empresa
        WHERE 1=1
    """

    # Filter by empresa_nit for non-super administrators
    rol_usuario = session.get("rol")
    empresa_nit = session.get("nit_empresa")
    if rol_usuario != 'Super Administrador':
        consulta_base += " AND e.nit_empresa = %s"

    # Total registros
    params_total = []
    if rol_usuario != 'Super Administrador':
        params_total.append(empresa_nit)

    if filtro:
        consulta_total = f"""
            SELECT COUNT(*) AS total {consulta_base}
            AND (e.nombre LIKE %s OR e.nit_empresa LIKE %s OR p.nombre_completo LIKE %s)
        """
        params_total.extend([f"%{filtro}%", f"%{filtro}%", f"%{filtro}%"])
        cursor.execute(consulta_total, params_total)
    else:
        consulta_total = f"SELECT COUNT(*) AS total {consulta_base}"
        cursor.execute(consulta_total, params_total)

    total_registros = cursor.fetchone()["total"]
    total_paginas = (total_registros // limite) + (1 if total_registros % limite > 0 else 0)

    # Obtener datos de los planes
    params_datos = []
    if rol_usuario != 'Super Administrador':
        params_datos.append(empresa_nit)

    if filtro:
        consulta_datos = f"""
            SELECT
                e.nit_empresa,
                pa.id,
                pa.descripcion,
                pa.estado,
                pa.fecha_limite,
                p.nombre_completo AS responsable,
                h.descripcion AS hallazgo,
                e.nombre AS nombre_empresa
            {consulta_base}
            AND (e.nombre LIKE %s OR e.nit_empresa LIKE %s OR p.nombre_completo LIKE %s)
            ORDER BY pa.id DESC
            LIMIT %s OFFSET %s
        """
        params_datos.extend([f"%{filtro}%", f"%{filtro}%", f"%{filtro}%", limite, offset])
        cursor.execute(consulta_datos, params_datos)
    else:
        consulta_datos = f"""
            SELECT
                e.nit_empresa,
                pa.id,
                pa.descripcion,
                pa.estado,
                pa.fecha_limite,
                p.nombre_completo AS responsable,
                h.descripcion AS hallazgo,
                e.nombre AS nombre_empresa
            {consulta_base}
            ORDER BY pa.id DESC
            LIMIT %s OFFSET %s
        """
        params_datos.extend([limite, offset])
        cursor.execute(consulta_datos, params_datos)

    planes = cursor.fetchall()

    # Obtener todas las empresas para el select del modal (solo para Super Admin)
    if rol_usuario == 'Super Administrador':
        cursor.execute("SELECT nit_empresa, nombre FROM empresas")
        empresas = cursor.fetchall()
    else:
        empresas = []

    # Obtener todo el personal (para modal editar)
    cursor.execute("SELECT id, nombre_completo FROM personal")
    personal = cursor.fetchall()

    # Obtener información del usuario actual
    cursor.execute("""
        SELECT u.nombre_completo, r.nombre AS rol
        FROM usuarios u
        JOIN roles r ON u.rol_id = r.id
        WHERE u.id = %s
    """, (session['usuario_id'],))
    usuario_actual = cursor.fetchone()

    # Si no se encuentra el usuario, usar datos de sesión como fallback
    if not usuario_actual:
        usuario_actual = {
            'nombre_completo': session.get('usuario_nombre', 'Usuario Desconocido'),
            'rol': session.get('rol', 'Sin Rol')
        }

    cursor.close()
    conexion.close()

    # Renderizar plantilla con todos los datos
    return render_template(
        'planes_listar.html',
        planes=planes,
        filtro=filtro,
        pagina_actual=pagina_actual,
        total_paginas=total_paginas,
        empresas=empresas,
        personal=personal,
        usuario_actual=usuario_actual,
        rol=rol_usuario,
        hoy=hoy
    )

# ======================= Agregar Plan de Acción =======================
@planes_accion_bp.route('/agregar', methods=['POST'])
@requiere_roles("Super Administrador")
def agregar_plan():
    conexion = conectar_bd()
    cursor = conexion.cursor(dictionary=True)

    # Datos del formulario
    tarea = request.form['descripcion']
    responsable_id = request.form['responsable_id']
    fecha_limite = request.form['fecha_limite']
    hallazgo_descripcion = request.form['hallazgo_descripcion']
    nit_empresa = request.form['nit_empresa']  # Obtenido del select
    archivo = request.files.get('evidencia')

    evidencia_url = None
    if archivo and archivo.filename != '':
        os.makedirs("static/uploads/planes_accion", exist_ok=True)
        nombre_archivo = secure_filename(archivo.filename)
        ruta_guardado = os.path.join("static/uploads/planes_accion", nombre_archivo)
        archivo.save(ruta_guardado)
        evidencia_url = f"uploads/planes_accion/{nombre_archivo}"

    # Insertar hallazgo
    cursor.execute("""
        INSERT INTO hallazgos (descripcion, nit_empresa, fecha_deteccion)
        VALUES (%s, %s, %s)
    """, (hallazgo_descripcion, nit_empresa, datetime.now()))
    conexion.commit()
    hallazgo_id = cursor.lastrowid

    # Insertar plan de acción
    cursor.execute("""
        INSERT INTO planes_accion (hallazgo_id, descripcion, responsable_id, fecha_limite, estado, evidencia_url)
        VALUES (%s, %s, %s, %s, 'Pendiente', %s)
    """, (hallazgo_id, tarea, responsable_id, fecha_limite, evidencia_url))
    conexion.commit()

    flash("✅ Plan de acción y hallazgo registrados correctamente.", "success")
    cursor.close()
    conexion.close()
    return redirect(url_for('planes_accion.listar_planes'))

# ======================= API: Obtener Plan por ID =======================
@planes_accion_bp.route('/api/planes/<int:plan_id>')
def api_obtener_plan(plan_id):
    conexion = conectar_bd()
    cursor = conexion.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            pa.id,
            pa.descripcion,
            pa.estado,
            pa.fecha_limite,
            pa.evidencia_url,
            pa.responsable_id,
            p.nombre_completo AS responsable,
            h.descripcion AS hallazgo,
            e.nombre AS nombre_empresa,
            e.nit_empresa
        FROM planes_accion pa
        LEFT JOIN personal p ON pa.responsable_id = p.id
        LEFT JOIN hallazgos h ON pa.hallazgo_id = h.id
        LEFT JOIN empresas e ON h.nit_empresa = e.nit_empresa
        WHERE pa.id = %s
    """, (plan_id,))
    plan = cursor.fetchone()

    # Lista de personal (para editar)
    cursor.execute("SELECT id, nombre_completo FROM personal")
    personal = cursor.fetchall()

    # Lista de empresas (para editar, solo Super Admin)
    rol_usuario = session.get("rol")
    if rol_usuario == 'Super Administrador':
        cursor.execute("SELECT nit_empresa, nombre FROM empresas")
        empresas = cursor.fetchall()
    else:
        empresas = []

    cursor.close()
    conexion.close()

    if plan:
        return jsonify({"plan": plan, "personal": personal, "empresas": empresas})
    else:
        return jsonify({"error": "Plan no encontrado"}), 404

# ======================= Editar Plan de Acción =======================
@planes_accion_bp.route('/editar/<int:plan_id>', methods=['POST'])
@requiere_roles("Super Administrador")
def editar_plan(plan_id):
    conexion = conectar_bd()
    cursor = conexion.cursor(dictionary=True)
    
    try:
        data = request.form
        rol_actual = session.get('rol')
        print(f"🧠 Rol actual: {rol_actual}")
        print(f"📋 Datos recibidos: {dict(data)}")

        # Campos editables por rol
        campos_super_admin = ['descripcion', 'responsable_id', 'estado', 'fecha_limite']
        campos_admin = ['descripcion', 'responsable_id', 'estado']
        campos_permitidos = campos_super_admin if rol_actual == "Super Administrador" else campos_admin

        # Construcción dinámica del UPDATE para planes_accion
        updates = []
        values = []

        for campo in campos_permitidos:
            updates.append(f"{campo} = %s")
            values.append(data.get(campo))

        # Manejo de archivo de evidencia
        archivo = request.files.get('evidencia')
        if archivo and archivo.filename:
            upload_folder = "static/uploads/planes_accion"
            os.makedirs(upload_folder, exist_ok=True)
            filename = f"plan_{plan_id}_{secure_filename(archivo.filename)}"
            archivo_path = os.path.join(upload_folder, filename)
            archivo.save(archivo_path)
            archivo_url = f"uploads/planes_accion/{filename}"
            updates.append("evidencia_url = %s")
            values.append(archivo_url)

        # Ejecutar UPDATE si hay campos
        if updates:
            query = f"UPDATE planes_accion SET {', '.join(updates)} WHERE id = %s"
            values.append(plan_id)
            print("🔧 Ejecutando query:", query, values)
            cursor.execute(query, values)
            conexion.commit()
            print("✅ Plan de acción actualizado correctamente")

        # Actualizar hallazgo si viene hallazgo_descripcion
        hallazgo_descripcion = data.get('hallazgo_descripcion')
        if hallazgo_descripcion:
            cursor.execute("SELECT hallazgo_id FROM planes_accion WHERE id = %s", (plan_id,))
            resultado = cursor.fetchone()
            if resultado and resultado['hallazgo_id']:
                cursor.execute(
                    "UPDATE hallazgos SET descripcion = %s WHERE id = %s",
                    (hallazgo_descripcion, resultado['hallazgo_id'])
                )
                conexion.commit()
                print("✅ Hallazgo actualizado correctamente")

        flash("✅ Plan de acción actualizado correctamente.", "success")
        return redirect(url_for('planes_accion.listar_planes'))

    except Exception as e:
        conexion.rollback()
        print("❌ Error al actualizar plan de acción:", e)
        flash("Error al actualizar el plan de acción.", "error")
        return redirect(url_for('planes_accion.listar_planes'))

    finally:
        cursor.close()
        conexion.close()
        print(">>> Conexión cerrada")



# ======================= API: Obtener Responsables por Empresa =======================
@planes_accion_bp.route('/api/responsables/<nit_empresa>')
def api_responsables_empresa(nit_empresa):
    conexion = conectar_bd()
    cursor = conexion.cursor(dictionary=True)
    
    # Obtener personal que pertenece a la empresa seleccionada
    cursor.execute("""
        SELECT id, nombre_completo
        FROM personal
        WHERE nit_empresa = %s
    """, (nit_empresa,))
    
    responsables = cursor.fetchall()
    cursor.close()
    conexion.close()
    
    return jsonify(responsables)

# ======================= Descargar Evidencia =======================
@planes_accion_bp.route('/descargar/<int:plan_id>')
def descargar_evidencia(plan_id):
    conexion = conectar_bd()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT evidencia_url FROM planes_accion WHERE id = %s", (plan_id,))
    plan = cursor.fetchone()
    cursor.close()
    conexion.close()

    if not plan or not plan['evidencia_url']:
        flash("❌ No se encontró la evidencia asociada a este plan.", "danger")
        return redirect(url_for('planes_accion.listar_planes'))

    archivo_relativo = plan['evidencia_url'].replace("\\", "/")
    archivo_nombre = os.path.basename(archivo_relativo)

    carpeta_archivos = os.path.join(current_app.root_path, 'static', 'uploads', 'planes_accion')
    ruta_original = os.path.join(carpeta_archivos, archivo_nombre)

    # 🔄 Si no existe, probar reemplazando “PROYEECTOS” por “PROYECTOS”
    if not os.path.exists(ruta_original):
        ruta_corregida = ruta_original.replace("PROYEECTOS", "PROYECTOS")
    else:
        ruta_corregida = ruta_original

    if os.path.exists(ruta_corregida):
        return send_from_directory(
            os.path.dirname(ruta_corregida),
            os.path.basename(ruta_corregida),
            as_attachment=True
        )

    flash("⚠️ El archivo no se encuentra en el servidor.", "warning")
    print(f"⚠️ No se encontró archivo ni en: {ruta_original} ni en: {ruta_corregida}")
    return redirect(url_for('planes_accion.listar_planes'))

