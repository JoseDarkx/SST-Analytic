from flask import render_template, request, redirect, url_for, session, flash, jsonify, send_file
import mysql.connector
from datetime import timedelta
from utils.permisos import requiere_roles
from .routes import capacitaciones_bp

def format_timedelta(td):
    """Convierte un objeto timedelta en string HH:MM."""
    if isinstance(td, timedelta):
        total_seconds = int(td.total_seconds())
        horas, resto = divmod(total_seconds, 3600)
        minutos, _ = divmod(resto, 60)
        return f"{horas:02}:{minutos:02}"
    return td


#------------------------------
# RUTAS PARA EVALUACIONES DE CAPACITACIÓN
#------------------------------

@capacitaciones_bp.route('/evaluaciones', methods=['GET'])
def evaluacion_capacitacion():
    """Mostrar evaluaciones de capacitación filtradas por empresa, capacitación y búsqueda."""
    print(">>> Entrando a la ruta /capacitaciones/evaluaciones")

    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    capacitacion_id = request.args.get('capacitacion_id')

    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="gestussg"
        )
        cursor = connection.cursor(dictionary=True, buffered=True)

        # Usuario actual
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

        rol_usuario = usuario_actual['rol']
        nit_usuario = usuario_actual['nit_empresa']

        pagina_actual = int(request.args.get('pagina', 1))
        por_pagina = 10
        offset = (pagina_actual - 1) * por_pagina
        busqueda = request.args.get('busqueda', '').strip()

        base_query = (
            " FROM evaluaciones_capacitacion ec "
            "JOIN capacitaciones c ON ec.capacitacion_id = c.id "
            "JOIN empresas e ON c.nit_empresa = e.nit_empresa "
            "LEFT JOIN usuarios u ON c.responsable_id = u.id "
            "WHERE 1=1"
        )
        params = []

        if rol_usuario != "Super Administrador":
            base_query += " AND c.nit_empresa = %s"
            params.append(nit_usuario)

        if capacitacion_id:
            base_query += " AND ec.capacitacion_id = %s"
            params.append(capacitacion_id)

        if busqueda:
            base_query += " AND ec.participante LIKE %s"
            params.append(f"%{busqueda}%")

        count_query = f"SELECT COUNT(*) AS total {base_query}"
        cursor.execute(count_query, params)
        total_registros = cursor.fetchone()['total']
        total_paginas = (total_registros + por_pagina - 1) // por_pagina

        data_query = (
            "SELECT ec.*, c.id AS capacitacion_id_obj, c.tema, c.fecha, c.hora, c.nit_empresa, c.estado AS capacitacion_estado, "
            "e.nombre AS nombre_empresa, u.nombre_completo AS responsable "
            f"{base_query} "
            "ORDER BY ec.participante ASC "
            "LIMIT %s OFFSET %s"
        )
        data_params = params + [por_pagina, offset]
        cursor.execute(data_query, data_params)
        evaluaciones_list = cursor.fetchall()

        # Capacitaciones disponibles
        if rol_usuario == "Super Administrador":
            # CORRECCIÓN: quitar las comillas alrededor de la columna fecha
            cursor.execute("SELECT id, tema, fecha, nit_empresa FROM capacitaciones ORDER BY fecha DESC")
        else:
            cursor.execute("""
                SELECT id, tema, fecha ,nit_empresa 
                FROM capacitaciones 
                WHERE nit_empresa = %s
                ORDER BY fecha DESC
            """, (nit_usuario,))
        capacitaciones_list = cursor.fetchall()

        # Empresas
        cursor.execute("SELECT nombre, nit_empresa FROM empresas ORDER BY nombre ASC")
        empresas = cursor.fetchall()
        
        from datetime import datetime

        for cap in capacitaciones_list:
            if isinstance(cap['fecha'], str):
                try:
                    cap['fecha'] = datetime.strptime(cap['fecha'], '%Y-%m-%d')
                except ValueError:
                    pass

        return render_template(
            'evaluacion_capacitacion.html',
            evaluaciones=evaluaciones_list,
            usuario_actual=usuario_actual,
            rol=usuario_actual['rol'],
            capacitacion_id=capacitacion_id,
            total_paginas=total_paginas,
            pagina_actual=pagina_actual,
            busqueda=busqueda,
            empresas=empresas,
            capacitaciones=capacitaciones_list
        )

    except mysql.connector.Error as e:
        print("⚠️ ERROR SQL EN /capacitaciones/evaluaciones >>>", e)
        flash("Error al obtener las evaluaciones de capacitación", "danger")
        # 🔹 Redirige correctamente a la vista de evaluaciones
        return redirect(url_for('capacitaciones.capacitaciones'))

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()



@capacitaciones_bp.route('/subir_evaluaciones', methods=['POST'])
@requiere_roles("Super Administrador", "Administrador")
def subir_evaluaciones():
    """Subir archivo Excel con evaluaciones y guardarlas en la BD"""
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    capacitacion_id = request.form.get("capacitacion_id")


    if not capacitacion_id:
        flash("Debe seleccionar una capacitación.", "danger")
        return redirect(url_for('capacitaciones.capacitaciones'))

    archivo = request.files.get('archivo_excel')

    if not archivo or archivo.filename == '':
        flash("Debes seleccionar un archivo Excel (.xlsx o .xls)", "warning")
        return redirect(url_for('capacitaciones.capacitaciones'))

    if not archivo.filename.endswith(('.xlsx', '.xls')):
        flash("Formato no permitido. Solo se aceptan archivos Excel (.xlsx o .xls)", "danger")
        return redirect(url_for('capacitaciones.capacitaciones'))

    import pandas as pd
    import io
    from decimal import Decimal

    # 🔹 MAPEO DE RESULTADOS PERMITIDOS
    mapa_resultados = {
        'aprobado': 'Aprobado',
        'aprobada': 'Aprobado',
        'ok': 'Aprobado',

        'no aprobado': 'No aprobado',
        'no aprobo': 'No aprobado',
        'reprobado': 'No aprobado',
        'reprobada': 'No aprobado',

        'requiere': 'Requiere',
        'necesita apoyo': 'Requiere',
        'requiere apoyo': 'Requiere'
    }

    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="gestussg"
        )
        cursor = connection.cursor()
        

        df = pd.read_excel(io.BytesIO(archivo.read()))
        df.columns = [c.strip().lower() for c in df.columns]

        columnas_necesarias = {'participante', 'pre_test', 'post_test', 'resultado', 'observaciones'}
        if not columnas_necesarias.issubset(df.columns):
            flash("❌ El archivo Excel no tiene las columnas requeridas.", "danger")
            return redirect(url_for('capacitaciones.capacitaciones'))

        for _, fila in df.iterrows():
            participante = str(fila.get('participante', '')).strip()
            pre_test = Decimal(fila.get('pre_test')) if pd.notna(fila.get('pre_test')) else None
            post_test = Decimal(fila.get('post_test')) if pd.notna(fila.get('post_test')) else None
            
            # 🔹 Normalizar resultado
            resultado_raw = str(fila.get('resultado', '')).strip().lower()
            resultado = mapa_resultados.get(resultado_raw)

            if not resultado:
                flash(f"⚠️ El valor '{fila.get('resultado')}' no es válido para 'resultado'. Use: Aprobado, No aprobado o Requiere.", "danger")
                return redirect(url_for('capacitaciones.capacitaciones'))

            observaciones = str(fila.get('observaciones', '')).strip()

            if not participante:
                continue

            cursor.execute("""
                INSERT INTO evaluaciones_capacitacion (
                    capacitacion_id, participante, pre_test, post_test, resultado, observaciones, fecha_evaluacion
                ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """, (
                capacitacion_id, participante, pre_test, post_test, resultado, observaciones
            ))

        connection.commit()
        flash("Evaluaciones cargadas correctamente desde Excel.", "success")

    except Exception as e:
        print(f">>> ERROR al subir evaluaciones: {e}")
        flash("Error al procesar el archivo Excel.", "danger")

    finally:
        if 'cursor' in locals(): cursor.close()
        if 'connection' in locals(): connection.close()

    return redirect(url_for('capacitaciones.capacitaciones'))


@capacitaciones_bp.route('/editar_evaluacion/<int:evaluacion_id>', methods=['GET', 'POST'])
def editar_evaluacion(evaluacion_id):
    """Editar evaluación de capacitación"""
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    try:
        print(f">>> Entró al endpoint /editar_evaluacion/{evaluacion_id}")

        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="gestussg"
        )
        cursor = connection.cursor(dictionary=True)
        print(">>> Conexión establecida con la BD")

        if request.method == 'POST':
            participante = request.form['participante']
            pre_test = request.form['pre_test']
            post_test = request.form['post_test']
            observaciones = request.form.get('observaciones', '')

            print(">>> Datos recibidos:", participante, pre_test, post_test, observaciones)

            pre_test_num = float(pre_test) if pre_test else None
            post_test_num = float(post_test) if post_test else 0

            if post_test_num >= 70:
                resultado = 'Aprobado'
            elif post_test_num >= 60:
                resultado = 'Requiere'
            else:
                resultado = 'No aprobado'

            print(f">>> Resultado calculado: {resultado}")

            cursor.execute("""
                UPDATE evaluaciones_capacitacion 
                SET participante = %s, pre_test = %s, post_test = %s, resultado = %s, observaciones = %s
                WHERE id = %s
            """, (participante, pre_test_num, post_test_num, resultado, observaciones, evaluacion_id))

            connection.commit()
            print(">>> Evaluación actualizada en la BD")

            flash('Evaluación actualizada exitosamente', 'success')
            return redirect(url_for('capacitaciones.capacitaciones'))

        else:
            cursor.execute("SELECT * FROM evaluaciones_capacitacion WHERE id = %s", (evaluacion_id,))
            evaluacion = cursor.fetchone()

            if not evaluacion:
                flash('Evaluación no encontrada', 'error')
                return redirect(url_for('capacitaciones.capacitaciones'))

            return render_template('editar_evaluacion.html', evaluacion=evaluacion)

    except mysql.connector.Error as e:
        print(f">>> ERROR al editar evaluación: {e}")
        flash('Error al editar la evaluación', 'error')
        return redirect(url_for('capacitaciones.capacitaciones'))

    finally:
        if 'cursor' in locals():
            cursor.close()
            print(">>> Cursor cerrado")
        if 'connection' in locals():
            connection.close()
            print(">>> Conexión cerrada")