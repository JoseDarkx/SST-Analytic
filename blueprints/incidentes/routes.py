# ============================================================
# RUTA: INCIDENTES Y ACCIDENTES
# ============================================================

from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, current_app, flash
from utils.permisos import  requiere_roles
import os
from datetime import datetime
from extensions import get_db

# Blueprint sin url_prefix (como pediste)
incidentes_bp = Blueprint('incidentes', __name__)

# ============================================================
# LISTADO DE INCIDENTES / ACCIDENTES
# ============================================================
@incidentes_bp.route('/incidentes_accidentes')
def incidentes_accidentes():
    # 🔹 Validar sesión activa
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión primero.", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    try:
        conexion = get_db()
        cursor = conexion.cursor(dictionary=True)

        # 🔹 Obtener datos del usuario logueado
        cursor.execute("""
            SELECT u.id, u.nombre_completo, r.nombre AS rol
            FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            WHERE u.id = %s
        """, (session['usuario_id'],))
        usuario = cursor.fetchone()
        rol = usuario['rol'] if usuario else None
        print(f"Rol del usuario: {rol}")
        #El select de los incidentes
        rol_usuario = session.get("rol")
        empresa_nit = session.get("nit_empresa")

        # -------------------------------
        # Paginación
        # -------------------------------
        pagina_actual = int(request.args.get('pagina', 1))
        por_pagina = 10
        offset = (pagina_actual - 1) * por_pagina

        query_incidentes = """
            SELECT
                i.id,i.nit_empresa,i.tipo,i.clasificacion,i.fecha,i.hora,i.lugar,
                i.area,i.estado,i.severidad,i.descripcion,i.causas,i.acciones_inmediatas,
                i.responsable_investigacion_id,
                e.nombre AS empresa,
                COUNT(ip.id) AS personas_involucradas
            FROM incidentes i
            JOIN empresas e ON i.nit_empresa = e.nit_empresa
            LEFT JOIN incidentes_personal ip ON i.id = ip.incidente_id
            WHERE 1=1
        """
        params = []

        # Filter by empresa_nit for non-super administrators
        if rol_usuario != 'Super Administrador':
            query_incidentes += " AND i.nit_empresa = %s"
            params.append(empresa_nit)

        # Contar total de registros para paginación
        count_query = f"""
            SELECT COUNT(*) AS total
            FROM ({query_incidentes} GROUP BY i.id) AS subquery
        """
        cursor.execute(count_query, params)
        total_registros = cursor.fetchone()['total']
        total_paginas = (total_registros + por_pagina - 1) // por_pagina

        query_incidentes += " GROUP BY i.id ORDER BY i.fecha DESC LIMIT %s OFFSET %s"
        cursor.execute(query_incidentes, params + [por_pagina, offset])
        incidentes = cursor.fetchall()
        #print(f"Incidentes encontrados: {incidentes}")

        # ====================================================
        detalle_personal = {}
        for inc in incidentes:
            cursor.execute("""
                SELECT ip.tipo_afectacion, ip.descripcion_afectacion, 
                    ip.requirio_atencion, ip.tipo_atencion, ip.personal_id,
                    p.nombre_completo AS nombre_afectado
                FROM incidentes_personal ip
                JOIN personal p ON ip.personal_id = p.id
                WHERE ip.incidente_id = %s
            """, (inc['id'],))
            detalle_personal[inc['id']] = cursor.fetchall() or []



        print(f"Detalle de personal: {detalle_personal}")

        #Obtener datos empresas y personal
        cursor.execute("SELECT nit_empresa, nombre FROM empresas")
        empresas = cursor.fetchall()
        print(f"Empresas encontradas: {empresas}")

        cursor.execute("SELECT id, nombre_completo FROM usuarios")
        usuarios = cursor.fetchall()

        cursor.close()
        conexion.close()

        return render_template(
            'incidentes/incidentes.html',
            incidentes=incidentes,
            detalle_personal=detalle_personal,
            usuario=usuario,
            rol=rol,
            empresas=empresas,
            usuarios=usuarios,
            pagina_actual=pagina_actual,
            total_paginas=total_paginas
        )

    except Exception as e:
        print(f"❌ Error al cargar incidentes: {e}")
        flash("Error al cargar la lista de incidentes.", "danger")
        return redirect(url_for('auth.dashboard'))

    
# ============================================================
# OBTENER PERSONAL SEGÚN LA EMPRESA
# ============================================================
@incidentes_bp.route('/obtener_personal/<nit_empresa>')
def obtener_personal(nit_empresa):
    try:
        conexion = get_db()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, nombre_completo 
            FROM personal 
            WHERE nit_empresa = %s
        """, (nit_empresa,))
        personal = cursor.fetchall()
        print(f"Personal encontrado: {personal}")
        cursor.close()
        conexion.close()
        return jsonify(personal)
    except Exception as e:
        print(f"❌ Error al cargar personal: {e}")
        flash("Error al cargar la lista de personal.")
        return jsonify([])
    
@incidentes_bp.route('/api/afectados_empresa/<nit_empresa>/<int:incidente_id>')
def api_afectados_empresa(nit_empresa, incidente_id):
    try:
        conexion = get_db()
        cursor = conexion.cursor(dictionary=True)

        # 🔹 Obtener todo el personal de la empresa
        cursor.execute("""
            SELECT id, nombre_completo
            FROM personal
            WHERE nit_empresa = %s
        """, (nit_empresa,))
        personal = cursor.fetchall()

        # 🔹 Obtener IDs de los afectados en este incidente
        cursor.execute("""
            SELECT personal_id
            FROM incidentes_personal
            WHERE incidente_id = %s
        """, (incidente_id,))
        afectados = [row['personal_id'] for row in cursor.fetchall()]

        # 🔹 Marcar si cada persona está afectada
        for p in personal:
            p['afectado'] = p['id'] in afectados

        cursor.close()
        conexion.close()

        return jsonify(personal)

    except Exception as e:
        print(f"❌ Error al obtener afectados por empresa: {e}")
        return jsonify([])

@incidentes_bp.route('/agregar_incidente', methods=['POST'])
@requiere_roles("Super Administrador", "Administrador")
def agregar_incidente():
    print("📩 Llego el POST a /agregar_incidente")
    conexion = get_db()
    cursor = conexion.cursor(dictionary=True)

    try:
        data = request.form
        print("📋 Datos recibidos del formulario:", data)

        required = [
            'nit_empresa', 'tipo', 'clasificacion', 'fecha', 'hora', 'lugar',
            'descripcion', 'personal_id', 'tipo_afectacion', 'severidad',
            'responsable_investigacion_id'
        ]
        missing = [f for f in required if not data.get(f)]
        if missing:
            print("❌ Faltan campos:", missing)
            return jsonify(success=False, error=f"Faltan campos: {', '.join(missing)}"), 400

        nit_empresa = data.get('nit_empresa')
        tipo = data.get('tipo')
        clasificacion = data.get('clasificacion')
        fecha = data.get('fecha')
        hora = data.get('hora')
        lugar = data.get('lugar')
        area = data.get('area') or None
        descripcion = data.get('descripcion')
        causas = data.get('causas') or None
        acciones_inmediatas = data.get('acciones_inmediatas') or None
        estado = data.get('estado') or 'Reportado'
        severidad = data.get('severidad')
        responsable_investigacion_id = int(data.get('responsable_investigacion_id'))

        personal_id = int(data.get('personal_id'))
        tipo_afectacion = data.get('tipo_afectacion')
        descripcion_afectacion = data.get('descripcion_afectacion') or None
        requirio_atencion = 1 if data.get('requirio_atencion') in ('1', 'si', 'true', 'on') else 0
        tipo_atencion = data.get('tipo_atencion') or None

        # Generar código único
        cursor.execute("""
         SELECT AUTO_INCREMENT 
            FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'incidentes'
        """)
        next_id = cursor.fetchone()['AUTO_INCREMENT']

        codigo = f"INC-{datetime.now().year}-{next_id:04d}"
        print(f"🧾 Código generado único: {codigo}")


        # Manejar archivo (opcional)
        archivo_url = None
        if 'archivo_url' in request.files:
            archivo = request.files['archivo_url']
            if archivo and archivo.filename:
                filename = f"incidente_{datetime.now().strftime('%Y%m%d%H%M%S')}_{archivo.filename}"
                upload_path = current_app.config.get('UPLOAD_FOLDER', 'static/uploads/incidentes')
                os.makedirs(upload_path, exist_ok=True)
                archivo.save(os.path.join(upload_path, filename))
                archivo_url = f"{upload_path}/{filename}"
                print(f"📎 Archivo guardado en: {archivo_url}")

        # Insertar incidente
        cursor.execute("""
            INSERT INTO incidentes (
                nit_empresa, codigo, tipo, clasificacion, fecha, hora,
                lugar, area, descripcion, causas, acciones_inmediatas,
                estado, severidad, responsable_investigacion_id, archivo_url
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            nit_empresa, codigo, tipo, clasificacion, fecha, hora,
            lugar, area, descripcion, causas, acciones_inmediatas,
            estado, severidad, responsable_investigacion_id, archivo_url
        ))

        incidente_id = cursor.lastrowid
        print(f"✅ Incidente insertado con ID: {incidente_id}")

        # Insertar afectado
        cursor.execute("""
            INSERT INTO incidentes_personal (
                incidente_id, personal_id, tipo_afectacion,
                descripcion_afectacion, requirio_atencion, tipo_atencion
            ) VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            incidente_id, personal_id, tipo_afectacion,
            descripcion_afectacion, requirio_atencion, tipo_atencion
        ))
        print(f"👤 Afectado vinculado correctamente: {personal_id}")

        conexion.commit()
        print("💾 Transacción confirmada")

        return jsonify(success=True, incidente_id=incidente_id, codigo=codigo,
                       mensaje="Incidente y afectado registrados correctamente"), 201

    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        conexion.rollback()
        return jsonify(success=False, error=f"Error inesperado: {str(e)}"), 500

    finally:
        cursor.close()
        conexion.close()


#EDITAR INCIDENTE

@incidentes_bp.route('/editar_incidente', methods=['POST'])
@requiere_roles("Super Administrador", "Administrador")
def editar_incidente():
    print("📩 Llego el POST a /editar_incidente")

    conexion = None
    cursor = None
    try:
        conexion = get_db()
        cursor = conexion.cursor(dictionary=True)

        data = request.form
        print("📋 Datos recibidos del formulario:", dict(data))

        incidente_id = data.get('id')
        if not incidente_id:
            return jsonify(success=False, error="Falta el ID del incidente"), 400

        rol = session.get('rol')
        print(f"🧠 Rol del usuario actual: {rol}")

        # ---------------------------
        # Campos editables por rol
        # ---------------------------
        campos_incidentes_super = [
            'nit_empresa', 'tipo', 'clasificacion', 'fecha', 'hora',
            'lugar', 'area', 'descripcion', 'causas', 'acciones_inmediatas',
            'estado', 'severidad', 'responsable_investigacion_id'
        ]

        campos_incidentes_admin_empresa = [
            'lugar', 'area', 'descripcion', 'causas', 'acciones_inmediatas',
            'estado', 'severidad', 'responsable_investigacion_id'
        ]

        campos_personal = [
            'tipo_afectacion', 'descripcion_afectacion',
            'requirio_atencion', 'tipo_atencion'
        ]

        # Determinar qué campos se pueden actualizar según el rol
        # Para incidentes
        campos_permitidos = campos_incidentes_super if rol == "Super Administrador" else campos_incidentes_admin_empresa

        # Para incidentes_personal
        campos_permitidos_personal = campos_personal if rol == "Super Administrador" else []

        # Construcción de UPDATE
        updates = []
        values = []
        for campo in campos_permitidos:
            if campo in data:
                updates.append(f"{campo} = %s")
                values.append(data.get(campo))

        if updates:
            query = f"UPDATE incidentes SET {', '.join(updates)} WHERE id = %s"
            values.append(incidente_id)
            print("🔧 Ejecutando query incidentes:", query, values)
            cursor.execute(query, values)
            conexion.commit()
            print("✅ Cambios guardados en incidentes")

        # ---------------------------
        # Actualizar incidentes_personal
        # ---------------------------
        updates_p = []
        values_p = []
        for campo in campos_permitidos_personal:
            if campo in data:
                updates_p.append(f"{campo} = %s")
                values_p.append(data.get(campo))

        if updates_p:
            query_p = f"UPDATE incidentes_personal SET {', '.join(updates_p)} WHERE incidente_id = %s"
            values_p.append(incidente_id)
            print("🔧 Ejecutando query incidentes_personal:", query_p, values_p)
            cursor.execute(query_p, values_p)
            conexion.commit()
            print("✅ Cambios guardados en incidentes_personal")

        return jsonify(success=True, mensaje="Incidente actualizado correctamente")

    except Exception as e:
        if conexion:
            conexion.rollback()
        print("❌ Error:", str(e))
        return jsonify(success=False, error=f"Error al actualizar: {str(e)}"), 500

    finally:
        if cursor: cursor.close()
        if conexion: conexion.close()


@incidentes_bp.route("/eliminar_incidente", methods=["POST"])
@requiere_roles("Super Administrador") 
def eliminar_incidente():
    print("🗑️ Solicitud para eliminar incidente recibida")

    conexion = None
    cursor = None

    try:
        incidente_id = request.form.get("id")
        if not incidente_id:
            return jsonify(success=False, error="No se recibió el ID del incidente"), 400

        conexion = get_db()
        cursor = conexion.cursor()

        # Primero elimina del detalle (incidentes_personal)
        cursor.execute("DELETE FROM incidentes_personal WHERE incidente_id = %s", (incidente_id,))
        conexion.commit()
        print("✅ Registro relacionado eliminado de incidentes_personal")

        # Luego elimina el incidente principal
        cursor.execute("DELETE FROM incidentes WHERE id = %s", (incidente_id,))
        conexion.commit()
        print("✅ Incidente eliminado correctamente")

        return jsonify(success=True, mensaje="Incidente eliminado correctamente")

    except Exception as e:
        if conexion:
            conexion.rollback()
        print("❌ Error al eliminar incidente:", str(e))
        return jsonify(success=False, error=f"Error al eliminar: {str(e)}"), 500

    finally:
        if cursor: cursor.close()
        if conexion: conexion.close()

@incidentes_bp.route('/api/ver_incidente/<int:incidente_id>', methods=['GET'])
def api_ver_incidente(incidente_id):
    """Devuelve todos los datos de un incidente para el modal en JSON"""
    try:
        conexion = get_db()
        cursor = conexion.cursor(dictionary=True)

        # Datos principales del incidente
        cursor.execute("""
            SELECT i.id, i.nit_empresa, i.tipo, i.clasificacion, i.fecha, i.hora,
                   i.lugar, i.area, i.estado, i.severidad, i.descripcion, i.causas,
                   i.acciones_inmediatas, i.responsable_investigacion_id,
                   e.nombre AS empresa
            FROM incidentes i
            JOIN empresas e ON i.nit_empresa = e.nit_empresa
            WHERE i.id = %s
        """, (incidente_id,))
        incidente = cursor.fetchone()

        if not incidente:
            return jsonify({'error': 'Incidente no encontrado'}), 404

        # Detalle del personal involucrado
        cursor.execute("""
            SELECT tipo_afectacion, descripcion_afectacion, requirio_atencion, tipo_atencion
            FROM incidentes_personal
            WHERE incidente_id = %s
        """, (incidente_id,))
        personal = cursor.fetchall()

        cursor.close()
        conexion.close()

        return jsonify({
            'incidente': incidente,
            'personal': personal
        }), 200

    except Exception as e:
        print(f"❌ Error en API ver_incidente: {e}")
        return jsonify({'error': str(e)}), 500

