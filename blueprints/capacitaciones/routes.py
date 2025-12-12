from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from database import get_connection as get_db
import mysql.connector
from io import BytesIO
from datetime import timedelta
from utils.permisos import requiere_roles

def format_timedelta(td):
    """Convierte un objeto timedelta en string HH:MM."""
    if isinstance(td, timedelta):
        total_seconds = int(td.total_seconds())
        horas, resto = divmod(total_seconds, 3600)
        minutos, _ = divmod(resto, 60)
        return f"{horas:02}:{minutos:02}"
    return td

capacitaciones_bp = Blueprint('capacitaciones', __name__)

@capacitaciones_bp.route('/')
def capacitaciones():
    """Mostrar listado de capacitaciones con paginación, filtro y permisos por rol"""

    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    try:
        connection = get_db()  # 🔄 Conexión centralizada
        cursor = connection.cursor(dictionary=True, buffered=True)

        # 🔹 Obtener información del usuario actual y su empresa
        cursor.execute("""
            SELECT u.id, u.nombre_completo, r.nombre AS rol, u.nit_empresa
            FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            WHERE u.id = %s
        """, (session['usuario_id'],))
        usuario_actual = cursor.fetchone()

        if not usuario_actual:
            flash("Usuario no encontrado", "danger")
            return redirect(url_for('auth.iniciar_sesion'))

        # -------------------------------
        # Paginación y filtro
        # -------------------------------
        pagina_actual = int(request.args.get('pagina', 1))
        por_pagina = 10
        offset = (pagina_actual - 1) * por_pagina
        estado = request.args.get('estado')

        params = []
        where_clauses = []

        # 🔹 Filtro por estado
        if estado:
            where_clauses.append("c.estado = %s")
            params.append(estado)

        # 🔹 Restricción por rol
        if usuario_actual["rol"] != "Super Administrador":
            where_clauses.append("c.nit_empresa = %s")
            params.append(usuario_actual["nit_empresa"])

        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # -------------------------------
        # Contar total de registros
        # -------------------------------
        count_query = f"""
            SELECT COUNT(*) AS total
            FROM capacitaciones c
            JOIN empresas e ON c.nit_empresa = e.nit_empresa
            LEFT JOIN usuarios u ON c.responsable_id = u.id
            {where_sql}
        """
        cursor.execute(count_query, params)
        total_registros = cursor.fetchone()['total']
        total_paginas = (total_registros + por_pagina - 1) // por_pagina

        

        # -------------------------------
        # Obtener registros paginados
        # -------------------------------
        query = f"""
            SELECT 
                c.id,
                c.nit_empresa,
                c.tema,
                e.nombre AS nombre_empresa,
                c.fecha,
                c.hora,
                TIME_FORMAT(c.hora, '%H:%i') AS hora_formateada,
                u.id AS responsable_id,
                u.nombre_completo AS responsable,
                c.estado,
                c.fecha_creacion
            FROM capacitaciones c
            JOIN empresas e ON c.nit_empresa = e.nit_empresa
            LEFT JOIN usuarios u ON c.responsable_id = u.id
            {where_sql}
            ORDER BY c.fecha DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, params + [por_pagina, offset])
        capacitaciones_list = cursor.fetchall()

        # Normalizar hora_formateada
        from datetime import datetime, time
        for cap in capacitaciones_list:
            hf = cap.get('hora_formateada')
            raw_hora = cap.get('hora')
            if not hf or (isinstance(hf, str) and '%' in hf):
                try:
                    if isinstance(raw_hora, (datetime, time)):
                        cap['hora_formateada'] = raw_hora.strftime('%H:%M')
                    elif isinstance(raw_hora, str) and raw_hora:
                        cap['hora_formateada'] = raw_hora[:5]
                    else:
                        cap['hora_formateada'] = ''
                except Exception:
                    cap['hora_formateada'] = ''

        # -------------------------------
        # Empresas activas
        # -------------------------------
        cursor.execute("""
            SELECT nit_empresa, nombre 
            FROM empresas 
            WHERE estado = 'Activa' 
            ORDER BY nombre
        """)
        empresas = cursor.fetchall()

        # -------------------------------
        # Evaluaciones
        # -------------------------------
        cursor.execute("SELECT * FROM evaluaciones_capacitacion ORDER BY participante")
        evaluaciones = cursor.fetchall()

        # -------------------------------
        # Usuarios activos (para selects)
        # -------------------------------
        cursor.execute("""
            SELECT id, nombre_completo
            FROM usuarios
            WHERE estado = 'Activo'
            ORDER BY nombre_completo
        """)
        usuarios = cursor.fetchall()

                # -------------------------------
        # Personal activo (para los selects)
        # -------------------------------
        if usuario_actual["rol"] == "Super Administrador":
            cursor.execute("""
                SELECT id, nombre_completo, nit_empresa
                FROM personal
                WHERE estado = 'Activo'
                ORDER BY nombre_completo
            """)
        else:
            cursor.execute("""
                SELECT id, nombre_completo, nit_empresa
                FROM personal
                WHERE estado = 'Activo' AND nit_empresa = %s
                ORDER BY nombre_completo
            """, (usuario_actual["nit_empresa"],))
        personal = cursor.fetchall()

                # 🔹 Para cada capacitación, obtener personal por empresa y asignado
        for cap in capacitaciones_list:
            # Personal activo de la empresa correspondiente
            cursor.execute("""
                SELECT id, nombre_completo 
                FROM personal 
                WHERE nit_empresa = %s AND estado = 'Activo'
                ORDER BY nombre_completo
            """, (cap['nit_empresa'],))
            cap['personal'] = cursor.fetchall()

            # Personal asignado a esa capacitación
            cursor.execute("""
                SELECT personal_id 
                FROM capacitaciones_participantes 
                WHERE capacitacion_id = %s
            """, (cap['id'],))
            cap['personal_asignado'] = [str(p['personal_id']) for p in cursor.fetchall()]


        # 🔹 Renderizar template
        return render_template(
            'capacitaciones.html',
            usuario_actual=usuario_actual,
            capacitaciones=capacitaciones_list,
            empresas=empresas,
            evaluaciones=evaluaciones,
            usuarios=usuarios,
            personal=personal,  # 👈 AQUI SE AGREGA
            estado_filtro=estado,
            pagina_actual=pagina_actual,
            total_paginas=total_paginas
        )

    except mysql.connector.Error as e:
        print(f">>> ERROR en capacitaciones: {e}")
        flash('Error al cargar las capacitaciones', 'error')
        return render_template(
            'capacitaciones.html',
            usuario_actual=None,
            capacitaciones=[], empresas=[], evaluaciones=[], usuarios=[]
        )

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

# ===============================
# VER CAPACITACIÓN INDIVIDUAL
# ===============================
@capacitaciones_bp.route('/ver_capacitacion/<int:capacitacion_id>')
def ver_capacitacion(capacitacion_id):
    """Ver detalles de una capacitación, su responsable, personal asignado y evaluaciones"""
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    try:
        connection = get_db()  # 🔄 Conexión centralizada
        cursor = connection.cursor(dictionary=True)

        # 🔹 Obtener información general de la capacitación
        cursor.execute("""
            SELECT 
                c.id,
                c.tema,
                c.fecha,
                TIME_FORMAT(c.hora, '%H:%i') AS hora_formateada,
                c.hora,
                c.estado,
                e.nombre AS nombre_empresa,
                e.nit_empresa,
                u.nombre_completo AS responsable
            FROM capacitaciones c
            JOIN empresas e ON c.nit_empresa = e.nit_empresa
            LEFT JOIN usuarios u ON c.responsable_id = u.id
            WHERE c.id = %s
        """, (capacitacion_id,))
        capacitacion = cursor.fetchone()
        print(f">>> Capacitación obtenida: {capacitacion}")

        if not capacitacion:
            flash("Capacitación no encontrada", "warning")
            return redirect(url_for('capacitaciones.capacitaciones'))

        # 🔹 Normalizar hora_formateada
        try:
            hf = capacitacion.get('hora_formateada')
            raw_hora = capacitacion.get('hora')
            if not hf or (isinstance(hf, str) and '%' in hf):
                if hasattr(raw_hora, 'strftime'):
                    capacitacion['hora_formateada'] = raw_hora.strftime('%H:%M')
                elif isinstance(raw_hora, str) and raw_hora:
                    capacitacion['hora_formateada'] = raw_hora[:5]
                else:
                    capacitacion['hora_formateada'] = ''
        except Exception:
            capacitacion['hora_formateada'] = ''

        # 🔹 Obtener personal asignado
        cursor.execute("""
            SELECT p.id, p.nombre_completo
            FROM capacitaciones_participantes cp
            JOIN personal p ON cp.personal_id = p.id
            WHERE cp.capacitacion_id = %s
            ORDER BY p.nombre_completo
        """, (capacitacion_id,))
        personal_asignado = cursor.fetchall()
        print(f">>> Personal asignado: {personal_asignado}")

        # 🔹 Evaluaciones
        cursor.execute("""
            SELECT ec.id, ec.participante, ec.pre_test, ec.post_test, 
                   ec.resultado, ec.fecha_evaluacion, ec.observaciones
            FROM evaluaciones_capacitacion ec
            WHERE ec.capacitacion_id = %s
            ORDER BY ec.fecha_evaluacion DESC
        """, (capacitacion_id,))
        evaluaciones = cursor.fetchall()
        print(f">>> Evaluaciones: {evaluaciones}")

        # 🔹 Datos del usuario actual
        cursor.execute("""
            SELECT u.id, u.nombre_completo, r.nombre AS rol
            FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            WHERE u.id = %s
        """, (session['usuario_id'],))
        usuario_actual = cursor.fetchone()
        print(f">>> Usuario actual: {usuario_actual}")

    except mysql.connector.Error as e:
        print(f">>> ERROR en ver_capacitacion: {e}")
        flash('Error al cargar la capacitación', 'error')
        return redirect(url_for('capacitaciones.capacitaciones'))

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()


# ============================================================
# API: Obtener personal según empresa (para formulario)
# ============================================================
@capacitaciones_bp.route('/api/personal/<nit_empresa>')
def api_personal_empresa(nit_empresa):
    try:
        conexion = get_db()  # 🔄 Conexión centralizada
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, nombre_completo
            FROM personal
            WHERE nit_empresa = %s
        """, (nit_empresa,))
        personal = cursor.fetchall()
        cursor.close()
        conexion.close()
        return jsonify(personal)
    except Exception as e:
        print(f"❌ Error al obtener personal: {e}")
        return jsonify([]), 500


@capacitaciones_bp.route('/crear_capacitacion', methods=['POST'])
def crear_capacitacion():
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    try:
        # Datos del formulario
        nit_empresa = request.form.get('empresa')
        tema = request.form.get('tema')
        fecha = request.form.get('fecha')
        hora = request.form.get('hora')
        responsable_id = request.form.get('responsable_id')
        estado = request.form.get('estado')
        personal_ids = request.form.getlist('personal_asignado')  # <--- lista de IDs del personal

        if not all([nit_empresa, tema, fecha, hora, responsable_id, estado]):
            flash('Todos los campos son obligatorios', 'error')
            return redirect(url_for('capacitaciones.capacitaciones'))

        responsable_id = int(responsable_id)

        connection = get_db()  # 🔄 Conexión centralizada
        cursor = connection.cursor()

        # Crear la capacitación
        cursor.execute("""
            INSERT INTO capacitaciones (nit_empresa, tema, fecha, hora, responsable_id, estado, fecha_creacion)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """, (nit_empresa, tema, fecha, hora, responsable_id, estado))
        connection.commit()

        # Obtener el ID de la capacitación recién creada
        capacitacion_id = cursor.lastrowid

        # Insertar los participantes seleccionados
        if personal_ids:
            for pid in personal_ids:
                cursor.execute("""
                    INSERT INTO capacitaciones_participantes (capacitacion_id, personal_id)
                    VALUES (%s, %s)
                """, (capacitacion_id, pid))
            connection.commit()

        flash('Capacitación y asignaciones creadas exitosamente', 'success')

    except mysql.connector.Error as e:
        print(f">>> ERROR SQL: {e}")
        flash('Error al crear la capacitación', 'error')

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

    return redirect(url_for('capacitaciones.capacitaciones'))



# ------------------------------------------------------
# RUTA: Obtener responsables por empresa (AJAX)
# ------------------------------------------------------
@capacitaciones_bp.route('/obtener_responsables/<nit_empresa>')
def obtener_responsables(nit_empresa):
    """
    Devuelve el personal (responsables) asociado a una empresa,
    filtrado por el NIT de la empresa.
    """
    try:
        connection = get_db()  # 🔄 Conexión centralizada
        cursor = connection.cursor(dictionary=True)

        # Traer el personal activo de esa empresa
        cursor.execute("""
            SELECT id, nombre_completo 
            FROM usuarios
            WHERE nit_empresa = %s AND estado = 'Activo'
        """, (nit_empresa,))
        responsables = cursor.fetchall()

        return jsonify(responsables)

    except mysql.connector.Error as e:
        print(f"Error al obtener responsables: {e}")
        return jsonify([])

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()



@capacitaciones_bp.route('/editar_capacitacion/<int:capacitacion_id>', methods=['GET', 'POST'])
@requiere_roles("Super Administrador", "Administrador")
def editar_capacitacion(capacitacion_id):
    """Editar capacitación con responsable y personal asignado (compatible con HTML y AJAX JSON)"""
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    try:
        print(f"🔄 Editando capacitación {capacitacion_id}")

        connection = get_db()  # 🔄 Conexión centralizada
        cursor = connection.cursor(dictionary=True)

        # =========================
        # POST → Guardar cambios
        # =========================
        if request.method == 'POST':
            data = request.form
            personal_ids = request.form.getlist('personal[]')
            print("📋 Datos recibidos:", dict(data))
            print("👥 Personal asignado recibido:", personal_ids)

            nit_empresa = data.get('nit_empresa')
            tema = data.get('tema')
            fecha = data.get('fecha')
            hora = data.get('hora')
            responsable_id = data.get('responsable_id')
            estado = data.get('estado')
            hora_changed = data.get('hora_changed') == 'true'

            # Mantener hora actual si no se cambió
            cursor.execute("SELECT TIME_FORMAT(hora, '%H:%i') as hora_formateada FROM capacitaciones WHERE id = %s", (capacitacion_id,))
            datos_actuales = cursor.fetchone()
            if not hora_changed and datos_actuales:
                hora = datos_actuales['hora_formateada']
                print(f"🕒 Manteniendo hora actual: {hora}")

            # Validar campos obligatorios
            campos_obligatorios = ['tema', 'fecha', 'responsable_id']
            campos_faltantes = [campo for campo in campos_obligatorios if not data.get(campo)]
            if campos_faltantes:
                flash(f"❌ Faltan campos requeridos: {', '.join(campos_faltantes)}", "error")
                return redirect(url_for('capacitaciones.capacitaciones'))

            # Actualizar capacitación
            actualizaciones = {
                'nit_empresa': nit_empresa,
                'tema': tema,
                'fecha': fecha,
                'hora': hora,
                'responsable_id': responsable_id,
                'estado': estado
            }
            set_clause = ', '.join(f"{campo} = %s" for campo in actualizaciones.keys())
            values = list(actualizaciones.values()) + [capacitacion_id]

            query = f"UPDATE capacitaciones SET {set_clause}, fecha_actualizacion = NOW() WHERE id = %s"
            cursor.execute(query, values)
            connection.commit()
            print(f"✅ Capacitación actualizada: {actualizaciones}")

            # Actualizar personal asignado
            cursor.execute("DELETE FROM capacitaciones_participantes WHERE capacitacion_id = %s", (capacitacion_id,))
            for pid in personal_ids:
                cursor.execute(
                    "INSERT INTO capacitaciones_participantes (capacitacion_id, personal_id) VALUES (%s, %s)",
                    (capacitacion_id, pid)
                )
            connection.commit()
            print(f"👥 Personal asignado actualizado: {personal_ids}")

            flash('✅ Capacitación y personal actualizado exitosamente', 'success')
            return redirect(url_for('capacitaciones.capacitaciones'))

        # =========================
        # GET → Mostrar o devolver datos JSON
        # =========================
        else:
            # Cargar datos principales
            cursor.execute("""
                SELECT 
                    c.*,
                    e.nombre AS nombre_empresa,
                    u.nombre_completo AS responsable_nombre,
                    TIME_FORMAT(c.hora, '%H:%i') AS hora_formateada
                FROM capacitaciones c
                JOIN empresas e ON c.nit_empresa = e.nit_empresa
                LEFT JOIN usuarios u ON c.responsable_id = u.id
                WHERE c.id = %s
            """, (capacitacion_id,))
            capacitacion = cursor.fetchone()

            # Personal asignado
            cursor.execute("SELECT personal_id FROM capacitaciones_participantes WHERE capacitacion_id = %s", (capacitacion_id,))
            personal_asignado = [str(p['personal_id']) for p in cursor.fetchall()]
            print(f"👥 Personal asignado actual: {personal_asignado}")

            # Si la petición viene de fetch (AJAX), devolver JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    "capacitacion": capacitacion,
                    "personal_asignado": personal_asignado
                })

            # Si es un acceso directo (GET normal), renderizar la vista
            cursor.execute("SELECT id, nombre_completo FROM personal WHERE nit_empresa = %s AND estado='Activo' ORDER BY nombre_completo", (capacitacion['nit_empresa'],))
            personal = cursor.fetchall()
            cursor.execute("SELECT nit_empresa, nombre FROM empresas WHERE estado='Activa' ORDER BY nombre")
            empresas = cursor.fetchall()
            cursor.execute("SELECT id, nombre_completo FROM usuarios WHERE estado='Activo' ORDER BY nombre_completo")
            usuarios = cursor.fetchall()

            

    except mysql.connector.Error as e:
        print(f"❌ Error SQL al editar capacitación: {e}")
        flash('Error al editar la capacitación', 'error')
        return redirect(url_for('capacitaciones.capacitaciones'))

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

@capacitaciones_bp.route('/eliminar_capacitacion/<int:capacitacion_id>', methods=['POST'])
@requiere_roles("Super Administrador")
def eliminar_capacitacion(capacitacion_id):
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    try:
        connection = get_db()  # 🔄 Conexión centralizada
        cursor = connection.cursor()

        cursor.execute("SELECT id FROM capacitaciones WHERE id = %s", (capacitacion_id,))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'Capacitación no encontrada'}), 404

        cursor.execute("DELETE FROM evaluaciones_capacitacion WHERE capacitacion_id = %s", (capacitacion_id,))
        cursor.execute("DELETE FROM capacitaciones WHERE id = %s", (capacitacion_id,))
        connection.commit()
        return jsonify({'success': True, 'message': 'Capacitación eliminada correctamente'})

    except mysql.connector.Error as e:
        print(f"Error al eliminar capacitación: {e}")
        flash("Error al eliminar capacitación")
        return jsonify({'success': False, 'message': 'Error en la base de datos'}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'connection' in locals(): connection.close()

@capacitaciones_bp.route('/actualizar_estado_capacitacion/<int:capacitacion_id>', methods=['POST'])
@requiere_roles("Super Administrador", "Administrador")
def actualizar_estado_capacitacion(capacitacion_id):
    """Actualiza el estado de una capacitación (Aprobada o Rechazada)."""
    if 'usuario_id' not in session:
        return jsonify({"success": False, "message": "No autorizado"}), 401

    data = request.get_json()
    nuevo_estado = data.get('estado')

    if nuevo_estado not in ['Aprobada', 'Rechazada']:
        return jsonify({"success": False, "message": "Estado no válido"}), 400

    try:
        connection = get_db()  # 🔄 Conexión centralizada
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE capacitaciones
            SET estado = %s
            WHERE id = %s
        """, (nuevo_estado, capacitacion_id))

        connection.commit()
        return jsonify({"success": True})

    except mysql.connector.Error as e:
        print(f"⚠️ Error al actualizar estado de capacitación: {e}")
        return jsonify({"success": False, "message": "Error en la base de datos"}), 500

    finally:
        if 'cursor' in locals(): cursor.close()
        if 'connection' in locals(): connection.close()



from . import evaluaciones, reportes