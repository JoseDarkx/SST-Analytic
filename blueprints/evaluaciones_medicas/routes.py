import os
import re
import mysql.connector
from flask import render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename
from flask import Blueprint
from datetime import datetime, date
from utils.permisos import requiere_roles



evaluaciones_medicas_bp = Blueprint(
    'evaluaciones_medicas', __name__, url_prefix='/evaluaciones_medicas'
)


# ===============================
# LISTAR EVALUACIONES MÉDICAS
# ===============================
@evaluaciones_medicas_bp.route('/', methods=['GET'])
def evaluaciones_medicas():
    print(">>> Entrando a ruta /evaluaciones_medicas")

    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    # Parámetros de búsqueda y página actual
    filtro_participante = request.args.get('participante', '').strip()
    nombre = request.args.get('nombre', '').strip()
    nit_empresa = request.args.get('nit_empresa', '').strip()
    pagina_actual = int(request.args.get('pagina', 1))
    por_pagina = 10  # número de registros por página

    try:
        conexion = mysql.connector.connect(
            host='localhost',
            user='root',
            password='',
            database='gestusSG'
        )
        cursor = conexion.cursor(dictionary=True)

        # Obtener datos completos del usuario actual
        usuario_id_sesion = session.get('usuario_id')
        rol_usuario = session.get('rol', '')
        
        # Obtener nombre y otros datos del usuario
        if usuario_id_sesion:
            cursor.execute("""
                SELECT u.id, 
                    COALESCE(u.nombre_completo, 'Usuario') AS nombre,
                    TRIM(u.nit_empresa) AS nit_empresa,
                    r.nombre AS rol
                FROM usuarios u
                LEFT JOIN roles r ON u.rol_id = r.id
                WHERE u.id = %s
            """, (usuario_id_sesion,))
            datos_usuario = cursor.fetchone()
            if datos_usuario:
                usuario_actual = {
                    "empresa": session.get("empresa"),
                    "nombre": datos_usuario['nombre'],
                    "id": datos_usuario['id'],
                    "rol": datos_usuario['rol'] or rol_usuario
                }
            else:
                usuario_actual = {
                    "empresa": session.get("empresa"),
                    "nombre": "Usuario",
                    "id": usuario_id_sesion,
                    "rol": rol_usuario
                }
        else:
            usuario_actual = {
                "empresa": session.get("empresa"),
                "nombre": "Usuario",
                "id": None,
                "rol": rol_usuario
            }

        nit_usuario = ''
        if usuario_id_sesion:
            cursor.execute("SELECT TRIM(nit_empresa) AS nit_empresa FROM usuarios WHERE id = %s", (usuario_id_sesion,))
            row = cursor.fetchone()
            nit_usuario = row['nit_empresa'] if row and row.get('nit_empresa') else ''
        print(f"🔎 Rol en listado: {rol_usuario}, NIT usuario: '{nit_usuario}'")

        # ========= 🔹 Contar total de registros filtrados =========
        query_count = """
            SELECT COUNT(*) AS total
            FROM evaluaciones_medicas em
            JOIN personal p ON em.personal_id = p.id
            JOIN empresas e ON em.nit_empresa = e.nit_empresa
            WHERE 1=1
        """
        params = []

        if filtro_participante:
            query_count += " AND p.nombre_completo LIKE %s"
            params.append(f"%{filtro_participante}%")
        if nombre:
            query_count += " AND em.medico_examinador LIKE %s"
            params.append(f"%{nombre}%")
        # Si el usuario NO es Super Administrador, forzamos el filtro por su NIT
        if rol_usuario != 'Super Administrador':
            # si no hay NIT asociado, no devolver registros
            if nit_usuario:
                query_count += " AND em.nit_empresa = %s"
                params.append(nit_usuario)
                # sobreescribimos nit_empresa para que la interfaz refleje el filtro
                nit_empresa = nit_usuario
            else:
                # Forzamos un NIT imposible para que no devuelva nada
                query_count += " AND em.nit_empresa = %s"
                params.append('__NO_NIT__')
                nit_empresa = ''

        cursor.execute(query_count, params)
        total_registros = cursor.fetchone()['total']
        total_paginas = (total_registros + por_pagina - 1) // por_pagina

        # ========= 🔹 Obtener registros paginados =========
        offset = (pagina_actual - 1) * por_pagina

        query = """
            SELECT em.*, p.nombre_completo, p.documento_identidad, e.nombre AS empresa
            FROM evaluaciones_medicas em
            JOIN personal p ON em.personal_id = p.id
            JOIN empresas e ON em.nit_empresa = e.nit_empresa
            WHERE 1=1
        """
        if filtro_participante:
            query += " AND p.nombre_completo LIKE %s"
        if nombre:
            query += " AND em.medico_examinador LIKE %s"
        if nit_empresa:
            query += " AND em.nit_empresa = %s"

        query += " ORDER BY em.fecha DESC LIMIT %s OFFSET %s"
        params += [por_pagina, offset]

        cursor.execute(query, params)
        evaluaciones = cursor.fetchall()

        # ========= 🔹 Obtener empresas (solo las permitidas según rol) =========
        if rol_usuario == 'Super Administrador':
            cursor.execute("SELECT TRIM(nit_empresa) AS nit_empresa, nombre FROM empresas ORDER BY nombre ASC")
            empresas = cursor.fetchall()
        else:
            if nit_usuario:
                cursor.execute("SELECT TRIM(nit_empresa) AS nit_empresa, nombre FROM empresas WHERE TRIM(nit_empresa) = %s", (nit_usuario,))
                empresa_row = cursor.fetchone()
                empresas = [empresa_row] if empresa_row else []
            else:
                empresas = []

        # ========= 🔹 Obtener personal (para modal) - filtrar por empresa del usuario si no es superadmin =========
        if rol_usuario == 'Super Administrador':
            # No cargamos personal por defecto para Super Administrador: se debe usar la API
            personal = []
        else:
            if nit_usuario:
                cursor.execute("""
                    SELECT p.id, p.nombre_completo, p.documento_identidad, e.nombre AS empresa, TRIM(p.nit_empresa) AS nit_empresa
                    FROM personal p
                    JOIN empresas e ON TRIM(p.nit_empresa) = TRIM(e.nit_empresa)
                    WHERE TRIM(p.nit_empresa) = %s
                    ORDER BY p.nombre_completo
                """, (nit_usuario,))
                personal = cursor.fetchall()
            else:
                personal = []

    except mysql.connector.Error as e:
        print(f"Error al obtener las evaluaciones médicas: {e}")
        flash("Error al obtener las evaluaciones médicas", "danger")
        return redirect(url_for('evaluaciones_medicas.evaluaciones_medicas'))

    finally:
        cursor.close()
        conexion.close()

    return render_template(
        'evaluaciones_medicas.html',
        evaluaciones=evaluaciones,
        empresas=empresas,
        personal=personal,
        filtro_participante=filtro_participante,
        filtro_nombre=nombre,
        filtro_empresa=nit_empresa,
        current_date=date.today().isoformat(),
        pagina_actual=pagina_actual,
        total_paginas=total_paginas,
        usuario_actual=usuario_actual
    )
#================================
# AGREGAR EVALUACIÓN MÉDICA
# ===============================

@evaluaciones_medicas_bp.route('/agregar_evaluaciones', methods=['GET', 'POST'])
@requiere_roles("Super Administrador", "Administrador", "Administrador Empresa")
def agregar_evaluaciones():
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    usuario_id = session.get('usuario_id')
    rol = session.get('rol', '')
    print(f"🔑 Rol del usuario en sesión: {rol}")

    try:
        conexion = mysql.connector.connect(
            host='localhost',
            user='root',
            password="",
            database='gestusSG'
        )
        cursor = conexion.cursor(dictionary=True)
        print("✅ Conexión a la base de datos establecida correctamente")

        # Datos del usuario actual
        cursor.execute("""
            SELECT id, COALESCE(nombre_completo, '') AS nombre_completo,
                   correo, rol_id, TRIM(nit_empresa) AS nit_empresa
            FROM usuarios
            WHERE id = %s
        """, (usuario_id,))
        usuario_actual = cursor.fetchone()
        print(f"👤 Usuario actual: {usuario_actual}")

    except mysql.connector.Error as e:
        flash("Error al conectar a la base de datos", "danger")
        print(f"❌ Error en la conexión MySQL: {e}")
        return redirect(url_for('evaluaciones_medicas.evaluaciones_medicas')) 

    # ======================================
    # 🔹 OBTENER EMPRESAS Y PERSONAL SEGÚN ROL
    # --------------------------------------
    # Cambios:
    # - Super Administrador: cargar solo la lista de empresas. El personal se
    #   obtendrá sólo si llega un parámetro `nit_empresa` (soporte para
    #   carga dinámica desde el front mediante GET o la API que se añade más
    #   abajo). Esto evita listar todo el personal globalmente.
    # - Admin/Administrador Empresa: mantener comportamiento actual (solo su empresa y su personal).
    empresas = []
    personal = []

    if rol == "Super Administrador":
        # Obtener todas las empresas
        cursor.execute("SELECT TRIM(nit_empresa) AS nit_empresa, nombre FROM empresas ORDER BY nombre ASC")
        empresas = cursor.fetchall()

        # Soporte para pre-carga del personal cuando se pasa nit_empresa como parámetro GET
        selected_nit = request.args.get('nit_empresa', '').strip()
        if selected_nit:
            cursor.execute("""
                SELECT p.id, p.nombre_completo, p.documento_identidad, e.nombre AS empresa, TRIM(p.nit_empresa) AS nit_empresa
                FROM personal p
                JOIN empresas e ON TRIM(p.nit_empresa) = TRIM(e.nit_empresa)
                WHERE TRIM(p.nit_empresa) = %s
                ORDER BY p.nombre_completo
            """, (selected_nit,))
            personal = cursor.fetchall()
        else:
            # Por defecto no cargamos TODO el personal global
            personal = []

    elif rol in ["Administrador", "Administrador Empresa"]:
        nit_empresa_usuario = usuario_actual.get('nit_empresa', '').strip()
        print(f"🏢 NIT asociado al usuario administrador: '{nit_empresa_usuario}'")

        if nit_empresa_usuario:
            # Obtener solo la empresa asociada
            cursor.execute("""
                SELECT TRIM(nit_empresa) AS nit_empresa, nombre 
                FROM empresas 
                WHERE TRIM(nit_empresa) = %s
            """, (nit_empresa_usuario,))
            empresa_usuario = cursor.fetchone()

            if empresa_usuario:
                empresas = [empresa_usuario]
                print(f"🏢 Empresa asociada encontrada: {empresa_usuario}")

                # Filtrar solo personal de ESA empresa
                cursor.execute("""
                    SELECT p.id, p.nombre_completo, p.documento_identidad, e.nombre AS empresa, 
                        TRIM(p.nit_empresa) AS nit_empresa
                    FROM personal p
                    JOIN empresas e ON TRIM(p.nit_empresa) = TRIM(e.nit_empresa)
                    WHERE TRIM(p.nit_empresa) = %s
                    ORDER BY p.nombre_completo
                """, (nit_empresa_usuario,))
                personal = cursor.fetchall()
                print(f"📋 Personal cargado ({len(personal)} registros) para empresa: {nit_empresa_usuario}")

            else:
                flash("⚠️ No se encontró la empresa asociada a tu usuario", "warning")
                print("⚠️ No se encontró la empresa asociada al usuario")

        else:
            flash("⚠️ Tu usuario no tiene una empresa asociada", "warning")
            print("⚠️ Usuario sin NIT asociado")

    # ======================================
    # 🔹 Procesar POST
    # ======================================
    if request.method == 'POST':
        try:
            personal_id = int(request.form['personal_id'])
            nit_empresa = request.form['nit_empresa']
            fecha = request.form['fecha']
            tipo_evaluacion = request.form['tipo_evaluacion']
            medico_examinador = request.form['medico_examinador']
            restricciones = request.form.get('restricciones', '')
            observaciones = request.form.get('observaciones', '')
            recomendaciones = request.form.get('recomendaciones', '')

            print(f"📥 Datos recibidos del formulario: Personal {personal_id}, NIT {nit_empresa}, Fecha {fecha}")

            # -----------------------------
            # Validación: personal pertenece a la empresa indicada
            # -----------------------------
            nit_lim = nit_empresa.strip()
            cursor.execute("SELECT id FROM personal WHERE id = %s AND TRIM(nit_empresa) = %s", (personal_id, nit_lim))
            pertenencia = cursor.fetchone()
            if not pertenencia:
                flash('❌ El personal seleccionado no pertenece a la empresa indicada', 'danger')
                return redirect(url_for('evaluaciones_medicas.agregar_evaluaciones'))

            fecha_obj = date.fromisoformat(fecha)
            # Validación: no permitir fechas anteriores a hoy para todos los roles
            if fecha_obj < date.today():
                flash("❌ No puedes registrar una evaluación con fecha anterior a hoy", "danger")
                return redirect(url_for('evaluaciones_medicas.agregar_evaluaciones'))

            # Normalizar nombre del médico: prefijar 'Dr ' si no viene con 'Dr' o 'Dr.' (case-insensitive)
            if medico_examinador:
                me_clean = medico_examinador.strip()
                if not re.match(r'(?i)^dr\.?\s', me_clean):
                    medico_examinador = 'Dr ' + me_clean
                else:
                    medico_examinador = me_clean

            archivo = request.files.get('archivo')
            archivo_url = None
            if archivo and archivo.filename != '':
                nombre_archivo = secure_filename(archivo.filename)
                carpeta_destino = os.path.join('static', 'uploads', 'archivos_evaluaciones')
                os.makedirs(carpeta_destino, exist_ok=True)
                ruta_archivo = os.path.join(carpeta_destino, nombre_archivo)
                archivo.save(ruta_archivo)
                archivo_url = f"uploads/archivos_evaluaciones/{nombre_archivo}"

            cursor.execute("""
                INSERT INTO evaluaciones_medicas (
                    personal_id, nit_empresa, fecha, tipo_evaluacion, medico_examinador,
                    archivo_url, restricciones, observaciones, recomendaciones
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                personal_id, nit_empresa, fecha, tipo_evaluacion, medico_examinador,
                archivo_url, restricciones, observaciones, recomendaciones
            ))
            conexion.commit()
            flash('✅ Evaluación médica agregada correctamente', 'success')
            return redirect(url_for('evaluaciones_medicas.evaluaciones_medicas'))

        except Exception as e:
            print(f"❌ Error al guardar la evaluación: {str(e)}")
            flash('Error al guardar la evaluación', 'danger')
            return redirect(url_for('evaluaciones_medicas.evaluaciones_medicas'))

    # ======================================
    # 🔹 Cerrar conexión
    # ======================================
    cursor.close()
    conexion.close()
    hoy = date.today().isoformat()

    return render_template(
        'evaluaciones_medicas.html',
        personal=personal,
        empresas=empresas,
        current_date=hoy,
        rol_usuario=rol,
        usuario_actual=usuario_actual
    )

# ===============================
# VER EVALUACIÓN MÉDICA
# ===============================
# ===============================
# VER EVALUACIÓN MÉDICA
# ===============================
@evaluaciones_medicas_bp.route('/ver_evaluaciones/<int:evaluacion_id>')
def ver_evaluacion_medica(evaluacion_id):
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))
    
    conexion = None
    cursor = None
    try:
        conexion = mysql.connector.connect(
            host='localhost',
            user='root',
            password="",
            database='gestusSG'
        )
        cursor = conexion.cursor(dictionary=True)

        # Obtener evaluación médica
        cursor.execute("""
            SELECT em.*, p.nombre_completo, p.documento_identidad, e.nombre AS nombre_empresa,
                   p.id AS personal_id_obj
            FROM evaluaciones_medicas em
            JOIN personal p ON em.personal_id = p.id
            JOIN empresas e ON em.nit_empresa = e.nit_empresa
            WHERE em.id = %s
        """, (evaluacion_id,))
        
        evaluacion = cursor.fetchone()

        if not evaluacion:
            flash("Evaluación no encontrada", "warning")
            return redirect(url_for('evaluaciones_medicas.evaluaciones_medicas'))

        # Obtener capacitaciones relacionadas del mismo personal en la misma empresa
        personal_id = evaluacion.get('personal_id_obj')
        nit_empresa = evaluacion.get('nit_empresa')
        
        capacitaciones_relacionadas = []
        if personal_id and nit_empresa:
            cursor.execute("""
                SELECT c.id, c.tema, c.fecha, c.hora, c.estado, 
                       u.nombre_completo AS responsable
                FROM capacitaciones c
                LEFT JOIN usuarios u ON c.responsable_id = u.id
                WHERE c.nit_empresa = %s
                ORDER BY c.fecha DESC
                LIMIT 5
            """, (nit_empresa,))
            capacitaciones_relacionadas = cursor.fetchall()

    except mysql.connector.Error as e:
        print(f"❌ Error en la base de datos: {e}")
        flash("Error en la conexión", "danger")
        return redirect(url_for('evaluaciones_medicas.evaluaciones_medicas'))
    
    except Exception as e:
        print(f"❌ Error general: {e}")
        flash("Error general", "danger")
        return redirect(url_for('evaluaciones_medicas.evaluaciones_medicas'))
    
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

    return render_template('evaluaciones_medicas.html', evaluacion=evaluacion, 
                           capacitaciones=capacitaciones_relacionadas,
                           current_date=date.today().isoformat())





# ===============================
# EDITAR EVALUACIÓN MÉDICA
# ===============================
@evaluaciones_medicas_bp.route('/editar_evaluaciones/<int:evaluacion_id>', methods=['GET', 'POST'])
@requiere_roles("Super Administrador", "Administrador Empresa", "Administrador")
def editar_evaluaciones(evaluacion_id):
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    conexion = None
    cursor = None
    try:
        conexion = mysql.connector.connect(
            host='localhost',
            user='root',
            password="",
            database='gestusSG'
        )
        cursor = conexion.cursor(dictionary=True)

        # Obtener rol del usuario
        cursor.execute("""
            SELECT r.nombre AS rol
            FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            WHERE u.id = %s
        """, (session['usuario_id'],))
        user_info = cursor.fetchone()
        rol = user_info['rol'] if user_info else None
        print(f"👤 Rol del usuario: {rol}")

        # Obtener evaluación y datos relacionados
        cursor.execute("""
            SELECT em.*, p.nit_empresa, p.nombre_completo
            FROM evaluaciones_medicas em
            JOIN personal p ON em.personal_id = p.id
            WHERE em.id = %s
        """, (evaluacion_id,))
        evaluacion = cursor.fetchone()

        if not evaluacion:
            flash("Evaluación no encontrada", "danger")
            return redirect(url_for('evaluaciones_medicas.evaluaciones_medicas'))

        if request.method == 'POST':
            data = request.form.to_dict()
            print("📩 Datos recibidos en editar_evaluaciones:", data)

            # ---------------------------
            # Campos editables por rol
            # NOTA: Fecha, Tipo de evaluación y Médico examinador NO deben modificarse
            # desde el modal de edición. Solo se permiten cambios en las notas y
            # recomendaciones/restricciones. Esto protege la integridad del registro.
            # ---------------------------
            campos_super = [
                'restricciones', 'observaciones', 'recomendaciones'
            ]
            campos_admin_empresa = [
                'restricciones', 'observaciones', 'recomendaciones'
            ]

            campos_permitidos = campos_super if rol == "Super Administrador" else campos_admin_empresa

            updates = []
            values = []
            for campo in campos_permitidos:
                if campo in data:
                    # Convertir fecha si es el caso
                    if campo == 'fecha' and data[campo]:
                        valor = datetime.strptime(data[campo], "%Y-%m-%d").date()
                        # Validación: no permitir fechas anteriores a hoy
                        if valor < date.today():
                            flash("❌ La fecha no puede ser anterior a hoy", 'danger')
                            return redirect(url_for('evaluaciones_medicas.evaluaciones_medicas'))
                    else:
                        valor = data[campo]
                        # Normalizar medico_examinador al editar
                        if campo == 'medico_examinador' and valor:
                            me_clean = valor.strip()
                            if not re.match(r'(?i)^dr\.?\s', me_clean):
                                valor = 'Dr ' + me_clean
                            else:
                                valor = me_clean
                    updates.append(f"{campo} = %s")
                    values.append(valor)

            # Manejo de archivo: solo super admin
            archivo_url = evaluacion['archivo_url']
            if rol == "Super Administrador":
                archivo = request.files.get('archivo')
                if archivo and archivo.filename != '':
                    nombre_archivo = secure_filename(archivo.filename)
                    upload_folder = os.path.join('static/uploads/archivos_evaluaciones')
                    os.makedirs(upload_folder, exist_ok=True)
                    ruta_archivo = os.path.join(upload_folder, nombre_archivo)
                    archivo.save(ruta_archivo)
                    archivo_url = f"uploads/archivos_evaluaciones/{nombre_archivo}"
                    updates.append("archivo_url = %s")
                    values.append(archivo_url)
                    print(f"📂 Archivo guardado: {ruta_archivo}")

            # Ejecutar UPDATE
            if updates:
                query = f"UPDATE evaluaciones_medicas SET {', '.join(updates)} WHERE id = %s"
                values.append(evaluacion_id)
                print("🔧 Ejecutando query:", query, values)
                cursor.execute(query, values)
                conexion.commit()
                print("✅ Evaluación actualizada correctamente")
                flash('Evaluación actualizada correctamente', 'success')

            return redirect(url_for('evaluaciones_medicas.evaluaciones_medicas'))

    except mysql.connector.Error as e:
        print(f"❌ Error en la conexión de Base de Datos: {e}")
        flash('Error en la conexión de Base de Datos', 'danger')
        return redirect(url_for('evaluaciones_medicas.evaluaciones_medicas'))

    except Exception as e:
        print(f"❌ Error al actualizar la evaluación: {e}")
        flash('Error al actualizar la evaluación', 'danger')
        return redirect(url_for('evaluaciones_medicas.evaluaciones_medicas'))

    finally:
        if cursor: cursor.close()
        if conexion: conexion.close()

    # Evitar renderizar la plantilla principal pasando solo `evaluacion` (causa páginas vacías
    # si se accede directamente a la URL). Redirigimos al listado; el flujo normal de edición
    # ocurre vía modal en la vista de listado (POST maneja la actualización).
    return redirect(url_for('evaluaciones_medicas.evaluaciones_medicas'))



@evaluaciones_medicas_bp.route('/api/evaluaciones_medicas', methods=['GET'])
def api_evaluaciones_medicas():
    """API para listar todas las evaluaciones médicas"""
    print("➡️ Entrando a /api/evaluaciones_medicas")  

    try:
        # Conexión a la BD
        conexion = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="gestusSG"
        )
        cursor = conexion.cursor(dictionary=True)

        # Consulta con JOIN a personal y empresas
        cursor.execute("""
            SELECT em.id, em.fecha, em.tipo_evaluacion, em.medico_examinador,
                em.archivo_url, em.restricciones, em.observaciones, em.recomendaciones,
                p.nombre_completo AS persona, p.documento_identidad, p.cargo,
                e.nombre AS empresa
            FROM evaluaciones_medicas em
            JOIN personal p ON em.personal_id = p.id
            JOIN empresas e ON em.nit_empresa = e.nit_empresa
            ORDER BY em.fecha DESC
        """)

        evaluaciones = cursor.fetchall()

        # 🔎 Logs en consola
        print(f"📦 Registros encontrados: {len(evaluaciones)}")
        for ev in evaluaciones[:10]:  # Solo mostramos los 10 primeros en consola
            print(f" - ID:{ev['id']} | Persona:{ev['persona']} | Empresa:{ev['empresa']} "
                f"| Tipo:{ev['tipo_evaluacion']} | Fecha:{ev['fecha']}")

        if not evaluaciones:
            print("ℹ️ No hay evaluaciones médicas en la base de datos")
            return jsonify({'evaluaciones': [], 'mensaje': 'No hay evaluaciones registradas'}), 200

        return jsonify({'evaluaciones': evaluaciones}), 200

    except mysql.connector.Error as e:
        print(f"❌ Error en /api/evaluaciones_medicas: {e}")
        return jsonify({'error': str(e)}), 500

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conexion' in locals():
            conexion.close()


@evaluaciones_medicas_bp.route('/api/personal_por_empresa', methods=['GET'])
def api_personal_por_empresa():
    """Devuelve el personal asociado a un NIT de empresa (parámetro `nit_empresa`)."""
    nit = request.args.get('nit_empresa', '').strip()
    if not nit:
        return jsonify({'personal': []}), 200

    try:
        conexion = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="gestusSG"
        )
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("""
            SELECT p.id, p.nombre_completo, p.documento_identidad, TRIM(p.nit_empresa) AS nit_empresa, e.nombre AS empresa
            FROM personal p
            JOIN empresas e ON TRIM(p.nit_empresa) = TRIM(e.nit_empresa)
            WHERE TRIM(p.nit_empresa) = %s
            ORDER BY p.nombre_completo
        """, (nit,))
        personal = cursor.fetchall()
        return jsonify({'personal': personal}), 200

    except mysql.connector.Error as e:
        print(f"❌ Error en /api/personal_por_empresa: {e}")
        return jsonify({'error': str(e)}), 500

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conexion' in locals():
            conexion.close()

# ===============================
# ELIMINAR EVALUACIÓN MÉDICA
# ===============================
@evaluaciones_medicas_bp.route('/eliminar/<int:evaluacion_id>', methods=['POST'])
def eliminar_evaluacion(evaluacion_id):
    if 'usuario' not in session:
        return redirect(url_for('auth.iniciar_sesion'))

    try:
        conexion = mysql.connector.connect(
            host='localhost',
            user='root',
            password="",
            database='gestusSG'
        )
        cursor = conexion.cursor()

        # Verificar que la evaluación existe
        cursor.execute("SELECT id FROM evaluaciones_medicas WHERE id = %s", (evaluacion_id,))
        evaluacion = cursor.fetchone()

        if not evaluacion:
            flash("La evaluación médica no existe", "warning")
            return redirect(url_for('evaluaciones_medicas.evaluaciones_medicas'))

        # Eliminar registro
        cursor.execute("DELETE FROM evaluaciones_medicas WHERE id = %s", (evaluacion_id,))
        conexion.commit()

        flash("✅ Evaluación eliminada correctamente", "success")

    except Exception as e:
        print(f"❌ Error al eliminar la evaluación: {e}")
        flash("Error al eliminar la evaluación", "danger")

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conexion' in locals():
            conexion.close()

    return redirect(url_for('evaluaciones_medicas.evaluaciones_medicas'))

