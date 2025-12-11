# ============================================================
# IMPORTACIONES
# ============================================================
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
import mysql.connector
from utils.helpers import guardar_json
from utils.permisos import requiere_roles
from datetime import date, datetime


# ============================================================
# BLUEPRINT INVENTARIO EPP
# ============================================================
inventario_bp = Blueprint("inventario", __name__, url_prefix="/inventario")


# ============================================================
# RUTA: Ver Inventario
# ============================================================
@inventario_bp.route('/ver_inventario', methods=['GET'])
def ver_inventario():
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    conexion = None
    cursor = None
    try:
        print(">>> Entró al endpoint /inventario/ver")

        conexion = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="gestussg"
        )
        cursor = conexion.cursor(dictionary=True)
        print(">>> Conexión establecida con la BD")

        # Usuario actual
        cursor.execute("""
            SELECT u.nombre_completo, r.nombre AS rol
            FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            WHERE u.id = %s
        """, (session['usuario_id'],))
        usuario = cursor.fetchone()
        print(f">>> Usuario actual: {usuario}")

        # Filtro
        filtro = request.args.get('filtro', None)

        # Paginación
        por_pagina = 10
        pagina_actual = int(request.args.get('pagina', 1))
        offset = (pagina_actual - 1) * por_pagina

        # Consulta base para EPP agrupados por nombre
        base_query = """
            SELECT
                nombre,
                tipo_proteccion,
                normativa_cumplida,
                proveedor,
                vida_util_dias,
                MAX(fecha_vencimiento) AS fecha_vencimiento,
                SUM(stock) AS stock,
                COUNT(*) AS cantidad_registros
            FROM epp
        """
        where_clause = ""
        if filtro == 'agotados':
            where_clause = " WHERE fecha_vencimiento < CURDATE()"

        group_order = " GROUP BY nombre, tipo_proteccion, normativa_cumplida, proveedor, vida_util_dias ORDER BY nombre ASC"

        # Contar total de grupos
        count_query = f"SELECT COUNT(*) AS total FROM ({base_query}{where_clause}{group_order}) AS grouped_epp"
        cursor.execute(count_query)
        total_registros = cursor.fetchone()['total']
        total_paginas = (total_registros + por_pagina - 1) // por_pagina

        # EPP agrupados con paginación
        full_query = f"{base_query}{where_clause}{group_order} LIMIT %s OFFSET %s"
        cursor.execute(full_query, (por_pagina, offset))
        epps = cursor.fetchall()
        print(f">>> Total EPP agrupados obtenidos: {len(epps)}")

        # Indicadores (sin cambios, ya que son conteos generales)
        cursor.execute("""
            SELECT COUNT(*) AS stock_bajo
            FROM epp
            WHERE DATEDIFF(fecha_vencimiento, CURDATE()) <= 120
        """)
        stock_bajo = cursor.fetchone()['stock_bajo']
        print(f">>> Stock bajo (<=120 días): {stock_bajo}")

        cursor.execute("""
            SELECT COUNT(*) AS agotados
            FROM epp
            WHERE fecha_vencimiento < CURDATE()
        """)
        agotados = cursor.fetchone()['agotados']
        print(f">>> EPP agotados: {agotados}")

        cursor.execute("""
            SELECT COUNT(*) AS entregados_mes
            FROM epp_asignados
            WHERE MONTH(fecha_entrega) = MONTH(CURDATE())
            AND YEAR(fecha_entrega) = YEAR(CURDATE())
        """)
        entregados_mes = cursor.fetchone()['entregados_mes']
        print(f">>> EPP entregados este mes: {entregados_mes}")

        return render_template(
            'ver_inventario.html',
            usuario_actual=usuario,
            epps=epps,
            total_epp=total_registros,
            stock_bajo=stock_bajo,
            agotados=agotados,
            entregados_mes=entregados_mes,
            pagina_actual=pagina_actual,
            total_paginas=total_paginas,
            filtro=filtro
        )

    except mysql.connector.Error as e:
        print(f">>> ERROR en MySQL: {e}")
        # Evitar mostrar detalles de la excepción al usuario por seguridad/UX
        flash("Error al conectar con la base de datos", "danger")
        return redirect(url_for('auth.dashboard'))

    except Exception as e:
        print(f">>> ERROR en /inventario/ver: {e}")
        flash("Error al cargar el inventario", "error")
        return redirect(url_for('auth.dashboard'))

    finally:
        if cursor: cursor.close()
        if conexion: conexion.close()
        print(">>> Cursor y conexión cerrados en /inventario/ver")


# ============================================================
# RUTA: Agregar EPP
# ============================================================
@inventario_bp.route('/agregar', methods=['GET', 'POST'])
@requiere_roles("Super Administrador", "Administrador", "Administrador Empresa")
def agregar_epp():
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    conexion = None
    cursor = None
    try:
        print(">>> Entró al endpoint /inventario/agregar")

        conexion = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="gestussg"
        )
        cursor = conexion.cursor(dictionary=True)
        print(">>> Conexión establecida con la BD")

        cursor.execute("""
            SELECT u.nombre_completo, r.nombre AS rol
            FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            WHERE u.id = %s
        """, (session['usuario_id'],))
        usuario = cursor.fetchone()
        print(f">>> Usuario actual: {usuario}")

        if request.method == 'POST':
            print(">>> POST recibido en /inventario/agregar")
            data = request.form.to_dict()
            print(f">>> Datos recibidos: {data}")

            cursor.execute("""
                INSERT INTO epp (
                    nombre, tipo_proteccion, normativa_cumplida,
                    proveedor, vida_util_dias, fecha_vencimiento, stock
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                data['nombre'], data['tipo_proteccion'], data['normativa_cumplida'],
                data['proveedor'], int(data['vida_util_dias']),
                data['fecha_vencimiento'], int(data['stock'])
            ))
            conexion.commit()
            print("✅ EPP agregado correctamente en la BD")

            flash('Elemento de EPP agregado correctamente.', 'success')
            return redirect(url_for('inventario.ver_inventario'))

        return render_template('agregar_epp.html', usuario_actual=usuario)
    
    except mysql.connector.Error as e:
        print(f">>> ERROR en MySQL: {e}")
        flash("Error al conectar con la base de datos", "danger")
        return redirect(url_for('inventario.ver_inventario'))

    except Exception as e:
        print(f">>> ERROR en /inventario/agregar: {e}")
        flash("Error al agregar el EPP", "danger")
        return redirect(url_for('inventario.ver_inventario'))
    finally:
        if cursor: cursor.close()
        if conexion: conexion.close()
        print(">>> Cursor y conexión cerrados en /inventario/agregar")


# ============================================================
# RUTA: Editar EPP (por nombre, actualiza todos los registros con ese nombre)
# ============================================================
@inventario_bp.route('/editar/<epp_nombre>', methods=['GET', 'POST'])
@requiere_roles("Super Administrador", "Administrador", "Administrador Empresa")
def editar_epp(epp_nombre):
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    conexion = None
    cursor = None
    try:
        print(f">>> Entró al endpoint /inventario/editar/{epp_nombre}")

        conexion = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="gestussg"
        )
        cursor = conexion.cursor(dictionary=True)
        print(">>> Conexión establecida con la BD")

        # Obtener rol del usuario actual
        cursor.execute("""
            SELECT u.nombre_completo, r.nombre AS rol
            FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            WHERE u.id = %s
        """, (session['usuario_id'],))
        usuario = cursor.fetchone()
        rol = usuario['rol']
        print(f">>> Usuario actual: {usuario}")

        # Obtener datos del EPP (primer registro con ese nombre)
        cursor.execute("SELECT * FROM epp WHERE nombre = %s LIMIT 1", (epp_nombre,))
        epp = cursor.fetchone()
        if not epp:
            flash("Elemento EPP no encontrado", "warning")
            return redirect(url_for('inventario.ver_inventario'))

        if request.method == 'POST':
            data = request.form.to_dict()
            print(f">>> Datos recibidos: {data}")

            # ---------------------------
            # Campos editables por rol
            # ---------------------------
            campos_super = ['nombre', 'tipo_proteccion', 'normativa_cumplida', 'proveedor',
                            'vida_util_dias', 'fecha_vencimiento', 'stock']
            campos_admin_empresa = ['nombre', 'tipo_proteccion', 'fecha_vencimiento', 'stock']

            campos_permitidos = campos_super if rol == "Super Administrador" else campos_admin_empresa

            # Construir UPDATE dinámico
            updates = []
            values = []
            for campo in campos_permitidos:
                if campo in data:
                    updates.append(f"{campo} = %s")
                    values.append(data[campo])

            if updates:
                query = f"UPDATE epp SET {', '.join(updates)} WHERE nombre = %s"
                values.append(epp_nombre)
                print("🔧 Ejecutando query:", query, values)
                cursor.execute(query, values)
                conexion.commit()
                print("✅ EPP actualizado correctamente en la BD")
                flash("EPP actualizado correctamente", "success")
            else:
                flash("No tienes permisos para editar los campos enviados", "warning")

            return redirect(url_for('inventario.ver_inventario'))

        return render_template('editar_epp.html', usuario_actual=usuario, epp=epp)

    except mysql.connector.Error as e:
        print(f">>> ERROR en MySQL/{epp_nombre}: {e}")
        flash("Error al conectar con la base de datos", "danger")
        return redirect(url_for('inventario.ver_inventario'))

    except Exception as e:
        print(f">>> ERROR en /inventario/editar/{epp_nombre}: {e}")
        flash("Error al actualizar el EPP", "danger")
        return redirect(url_for('inventario.ver_inventario'))

    finally:
        if cursor: cursor.close()
        if conexion: conexion.close()
        print(f">>> Cursor y conexión cerrados en /inventario/editar/{epp_nombre}")



# ============================================================
# RUTA: Eliminar EPP (por nombre, elimina todos los registros con ese nombre)
# ============================================================
@inventario_bp.route('/eliminar/<epp_nombre>')
@requiere_roles("Super Administrador", "Administrador", "Administrador Empresa")
def eliminar_epp(epp_nombre):
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    conexion = None
    cursor = None
    try:
        print(f">>> Entró al endpoint /inventario/eliminar/{epp_nombre}")

        conexion = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="gestussg"
        )
        cursor = conexion.cursor(dictionary=True)
        print(">>> Conexión establecida con la BD")

        # Obtener IDs de EPP con ese nombre
        cursor.execute("SELECT id FROM epp WHERE nombre = %s", (epp_nombre,))
        epp_ids = [row['id'] for row in cursor.fetchall()]

        if not epp_ids:
            flash("Elemento EPP no encontrado", "warning")
            return redirect(url_for('inventario.ver_inventario'))

        # Verificar si alguno tiene asignaciones
        for epp_id in epp_ids:
            cursor.execute("""
                SELECT COUNT(*) AS asignados 
                FROM epp_asignados 
                WHERE epp_id = %s AND estado = 'Entregado'
            """, (epp_id,))
            asignados = cursor.fetchone()['asignados']

            if asignados > 0:
                flash(f"No se puede eliminar el EPP '{epp_nombre}' porque tiene asignaciones ACTIVAS.", "warning")
                return redirect(url_for('inventario.ver_inventario'))


        # Cambiar cursor a no dictionary para DELETE
        cursor.close()
        cursor = conexion.cursor()

        cursor.execute("DELETE FROM epp WHERE nombre = %s", (epp_nombre,))
        conexion.commit()
        print(f"✅ EPP '{epp_nombre}' eliminado correctamente")

        flash("EPP eliminado correctamente", "success")

    except mysql.connector.Error as e:
        print(f"❌ ERROR en MySQL /{epp_nombre}: {e}")
        flash("Error al eliminar EPP", "danger")
        return redirect(url_for('inventario.ver_inventario'))

    except Exception as e:
        print(f"Error al eliminar EPP: {e}")
        flash("Error al eliminar EPP", "danger")
        return redirect(url_for('inventario.ver_inventario'))
    finally:
        if cursor:
            cursor.close()
            print(">>> Cursor cerrado en /inventario/eliminar")
        if conexion:
            conexion.close()
            print(">>> Conexión cerrada en /inventario/eliminar")

    return redirect(url_for('inventario.ver_inventario')) 


# ============================================================
# API: Obtener Inventario de EPP
# ============================================================
@inventario_bp.route('/api/inventario_epp', methods=['GET'])
def api_inventario_epp():
    conexion = None
    cursor = None
    try:
        print(">>> Entró al endpoint GET /inventario/api")

        # Conexión a la base de datos
        conexion = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="gestussg"
        )
        cursor = conexion.cursor(dictionary=True)
        print(">>> Conexión establecida con la BD")

        # Consulta de inventario
        cursor.execute("""
            SELECT id, nombre, tipo_proteccion, normativa_cumplida, proveedor,
                vida_util_dias, fecha_vencimiento, stock
            FROM epp
            ORDER BY nombre ASC
        """)
        inventario = cursor.fetchall()
        print(f">>> Inventario obtenido: {len(inventario)} registros")

        for item in inventario:
            if isinstance(item.get("fecha_vencimiento"), (date, datetime)):
                item["fecha_vencimiento"] = item["fecha_vencimiento"].strftime("%Y-%m-%d")

        for i, item in enumerate(inventario, start=1):
            print(f" {i}. {item['nombre']} - Stock: {item['stock']} - Vence: {item['fecha_vencimiento']}")

        print(">>> Respuesta lista para enviar al cliente")

        return jsonify({"status": "success", "data": inventario}), 200

    except mysql.connector.Error as e:
        print(f"❌ ERROR en API GET /inventario/api: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
            print(">>> Cursor cerrado en GET /inventario/api")
        if conexion:
            conexion.close()
            print(">>> Conexión cerrada en GET /inventario/api")



