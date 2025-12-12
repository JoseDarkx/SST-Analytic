from flask import render_template, request, redirect, url_for, session, flash, jsonify
from database import get_connection as get_db
from extensions import get_db
from flask import Blueprint
import mysql.connector
from utils.permisos import requiere_roles
from datetime import datetime
epp_bp = Blueprint("epp", __name__, url_prefix="/epp")


# ============================================================
# CONTROL DE EPP
# ============================================================
@epp_bp.route('/control_epp')
def control_epp(): 
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    try:
        conexion = get_db()
        cursor = conexion.cursor(dictionary=True)

        # --- Datos del usuario actual ---
        cursor.execute("""
            SELECT u.nombre_completo, u.nit_empresa, r.nombre AS rol
            FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            WHERE u.id = %s
        """, (session['usuario_id'],))
        usuario = cursor.fetchone()
        rol = usuario['rol'] if usuario else ''
        nit_usuario = usuario['nit_empresa'] if usuario else ''

        # 🧮 Paginación
        por_pagina = 10
        pagina_actual = int(request.args.get('pagina', 1))
        offset = (pagina_actual - 1) * por_pagina

        # --- Contar total de registros (filtrado por rol) ---
        count_query = "SELECT COUNT(*) AS total FROM epp_asignados ea JOIN personal p ON ea.personal_id = p.id WHERE 1=1"
        count_params = []
        
        if rol != 'Super Administrador':
            count_query += " AND p.nit_empresa = %s"
            count_params.append(nit_usuario)
        
        cursor.execute(count_query, count_params)
        total_registros = cursor.fetchone()['total']
        total_paginas = (total_registros + por_pagina - 1) // por_pagina

        # --- EPP asignados con límite (filtrado por rol) ---
        query = """
            SELECT ea.id, ea.personal_id, ea.epp_id, ea.fecha_entrega, ea.estado, ea.observaciones, ea.firmado,
                p.nombre_completo AS nombre_personal, p.nit_empresa,
                e.nombre AS nombre_epp
            FROM epp_asignados ea
            JOIN personal p ON ea.personal_id = p.id
            JOIN epp e ON ea.epp_id = e.id
            WHERE 1=1
        """
        params = []
        
        if rol != 'Super Administrador':
            query += " AND p.nit_empresa = %s"
            params.append(nit_usuario)
        
        query += " ORDER BY ea.id DESC LIMIT %s OFFSET %s"
        params += [por_pagina, offset]
        
        cursor.execute(query, params)
        epp_asignados = cursor.fetchall()

        # --- Listado de personal (filtrado por rol) ---
        personal_query = """
            SELECT p.id, p.nombre_completo, p.cargo, e.nombre AS empresa, p.nit_empresa
            FROM personal p
            JOIN empresas e ON p.nit_empresa = e.nit_empresa
            WHERE 1=1
        """
        personal_params = []
        
        if rol != 'Super Administrador':
            personal_query += " AND p.nit_empresa = %s"
            personal_params.append(nit_usuario)
        
        personal_query += " ORDER BY p.nombre_completo"
        cursor.execute(personal_query, personal_params)
        personal = cursor.fetchall()

        # --- Listado de EPP ---
        cursor.execute("SELECT id, nombre, tipo_proteccion FROM epp")
        epps = cursor.fetchall()

    except Exception as e:
        print(f"Error al obtener los datos de los EPP : {e}")
        flash("Error al obtener los datos de los EPP ", "danger")
        return redirect(url_for('auth.iniciar_sesion'))
    finally:
        cursor.close()

    return render_template(
        'control_epp.html',
        usuario_actual=usuario,
        epp_asignados=epp_asignados,
        personal=personal,
        epps=epps,
        pagina_actual=pagina_actual,
        total_paginas=total_paginas,
        rol=rol,
        now=datetime.now()
    )


# ============================================================
# ASIGNAR EPP (con prints de depuración)
# ============================================================
@epp_bp.route('/asignar_epp', methods=['GET', 'POST'])
@requiere_roles("Super Administrador", "Administrador", "Administrador Empresa")
def asignar_epp():
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    conexion = get_db()
    cursor = conexion.cursor(dictionary=True)

    # ==========================================
    # DATOS DEL USUARIO ACTUAL
    # ==========================================
    cursor.execute("""
        SELECT u.nombre_completo, u.nit_empresa, r.nombre AS rol
        FROM usuarios u
        JOIN roles r ON u.rol_id = r.id
        WHERE u.id = %s
    """, (session['usuario_id'],))
    usuario = cursor.fetchone()
    rol = usuario['rol'] if usuario else ''
    nit_usuario = usuario['nit_empresa'] if usuario else ''
    print(f"[DEBUG] Usuario actual: {usuario}")

    # ==========================================
    # LISTADO DE PERSONAL (filtrado por rol)
    # ==========================================
    personal_query = """
        SELECT p.id, p.nombre_completo, p.cargo, e.nombre AS empresa, p.nit_empresa
        FROM personal p
        JOIN empresas e ON p.nit_empresa = e.nit_empresa
        WHERE 1=1
    """
    personal_params = []
    
    if rol != 'Super Administrador':
        personal_query += " AND p.nit_empresa = %s"
        personal_params.append(nit_usuario)
    
    personal_query += " ORDER BY p.nombre_completo"
    cursor.execute(personal_query, personal_params)
    personal = cursor.fetchall()
    print(f"[DEBUG] Personal encontrado: {len(personal)} registros")

    # ==========================================
    # LISTADO DE EPP DISPONIBLES
    # ==========================================
    cursor.execute("SELECT id, nombre, tipo_proteccion FROM epp")
    epps = cursor.fetchall()
    print(f"[DEBUG] EPPs disponibles: {len(epps)} registros")

    # ==========================================
    # PROCESAR FORMULARIO (POST)
    # ==========================================
    if request.method == 'POST':
        print("[DEBUG] Método POST detectado. Procesando datos del formulario...")

        try:
            # Capturar valores desde el formulario
            personal_id = int(request.form['personal_id'])
            epp_id = int(request.form['epp_id'])
            fecha_entrega = request.form['fecha_entrega']
            estado = request.form['estado']
            observaciones = request.form.get('observaciones', '')
            firmado = 1 if 'firmado' in request.form else 0

            # Mostrar valores capturados en consola
            print("=== Datos recibidos del formulario ===")
            print(f"personal_id: {personal_id}")
            print(f"epp_id: {epp_id}")
            print(f"fecha_entrega: {fecha_entrega}")
            print(f"estado: {estado}")
            print(f"observaciones: {observaciones}")
            print(f"firmado: {firmado}")
            print("======================================")

            # ⚠️ VALIDACIÓN: Verificar que el personal pertenece a la empresa del usuario (si no es Super Admin)
            if rol != 'Super Administrador':
                cursor.execute("""
                    SELECT nit_empresa FROM personal WHERE id = %s
                """, (personal_id,))
                personal_record = cursor.fetchone()
                if not personal_record or (personal_record['nit_empresa'] or '').strip() != nit_usuario.strip():
                    print(f"[SECURITY] Intento de asignar personal de otra empresa")
                    cursor.close()
                    return jsonify({"success": False, "message": "❌ No tienes permiso para asignar EPP a este personal"}), 403

            # ⚠️ VALIDACIÓN: Fecha no puede ser en el pasado (excepto para Super Admin)
            fecha_obj = datetime.strptime(fecha_entrega, '%Y-%m-%d').date()
            today = datetime.today().date()
            if rol != 'Super Administrador' and fecha_obj < today:
                print(f"[DEBUG] Fecha {fecha_entrega} es anterior a hoy {today}")
                cursor.close()
                return jsonify({"success": False, "message": "❌ La fecha de entrega no puede ser en el pasado"}), 400

            # Insertar registro en la base de datos
            cursor.execute("""
                INSERT INTO epp_asignados (
                    epp_id, personal_id, fecha_entrega,
                    estado, observaciones, firmado
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                epp_id, personal_id, fecha_entrega,
                estado, observaciones, firmado
            ))
            conexion.commit()
            print("[DEBUG] Inserción completada y cambios confirmados (commit).")
            cursor.close()

            return jsonify({"success": True, "message": "✅ EPP asignado correctamente"}), 200

        except Exception as e:
            print(f"[ERROR] Error al asignar EPP: {e}")
            cursor.close()
            return jsonify({"success": False, "message": f"❌ Error: {str(e)}"}), 500

    # ==========================================
    # CIERRE DE CURSOR Y RENDER
    # ==========================================
    cursor.close()
    print("[DEBUG] Renderizando control_epp.html")
    return render_template('control_epp.html', usuario_actual=usuario, personal=personal, epps=epps)


# ============================================================
# EDITAR EPP ASIGNADO
# ============================================================
@epp_bp.route('/editar_epp/<int:asignacion_id>', methods=['GET', 'POST'])
@requiere_roles("Super Administrador", "Administrador", "Administrador Empresa")
def editar_epp(asignacion_id):
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    conexion = None
    cursor = None
    try:
        conexion = get_db()
        cursor = conexion.cursor(dictionary=True)

        # Obtener rol actual del usuario
        cursor.execute("""
            SELECT r.nombre AS rol
            FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            WHERE u.id = %s
        """, (session['usuario_id'],))
        user_info = cursor.fetchone()
        rol = user_info['rol'] if user_info else None

        # Obtener datos de la asignación
        cursor.execute("""
            SELECT ea.id, ea.fecha_entrega, ea.estado, ea.observaciones, ea.firmado,
                   ea.epp_id, p.nombre_completo AS nombre_personal,
                   e.nombre AS epp_nombre, e.tipo_proteccion, e.stock
            FROM epp_asignados ea
            JOIN personal p ON ea.personal_id = p.id
            JOIN epp e ON ea.epp_id = e.id
            WHERE ea.id = %s
        """, (asignacion_id,))
        asignacion = cursor.fetchone()

        if not asignacion:
            flash("La asignación no existe.", "danger")
            return redirect(url_for('epp.control_epp'))

        # Lista de EPP (solo para Super Admin)
        cursor.execute("SELECT id, nombre, tipo_proteccion, stock FROM epp")
        lista_epp = cursor.fetchall()

        if request.method == 'POST':
            data = request.form.to_dict()
            print(f"📩 Datos recibidos: {data}")

        # Campos editables según rol
            if rol == 'Super Administrador':
                campos_permitidos = ['epp_id', 'fecha_entrega', 'estado', 'observaciones', 'firmado']
            elif rol == 'Administrador':
                campos_permitidos = ['estado', 'observaciones', 'firmado']
            else:
                campos_permitidos = ['observaciones']  # Admin Empresa puede editar observaciones

            updates = []
            values = []

            for campo in campos_permitidos:
                if campo == 'firmado':
                    valor = 1 if 'firmado' in data else 0
                else:
                    valor = data.get(campo, asignacion[campo])
                updates.append(f"{campo} = %s")
                values.append(valor)

            values.append(asignacion_id)
            query = f"UPDATE epp_asignados SET {', '.join(updates)} WHERE id = %s"
            cursor.execute(query, values)
            conexion.commit()

            return jsonify({"success": True, "message": "✅ EPP actualizado correctamente"}), 200

        # Renderizar modal (GET)
        return render_template(
            'editar_epp.html',
            asignacion=asignacion,
            epps=lista_epp,
            rol=rol
        )

    except mysql.connector.Error as e:
        print(f"❌ Error MySQL: {e}")
        return jsonify({"success": False, "message": "Error en la base de datos"}), 500

    except Exception as e:
        print(f"❌ Error al actualizar EPP: {e}")
        return jsonify({"success": False, "message": f"Error al actualizar: {str(e)}"}), 500

    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()


# ============================================================
# REPORTE GENERAL DE EPP
# ============================================================
@epp_bp.route('/reporte_general_epp', methods=['GET', 'POST'])
def reporte_general_epp():
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))
    
    try:

        conexion = get_db()
        cursor = conexion.cursor(dictionary=True)

        cursor.execute("""
            SELECT u.nombre_completo, r.nombre AS rol
            FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            WHERE u.id = %s
        """, (session['usuario_id'],))
        usuario = cursor.fetchone()

        tipo_epp = request.args.get('tipoEpp')
        fecha_inicio = request.args.get('fechaInicio')
        fecha_fin = request.args.get('fechaFin')

        condiciones = []
        parametros = []

        if tipo_epp and tipo_epp != "Todos":
            condiciones.append("e.nombre = %s")
            parametros.append(tipo_epp)

        if fecha_inicio:
            condiciones.append("ea.fecha_entrega >= %s")
            parametros.append(fecha_inicio)

        if fecha_fin:
            condiciones.append("ea.fecha_entrega <= %s")
            parametros.append(fecha_fin)

        where_clause = "WHERE " + " AND ".join(condiciones) if condiciones else ""

        query = f"""
            SELECT COUNT(DISTINCT ea.personal_id) AS trabajadores,
            COUNT(*) AS epp_asignados,
            SUM(CASE WHEN e.fecha_vencimiento >= CURDATE() THEN 1 ELSE 0 END) AS vigentes,
            SUM(CASE WHEN e.fecha_vencimiento BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 30 DAY) THEN 1 ELSE 0 END) AS proximos_vencer,
            SUM(CASE WHEN e.fecha_vencimiento < CURDATE() THEN 1 ELSE 0 END) AS vencidos
            FROM epp_asignados ea
            JOIN epp e ON ea.epp_id = e.id
            {where_clause}
        """
        cursor.execute(query, parametros)
        resultado = cursor.fetchone()

        estado = "OK"
        if resultado and resultado.get("vencidos") is not None and resultado.get("vencidos", 0) > 5:
            estado = "Crítico"
        elif resultado["proximos_vencer"] or 0 > 5:
            estado = "Atención"

        resumen = {
            "trabajadores": resultado["trabajadores"],
            "epp_asignados": resultado["epp_asignados"],
            "vigentes": resultado["vigentes"],
            "proximos_vencer": resultado["proximos_vencer"],
            "vencidos": resultado["vencidos"],
            "estado": estado
        }

    except Exception as e:
        print(f"Error al obtener el reporte de EPP: {e}")
        flash("Error al obtener el reporte de EPP")
        return redirect(url_for('epp.control_epp'))

    cursor.close()
    return render_template('reporte_general_epp.html', usuario_actual=usuario, resumen=resumen)


# ============================================================
# ELIMINAR EPP ASIGNADO (Petición AJAX con JSON)
# ============================================================
@epp_bp.route('/eliminar/<int:asignacion_id>', methods=['POST'])
@requiere_roles("Super Administrador")
def eliminar_epp(asignacion_id):
    if 'usuario_id' not in session:
        return jsonify({"success": False, "error": "No autorizado"}), 401

    try:
        conexion = get_db()
        cursor = conexion.cursor()
        cursor.execute("DELETE FROM epp_asignados WHERE id = %s", (asignacion_id,))
        conexion.commit()

        print(f"🗑️ EPP asignado {asignacion_id} eliminado correctamente.")
        return jsonify({"success": True, "message": "EPP eliminado correctamente."})
    except Exception as e:
        print(f"❌ Error al eliminar EPP asignado: {e}")
        return jsonify({"success": False, "error": "Error al eliminar el registro."}), 500
    finally:
        cursor.close()


# ============================================================
# VER EPP ASIGNADO
# ============================================================
@epp_bp.route('/api/ver_epp_asignado/<int:personal_id>', methods=['GET'])
def api_ver_epp_asignado(personal_id):
    """Devuelve los datos del trabajador, entregas y novedades en JSON para llenar el modal"""
    try:
        conexion = get_db()
        cursor = conexion.cursor(dictionary=True)

        cursor.execute("SELECT nombre_completo, cargo, estado FROM personal WHERE id = %s", (personal_id,))
        trabajador = cursor.fetchone()

        cursor.execute("""
            SELECT ea.fecha_entrega, e.nombre AS nombre_epp, e.normativa_cumplida AS modelo,
                   e.fecha_vencimiento, 'Juan López' AS responsable
            FROM epp_asignados ea
            JOIN epp e ON ea.epp_id = e.id
            WHERE ea.personal_id = %s
            ORDER BY ea.fecha_entrega DESC
        """, (personal_id,))
        entregas = cursor.fetchall()

        cursor.execute("""
            SELECT '2025-03-12' AS fecha, e.nombre AS tipo_epp, 'Dañado' AS motivo,
                p.nombre_completo AS entidad, 'Aprobado' AS estado
            FROM epp_asignados ea
            JOIN epp e ON ea.epp_id = e.id
            JOIN personal p ON ea.personal_id = p.id
            WHERE ea.personal_id = %s
            LIMIT 2
        """, (personal_id,))
        novedades = cursor.fetchall()

        cursor.close()
        return jsonify({
            'trabajador': trabajador,
            'entregas': entregas,
            'novedades': novedades
        }), 200

    except Exception as e:
        print(f"❌ Error en API ver_epp_asignado: {e}")
        return jsonify({'error': str(e)}), 500

@epp_bp.route('/api/epp_asignados', methods=['GET'])
def api_epp_asignados():
    """API para listar todos los EPP asignados"""
    print("➡️ Entrando a /api/epp_asignados")  # Log inicial


    try:
        # Conexión a la BD
        connection = get_db()  # 🔄 Conexión centralizada
        cursor = connection.cursor(dictionary=True)

        # Consulta de EPP asignados con JOIN a personal y epp
        cursor.execute("""
            SELECT ea.id, ea.fecha_entrega, ea.estado, ea.observaciones, ea.firmado,
                p.nombre_completo AS persona, p.cargo, e.nombre AS empresa,
                ep.nombre AS epp_nombre, ep.tipo_proteccion
            FROM epp_asignados ea
            JOIN personal p ON ea.personal_id = p.id
            JOIN empresas e ON p.nit_empresa = e.nit_empresa
            JOIN epp ep ON ea.epp_id = ep.id
            ORDER BY ea.fecha_entrega DESC
        """)

        epp_asignados = cursor.fetchall()

        # 🔎 Logs en consola
        print(f"📦 Registros encontrados: {len(epp_asignados)}")
        for ea in epp_asignados[:10]:  # mostramos solo 10 primeros
            print(f" - ID:{ea['id']} | Persona:{ea['persona']} | "
                f"EPP:{ea['epp_nombre']} | Estado:{ea['estado']} | "
                f"Fecha:{ea['fecha_entrega']} | Firmado:{ea['firmado']}")

        if not epp_asignados:
            print("ℹ️ No hay EPP asignados en la base de datos")
            return jsonify({'epp_asignados': [], 'mensaje': 'No hay registros de EPP asignados'}), 200

        return jsonify({'epp_asignados': epp_asignados}), 200

    except mysql.connector.Error as e:
        print(f"❌ Error en /api/epp_asignados: {e}")
        return jsonify({'error': str(e)}), 500

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()


# ============================================================
# API: OBTENER PERSONAL POR EMPRESA
# ============================================================
@epp_bp.route('/api/personal_por_empresa/<nit_empresa>', methods=['GET'])
def api_personal_por_empresa(nit_empresa):
    """API para obtener personal de una empresa específica"""
    if 'usuario_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401

    try:
        conexion = get_db()
        cursor = conexion.cursor(dictionary=True)

        # Validar que el usuario tenga permiso para ver este personal
        cursor.execute("""
            SELECT u.nit_empresa, r.nombre AS rol
            FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            WHERE u.id = %s
        """, (session['usuario_id'],))
        usuario = cursor.fetchone()
        
        if not usuario:
            return jsonify({'error': 'Usuario no encontrado'}), 401
        
        rol = usuario['rol']
        user_nit = usuario['nit_empresa']

        # Si no es Super Admin, solo puede ver su propia empresa
        if rol != 'Super Administrador' and (user_nit or '') != nit_empresa:
            return jsonify({'error': 'No tienes permiso para acceder a este personal'}), 403

        # Obtener personal de la empresa
        cursor.execute("""
            SELECT p.id, p.nombre_completo, p.cargo
            FROM personal p
            WHERE p.nit_empresa = %s
            ORDER BY p.nombre_completo
        """, (nit_empresa,))
        
        personal = cursor.fetchall()
        cursor.close()

        return jsonify({'personal': personal}), 200

    except Exception as e:
        print(f"❌ Error en /api/personal_por_empresa: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================
# API: OBTENER DATOS DE ASIGNACIÓN EPP
# ============================================================
@epp_bp.route('/api/ver_epp/<int:asignacion_id>', methods=['GET'])
def api_ver_epp(asignacion_id):
    """API para obtener datos de una asignación de EPP (para modal Ver)"""
    if 'usuario_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401

    try:
        conexion = get_db()
        cursor = conexion.cursor(dictionary=True)

        # Obtener la asignación de EPP
        cursor.execute("""
            SELECT 
                ea.id,
                ea.fecha_entrega,
                ea.estado,
                ea.observaciones,
                ea.firmado,
                p.nombre_completo AS nombre_personal,
                p.cargo,
                e.nombre AS empresa,
                ep.nombre AS nombre_epp,
                ep.tipo_proteccion
            FROM epp_asignados ea
            JOIN personal p ON ea.personal_id = p.id
            JOIN empresas e ON p.nit_empresa = e.nit_empresa
            JOIN epp ep ON ea.epp_id = ep.id
            WHERE ea.id = %s
        """, (asignacion_id,))
        
        asignacion = cursor.fetchone()
        cursor.close()

        if not asignacion:
            return jsonify({'error': 'Asignación no encontrada'}), 404

        return jsonify(asignacion), 200

    except Exception as e:
        print(f"❌ Error en /api/ver_epp: {e}")
        return jsonify({'error': str(e)}), 500
