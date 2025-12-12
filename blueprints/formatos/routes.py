from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory
from database import get_connection as get_db
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from utils.permisos import requiere_roles
import mysql.connector

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../static/uploads/formatos_globales')

# =============================
# CONFIGURACIÓN BLUEPRINT
# =============================
formatos_globales_bp = Blueprint('formatos_globales_bp', __name__)

# Carpeta de subida
UPLOAD_FOLDER = os.path.join('static', 'uploads', 'formatos_globales')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# =============================
# FUNCIÓN DE CONEXIÓN A LA BD
# =============================
def get_db_connection():
    # Usa la misma base que tu sistema (igual que incidentes)
    return get_db()  # 🔄 Conexión centralizada

# =============================
# LISTAR FORMATOS
# =============================
@formatos_globales_bp.route('/formatos_globales')
def formatos_globales():
    print("📄 Cargando lista de formatos globales...")

    # --- Parámetros de paginación ---
    from flask import request, session, render_template
    pagina = request.args.get('pagina', 1, type=int)
    por_pagina = 10  # puedes ajustar el número de registros por página

    # --- Conexión a la BD ---
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1️⃣ Obtener el total de registros
    cursor.execute("SELECT COUNT(*) AS total FROM formatos_globales")
    total_registros = cursor.fetchone()['total']
    total_paginas = (total_registros + por_pagina - 1) // por_pagina  # redondeo hacia arriba

    # 2️⃣ Obtener los registros de la página actual
    offset = (pagina - 1) * por_pagina
    cursor.execute("""
        SELECT * FROM formatos_globales
        ORDER BY fecha_creacion DESC
        LIMIT %s OFFSET %s
    """, (por_pagina, offset))
    formatos = cursor.fetchall()
    conn.close()

    print(f"✅ Página {pagina}/{total_paginas} con {len(formatos)} formatos")

    # --- Información del usuario ---
    # Obtener datos del usuario logueado desde la BD
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT u.nombre_completo, r.nombre AS rol
        FROM usuarios u
        JOIN roles r ON u.rol_id = r.id
        WHERE u.id = %s
    """, (session['usuario_id'],))
    usuario_db = cursor.fetchone()
    conn.close()

    usuario = {
        "nombre_completo": usuario_db['nombre_completo'] if usuario_db else "Usuario Desconocido",
        "rol": usuario_db['rol'] if usuario_db else "Invitado"
    }

    # --- Obtener rol para el template ---
    rol = session.get("rol", "Invitado")

    # --- Renderizado ---
    return render_template('formatos/formatos_globales.html',
                           formatos=formatos,
                           usuario=usuario,
                           rol=rol,
                           pagina_actual=pagina,
                           total_paginas=total_paginas)

# =============================
# SUBIR NUEVO FORMATO
# =============================
@formatos_globales_bp.route('/formatos_globales/agregar', methods=['POST'])
@requiere_roles("Super Administrador")
def agregar_formato():
    nombre = request.form['nombre']
    descripcion = request.form.get('descripcion')
    archivo = request.files['archivo']

    if archivo: 
        nombre_archivo = secure_filename(archivo.filename)
        ruta_guardar = os.path.join(UPLOAD_FOLDER, nombre_archivo)
        archivo.save(ruta_guardar)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO formatos_globales (nombre, descripcion, archivo_url, fecha_creacion)
            VALUES (%s, %s, %s, %s)
        """, (nombre, descripcion, nombre_archivo, datetime.now()))
        conn.commit()
        conn.close()

        flash('Formato subido correctamente ✅', 'success')
        print(f"📤 Se subió el formato '{nombre}' correctamente.")
    else:
        flash('Debe seleccionar un archivo para subir ❌', 'danger')
        print("⚠️ Intento de subida sin archivo.")

    return redirect(url_for('formatos_globales_bp.formatos_globales'))


# =============================
# DESCARGAR / VISUALIZAR FORMATO
# =============================
@formatos_globales_bp.route('/descargar_formato/<int:id>')
def descargar_formato(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT archivo_url FROM formatos_globales WHERE id = %s", (id,))
    formato = cursor.fetchone()
    conn.close()

    if formato and formato['archivo_url']:
        archivo = formato['archivo_url']
        ruta_archivo = os.path.join(UPLOAD_FOLDER, archivo)

        if os.path.exists(ruta_archivo):
            print(f"⬇️ Abriendo archivo: {archivo}")
            # as_attachment=False → lo abre en navegador si es PDF / Word soporte viewer
            return send_from_directory(UPLOAD_FOLDER, archivo, as_attachment=False)
        else:
            print(f"⚠️ Archivo no existe: {ruta_archivo}")
            flash('El archivo no existe en el servidor.', 'warning')
            return redirect(url_for('formatos_globales_bp.formatos_globales'))
    else:
        print(f"⚠️ No se encontró el registro de formato con ID {id}")
        flash('No se encontró el formato.', 'danger')
        return redirect(url_for('formatos_globales_bp.formatos_globales'))


# =============================
# EDITAR FORMATO
# =============================
@formatos_globales_bp.route('/formatos_globales/editar/<int:id>', methods=['POST'])
@requiere_roles("Super Administrador")
def editar_formato(id):
    nombre = request.form['nombre']
    descripcion = request.form.get('descripcion')
    archivo = request.files.get('archivo')

    conn = get_db_connection()
    cursor = conn.cursor()

    # Si hay un nuevo archivo, actualizarlo
    if archivo and archivo.filename:
        nombre_archivo = secure_filename(archivo.filename)
        ruta_guardar = os.path.join(UPLOAD_FOLDER, nombre_archivo)
        archivo.save(ruta_guardar)

        # Eliminar archivo anterior
        cursor.execute("SELECT archivo_url FROM formatos_globales WHERE id = %s", (id,))
        formato_antiguo = cursor.fetchone()
        if formato_antiguo and formato_antiguo[0]:
            archivo_antiguo_path = os.path.join(UPLOAD_FOLDER, formato_antiguo[0])
            if os.path.exists(archivo_antiguo_path):
                os.remove(archivo_antiguo_path)

        cursor.execute("""
            UPDATE formatos_globales
            SET nombre = %s, descripcion = %s, archivo_url = %s
            WHERE id = %s
        """, (nombre, descripcion, nombre_archivo, id))
    else:
        # Solo actualizar nombre y descripción
        cursor.execute("""
            UPDATE formatos_globales
            SET nombre = %s, descripcion = %s
            WHERE id = %s
        """, (nombre, descripcion, id))

    conn.commit()
    conn.close()

    flash('Formato actualizado correctamente ✅', 'success')
    return redirect(url_for('formatos_globales_bp.formatos_globales'))

# =============================
# ELIMINAR FORMATO
# =============================
@formatos_globales_bp.route('/formatos_globales/eliminar/<int:id>', methods=['POST'])
@requiere_roles("Super Administrador")
def eliminar_formato(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT archivo_url FROM formatos_globales WHERE id = %s", (id,))
    formato = cursor.fetchone()

    if formato:
        archivo_path = os.path.join(UPLOAD_FOLDER, formato['archivo_url'])
        if os.path.exists(archivo_path):
            os.remove(archivo_path)
            print(f"🗑️ Archivo eliminado: {archivo_path}")

        cursor.execute("DELETE FROM formatos_globales WHERE id = %s", (id,))
        conn.commit()
        flash('Formato eliminado correctamente ✅', 'success')
    else:
        flash('Formato no encontrado ❌', 'danger')

    conn.close()
    return redirect(url_for('formatos_globales_bp.formatos_globales'))

