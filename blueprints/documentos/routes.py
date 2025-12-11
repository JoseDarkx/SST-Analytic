from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from werkzeug.utils import secure_filename
import os
import mysql.connector
from datetime import datetime
from utils.permisos import requiere_roles



documentos_bp = Blueprint('documentos', __name__)



# Configuración de archivos permitidos
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'}
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ------------------------------
# Ruta: Listado de Documentos
# ------------------------------
@documentos_bp.route('/documentacion', methods=['GET', 'POST'])
def documentacion():
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    try:
        # ----------------------------
        # 🔹 FILTROS DE BÚSQUEDA
        # ----------------------------
        buscar_nombre = request.args.get('nombre', '').strip()
        buscar_nit = request.args.get('nit', '').strip()
        filtrar_estado = request.args.get('estado', '')
        filtrar_formato = request.args.get('formato', '')

        # ----------------------------
        # 🔹 PAGINACIÓN
        # ----------------------------
        pagina = int(request.args.get('pagina', 1))
        por_pagina = 10
        offset = (pagina - 1) * por_pagina

        # ----------------------------
        # 🔹 CONEXIÓN A BD
        # ----------------------------
        connection = mysql.connector.connect(
            host='localhost',
            database='gestusSG',
            user='root',
            password=""
        )
        cursor = connection.cursor(dictionary=True)

        # ----------------------------
        # 🔹 OBTENER USUARIO EN SESIÓN
        # ----------------------------
        cursor.execute("""
            SELECT u.*, r.nombre AS rol
            FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            WHERE u.id = %s
        """, (session['usuario_id'],))
        usuario_actual = cursor.fetchone()
        if not usuario_actual:
            flash("No se encontró el usuario en la base de datos", "error")
            return redirect(url_for('auth.iniciar_sesion'))

        usuario_id = usuario_actual['id']
        rol_usuario = usuario_actual['rol']
        empresa_nit = usuario_actual['nit_empresa']
        print(f"👤 Usuario en sesión -> ID: {usuario_id}, Rol: {rol_usuario}, Empresa NIT: {empresa_nit}")

        # ----------------------------
        # 🔹 CARGAR EMPRESAS Y FORMATOS
        # ----------------------------
        if rol_usuario == 'Super Administrador':
            cursor.execute("SELECT nit_empresa, nombre FROM empresas WHERE estado='Activa' ORDER BY nombre")
            empresas = cursor.fetchall()
        else:
            cursor.execute("SELECT nit_empresa, nombre FROM empresas WHERE estado='Activa' AND nit_empresa = %s ORDER BY nombre", (empresa_nit,))
            empresas = cursor.fetchall()

        cursor.execute("SELECT id, nombre FROM formatos_globales ORDER BY nombre")
        formatos_globales = cursor.fetchall()

        # ----------------------------
        # 🔹 CONSULTA BASE
        # ----------------------------
        query_base = """
            FROM documentos_empresa d
            JOIN empresas e ON d.nit_empresa = e.nit_empresa
            WHERE 1=1
        """
        params = []

        # Filter by empresa_nit for non-super administrators
        if rol_usuario != 'Super Administrador':
            query_base += " AND d.nit_empresa = %s"
            params.append(empresa_nit)

        if buscar_nombre:
            query_base += " AND d.nombre LIKE %s"
            params.append(f"%{buscar_nombre}%")
        if buscar_nit:
            query_base += " AND d.nit_empresa LIKE %s"
            params.append(f"%{buscar_nit}%")
        if filtrar_estado:
            query_base += " AND d.estado = %s"
            params.append(filtrar_estado)
        if filtrar_formato:
            query_base += " AND d.formato = %s"
            params.append(filtrar_formato)

        # ----------------------------
        # 🔹 TOTAL DE DOCUMENTOS
        # ----------------------------
        cursor.execute(f"SELECT COUNT(*) AS total {query_base}", params)
        total_registros = cursor.fetchone()['total']
        total_paginas = (total_registros + por_pagina - 1) // por_pagina

        # ----------------------------
        # 🔹 CONSULTA FINAL CON LIMIT Y OFFSET
        # ----------------------------
        query_final = f"""
            SELECT d.*, e.nombre as nombre_empresa,
            DATE_FORMAT(d.fecha_vencimiento, '%%d/%%m/%%Y') as fecha_vencimiento_formateada
            {query_base}
            ORDER BY d.fecha_vencimiento DESC, d.id DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(query_final, params + [por_pagina, offset])
        documentos = cursor.fetchall()
        print(f"📄 Documentos obtenidos: {len(documentos)} de {total_registros}")

        # ----------------------------
        # 🔹 VALIDACIÓN DE FECHAS
        # ----------------------------
        hoy = datetime.now().date()
        for doc in documentos:
            if doc['fecha_vencimiento']:
                fecha_v = doc['fecha_vencimiento']
                if isinstance(fecha_v, datetime):
                    fecha_v = fecha_v.date()
                dias_restantes = (fecha_v - hoy).days
                doc['vencido'] = dias_restantes < 0
                doc['proximo_vencer'] = 0 <= dias_restantes <= 30
                doc['dias_restantes'] = dias_restantes

        # 🔹 Validar fecha desde formulario (solo POST)
        if request.method == 'POST':
            fecha_vencimiento = request.form.get('fecha_vencimiento')
            print("Fecha enviada desde formulario:", fecha_vencimiento)
            if fecha_vencimiento:
                fecha_vencimiento_date = datetime.strptime(fecha_vencimiento, '%Y-%m-%d').date()
                if rol_usuario not in ['Super Administrador', 'Admin', 'Administrador'] and fecha_vencimiento_date < hoy:
                    flash("No puedes colocar fechas pasadas", "error")
                    print("Intento de fecha pasada bloqueado para usuario:", rol_usuario)
                    return redirect(url_for('documentos.documentacion'))

        # ----------------------------
        # 🔹 PASAR DATOS AL TEMPLATE
        # ----------------------------
        return render_template(
            'documentacion.html',
            documentos=documentos,
            usuario_actual=usuario_actual,
            rol_usuario=rol_usuario,
            buscar_nombre=buscar_nombre,
            buscar_nit=buscar_nit,
            filtrar_estado=filtrar_estado,
            filtrar_formato=filtrar_formato,
            empresas=empresas,
            formatos_globales=formatos_globales,
            total_paginas=total_paginas,
            pagina_actual=pagina,
            datetime=datetime
        )

    except mysql.connector.Error as e:
        print(f"Error en documentacion: {e}")
        flash('Error al cargar la documentación', 'error')
        return render_template('documentacion.html', documentos=[], usuario_actual=None, rol='Usuario', pagina_actual=1, total_paginas=1, datetime=datetime)
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()


# Ruta: Guardar documento
# ------------------------------
@documentos_bp.route('/guardar_documento', methods=['POST', 'GET'])
@requiere_roles("Super Administrador")
def guardar_documento():
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))
    
    try:
        nit_empresa = request.form.get('nit_empresa', '').strip()
        nombre = request.form.get('nombre', '').strip()
        if not nit_empresa or not nombre:
            flash('Empresa y nombre del documento son obligatorios', 'error')
            return redirect(url_for('documentos.guardar_documento'))

        # Validar que el NIT de la empresa coincida con el del usuario si no es Super Administrador
        usuario_id = session.get("usuario_id")
        rol_usuario = session.get("rol")
        empresa_nit_sesion = session.get("empresa_nit")
        if rol_usuario != 'Super Administrador' and nit_empresa != empresa_nit_sesion:
            flash('No tienes permisos para agregar documentos a esta empresa', 'error')
            return redirect(url_for('documentos.documentacion'))

        archivo = request.files.get('archivo')
        archivo_url = None

        if archivo and archivo.filename:
            if not allowed_file(archivo.filename):
                flash('Tipo de archivo no permitido', 'error')
                return redirect(url_for('documentos.guardar_documento'))

            filename = secure_filename(archivo.filename)
            unique_name = f"{nit_empresa}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
            archivo_url = os.path.join(UPLOAD_FOLDER, unique_name)
            archivo.save(archivo_url)
            

        connection = mysql.connector.connect(
            host='localhost',
            database='gestusSG',
            user='root',
            password=""
        )
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO documentos_empresa (
                nit_empresa, formato_id, nombre,
                archivo_url, fecha_vencimiento,
                estado, formato
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            nit_empresa,
            request.form.get('formato_id') or None,
            nombre,
            archivo_url,
            request.form.get('fecha_vencimiento') or None,
            request.form.get('estado', 'Sin Diligenciar'),
            request.form.get('formato_archivo', 'PDF')
        ))

        connection.commit()
        flash('✅ Documento guardado exitosamente', 'success')
        return redirect(url_for('documentos.documentacion'))

    except Exception as e:
        print(f"Error en guardar_documento: {e}")
        flash('Error interno al guardar el documento', 'error')
        return redirect(url_for('documentos.guardar_documento'))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()
# ------------------------------
# RUTA: Editar Documento
# ------------------------------
@documentos_bp.route('/editar/<int:documento_id>', methods=["GET", "POST"])
@requiere_roles("Super Administrador", "Administrador")
def editar_documento(documento_id):
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    print("📌 Entrando a editar_documento con ID:", documento_id)

    conexion = None
    cursor = None
    try:
        conexion = mysql.connector.connect(
            host='localhost',
            database='gestusSG',
            user='root',
            password=""
        )
        cursor = conexion.cursor(dictionary=True)

        # 🔹 Traer rol del usuario
        cursor.execute("""
            SELECT r.nombre AS rol, u.nit_empresa
            FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            WHERE u.id = %s
        """, (session['usuario_id'],))
        user_info = cursor.fetchone()
        rol = user_info['rol'] if user_info else None
        empresa_nit = user_info['nit_empresa'] if user_info else None
        print(f"👤 Rol del usuario: {rol}, Empresa NIT: {empresa_nit}")

        # 🔹 Cargar documento
        cursor.execute("""
            SELECT d.*, e.nombre as nombre_empresa, f.nombre as formato_global_nombre
            FROM documentos_empresa d
            JOIN empresas e ON d.nit_empresa = e.nit_empresa
            LEFT JOIN formatos_globales f ON d.formato_id = f.id
            WHERE d.id = %s
        """, (documento_id,))
        documento = cursor.fetchone()

        if not documento:
            flash('Documento no encontrado', 'error')
            return redirect(url_for('documentos.documentacion'))

        # 🔹 Validar que el documento pertenezca a la empresa del usuario si no es Super Administrador
        if rol != 'Super Administrador' and documento['nit_empresa'] != empresa_nit:
            flash('No tienes permisos para editar este documento', 'error')
            return redirect(url_for('documentos.documentacion'))

        # 🔹 Listas de empresas y formatos para selects
        if rol == 'Super Administrador':
            cursor.execute("SELECT nit_empresa, nombre FROM empresas WHERE estado = 'Activa' ORDER BY nombre")
            empresas = cursor.fetchall()
        else:
            cursor.execute("SELECT nit_empresa, nombre FROM empresas WHERE estado = 'Activa' AND nit_empresa = %s ORDER BY nombre", (empresa_nit,))
            empresas = cursor.fetchall()

        cursor.execute("SELECT id, nombre FROM formatos_globales ORDER BY nombre")
        formatos_globales = cursor.fetchall()

        # 🔹 Calcular días restantes
        fecha_actual = datetime.now().date()
        dias_restantes = None
        if documento.get("fecha_vencimiento"):
            fecha_vencimiento = documento["fecha_vencimiento"]
            if isinstance(fecha_vencimiento, datetime):
                fecha_vencimiento = fecha_vencimiento.date()
            dias_restantes = (fecha_vencimiento - fecha_actual).days

        if request.method == "POST":
            print("📥 Datos recibidos en POST:", request.form)

            data = request.form.to_dict()
            archivo = request.files.get("archivo")
            archivo_url = documento.get("archivo_url")

            # ---------------------------
            # Solo permitir subir archivo para administradores
            # ---------------------------
            updates = []
            values = []

            # Solo el archivo puede ser actualizado
            archivo = request.files.get("archivo")
            if archivo and archivo.filename:
                nombre_archivo = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(archivo.filename)}"
                ruta_archivo = os.path.join("static/uploads/documentos", nombre_archivo)
                os.makedirs(os.path.dirname(ruta_archivo), exist_ok=True)
                archivo.save(ruta_archivo)
                archivo_url = ruta_archivo
                updates.append("archivo_url = %s")
                values.append(archivo_url)
                updates.append("estado = %s")
                values.append("Diligenciado")
                print("📂 Archivo guardado en:", archivo_url)
                print("📝 Estado cambiado a Diligenciado")

            # Actualizar solo si hay cambios
            if updates:
                values.append(documento_id)
                query = f"UPDATE documentos_empresa SET {', '.join(updates)} WHERE id = %s"
                cursor.execute(query, values)
                conexion.commit()
                print("✅ Documento actualizado en BD")

                flash("✅ Documento actualizado correctamente", "success")
            else:
                flash('No se realizó ningún cambio', 'info')

            return redirect(url_for('documentos.documentacion'))

        # Obtener usuario actual para el template
        cursor.execute("""
            SELECT u.*, r.nombre AS rol
            FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            WHERE u.id = %s
        """, (session['usuario_id'],))
        usuario_actual = cursor.fetchone()

        return render_template(
            'documentacion.html',
            documento=documento,
            empresas=empresas,
            formatos_globales=formatos_globales,
            fecha_actual=fecha_actual,
            dias_restantes=dias_restantes,
            rol=rol,
            usuario_actual=usuario_actual,
            modo='edicion'
        )

    except mysql.connector.Error as e:
        print(f"❌ Error en editar_documento: {e}")
        flash('Error al cargar documento', 'error')
        return redirect(url_for('documentos.documentacion'))

    finally:
        if cursor: cursor.close()
        if conexion and conexion.is_connected(): conexion.close()



# ------------------------------
# RUTA: Actualizar Documento
# ------------------------------
@documentos_bp.route('/actualizar_documento/<int:documento_id>', methods=['POST'])
@requiere_roles("Super Administrador", "Administrador")
def actualizar_documento(documento_id):
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    try:
        nit_empresa = request.form.get('nit_empresa', '').strip()
        nombre = request.form.get('nombre', '').strip()
        if not nit_empresa or not nombre:
            flash('Empresa y nombre del documento son obligatorios', 'error')
            return redirect(url_for('documentos.documentacion', documento_id=documento_id))

        # Validar que el NIT de la empresa coincida con el del usuario si no es Super Administrador
        usuario_id = session.get("usuario_id")
        rol_usuario = session.get("rol")
        empresa_nit_sesion = session.get("empresa_nit")
        if rol_usuario != 'Super Administrador' and nit_empresa != empresa_nit_sesion:
            flash('No tienes permisos para editar documentos de esta empresa', 'error')
            return redirect(url_for('documentos.documentacion'))

        connection = mysql.connector.connect(
            host='localhost',
            database='gestusSG',
            user='root',
            password=""
        )
        cursor = connection.cursor(dictionary=True)

        archivo = request.files.get('archivo')
        archivo_url = None

        if archivo and archivo.filename:
            if not allowed_file(archivo.filename):
                flash('Tipo de archivo no permitido', 'error')
                return redirect(url_for('documentos.documentacion', documento_id=documento_id))

            filename = secure_filename(archivo.filename)
            unique_name = f"{nit_empresa}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
            archivo_url = os.path.join(UPLOAD_FOLDER, unique_name)
            archivo.save(archivo_url)

            cursor.execute("SELECT archivo_url FROM documentos_empresa WHERE id = %s", (documento_id,))
            archivo_anterior = cursor.fetchone()['archivo_url']
        else:
            archivo_anterior = None

        if archivo_url:
            query = """
                UPDATE documentos_empresa 
                SET nit_empresa = %s, formato_id = %s, nombre = %s,
                    archivo_url = %s, fecha_vencimiento = %s,
                    estado = %s, formato = %s
                WHERE id = %s
            """
            params = (
                nit_empresa,
                request.form.get('formato_id') or None,
                nombre,
                archivo_url,
                request.form.get('fecha_vencimiento') or None,
                request.form.get('estado', 'Sin Diligenciar'),
                request.form.get('formato_archivo', 'PDF'),
                documento_id
            )
        else:
            query = """
                UPDATE documentos_empresa 
                SET nit_empresa = %s, formato_id = %s, nombre = %s,
                    fecha_vencimiento = %s, estado = %s, formato = %s
                WHERE id = %s
            """
            params = (
                nit_empresa,
                request.form.get('formato_id') or None,
                nombre,
                request.form.get('fecha_vencimiento') or None,
                request.form.get('estado', 'Sin Diligenciar'),
                request.form.get('formato_archivo', 'PDF'),
                documento_id
            )

        cursor.execute(query, params)
        connection.commit()

        if archivo_url and archivo_anterior and os.path.exists(archivo_anterior):
            try:
                os.remove(archivo_anterior)
            except Exception as e:
                print(f"Error al eliminar archivo anterior: {e}")

        flash('✅ Documento actualizado exitosamente', 'success')
        return redirect(url_for('documentos.documentacion'))

    except mysql.connector.Error as e:
        print(f"Error en actualizar_documento: {e}")
        flash('Error al actualizar documento', 'error')
        return redirect(url_for('documentos.documentacion', documento_id=documento_id))
    finally:
        if 'cursor' in locals():
            cursor.close()

# ------------------------------
# RUTA: Eliminar Documento
# ------------------------------
@documentos_bp.route('/eliminar/<int:documento_id>', methods=['POST'])
@requiere_roles("Super Administrador")
def eliminar_documento(documento_id):
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    try:
        connection = mysql.connector.connect(
            host='localhost',
            database='gestusSG',
            user='root',
            password=""
        )
        cursor = connection.cursor(dictionary=True)

        cursor.execute("SELECT archivo_url, nit_empresa FROM documentos_empresa WHERE id = %s", (documento_id,))
        documento = cursor.fetchone()

        if not documento:
            return jsonify({'success': False, 'message': 'Documento no encontrado'}), 404

        # Validar que el documento pertenezca a la empresa del usuario si no es Super Administrador
        usuario_id = session.get("usuario_id")
        rol_usuario = session.get("rol")
        empresa_nit_sesion = session.get("empresa_nit")
        if rol_usuario != 'Super Administrador' and documento['nit_empresa'] != empresa_nit_sesion:
            return jsonify({'success': False, 'message': 'No tienes permisos para eliminar este documento'}), 403

        cursor.execute("DELETE FROM documentos_empresa WHERE id = %s", (documento_id,))
        connection.commit()

        if documento['archivo_url']:
            archivo_path = os.path.abspath(documento['archivo_url'])
            if os.path.exists(archivo_path):
                os.remove(archivo_path)

        return jsonify({'success': True, 'message': 'Documento eliminado correctamente'})

    except Exception as e:
        print(f"Error en eliminar_documento: {e}")
        return jsonify({'success': False, 'message': 'Error en el servidor'}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'connection' in locals(): connection.close()

# ------------------------------
# RUTA: Descargar Documento
# ------------------------------
@documentos_bp.route('/descargar/<int:documento_id>')
def descargar_documento(documento_id):
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    try:
        connection = mysql.connector.connect(
            host='localhost',
            database='gestusSG',
            user='root',
            password=""
        )
        cursor = connection.cursor(dictionary=True)

        cursor.execute("SELECT archivo_url, nombre, nit_empresa FROM documentos_empresa WHERE id = %s", (documento_id,))
        documento = cursor.fetchone()

        if not documento or not documento['archivo_url']:
            flash('Archivo no encontrado', 'error')
            return redirect(url_for('documentos.documentacion'))

        # Validar que el documento pertenezca a la empresa del usuario si no es Super Administrador
        usuario_id = session.get("usuario_id")
        rol_usuario = session.get("rol")
        empresa_nit_sesion = session.get("empresa_nit")
        if rol_usuario != 'Super Administrador' and documento['nit_empresa'] != empresa_nit_sesion:
            flash('No tienes permisos para descargar este documento', 'error')
            return redirect(url_for('documentos.documentacion'))

        if not os.path.exists(documento['archivo_url']):
            flash('El archivo físico no existe', 'error')
            return redirect(url_for('documentos.documentacion'))

        return send_file(
            documento['archivo_url'],
            as_attachment=True,
            download_name=f"{documento['nombre']}.{documento['archivo_url'].split('.')[-1]}"
        )

    except mysql.connector.Error as e:
        print(f"Error en my.sql al descargar_documento: {e}")
        flash('Error en My SQL al descargar documento', 'error')
        return redirect(url_for('documentos.documentacion'))
    except Exception as e:
        print(f"Error inesperado en descargar_documento: {e}")
        flash('Error interno del servidor', 'error')
        return redirect(url_for('documentos.documentacion'))
    finally:
        if 'cursor' in locals():
            cursor.close()

@documentos_bp.route('/api/documentos', methods=['GET'])
def api_documentos():
    """API para listar documentos de empresa con logs en consola"""
    print("➡️ Entrando a /api/documentos")  

    try:
        # Conexión a la base de datos
        connection = mysql.connector.connect(
            host='localhost',
            database='gestusSG',
            user='root',
            password=""
        )
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT d.id, d.nit_empresa, e.nombre AS empresa, 
                d.formato_id, f.nombre AS formato_nombre,
                d.nombre, d.archivo_url, d.fecha_vencimiento, 
                d.estado, d.formato
            FROM documentos_empresa d
            LEFT JOIN empresas e ON d.nit_empresa = e.nit_empresa
            LEFT JOIN formatos_globales f ON d.formato_id = f.id
            ORDER BY d.fecha_vencimiento ASC
        """)
        
        documentos = cursor.fetchall()

        print(f"📑 Documentos encontrados: {len(documentos)}")
        for doc in documentos[:10]:  # mostramos máximo 10 para no saturar
            print(f" - ID:{doc['id']} | Empresa:{doc['empresa']} | "
                f"Nombre:{doc['nombre']} | Estado:{doc['estado']}")

        if not documentos:
            print("ℹ️ No hay documentos registrados en la base de datos")
            return jsonify({'documentos': [], 'mensaje': 'No hay documentos registrados'}), 200

        return jsonify({'documentos': documentos}), 200

    except mysql.connector.Error as e:
        print(f"❌ Error en /api/documentos: {e}")
        return jsonify({'error': str(e)}), 500

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()
