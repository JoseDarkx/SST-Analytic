from flask import render_template, redirect, url_for, session, flash, jsonify, send_file
import mysql.connector
from datetime import timedelta
from .routes import capacitaciones_bp
def format_timedelta(td):
    """Convierte un objeto timedelta en string HH:MM."""
    if isinstance(td, timedelta):
        total_seconds = int(td.total_seconds())
        horas, resto = divmod(total_seconds, 3600)
        minutos, _ = divmod(resto, 60)
        return f"{horas:02}:{minutos:02}"
    return td




@capacitaciones_bp.route('/capacitaciones_por_empresa/<nit_empresa>')
def capacitaciones_por_empresa(nit_empresa):
    """Devuelve las capacitaciones de una empresa que aún no tienen evaluación"""
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="gestussg"
        )
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT c.id, c.tema, c.fecha 
            FROM capacitaciones c
            WHERE c.nit_empresa = %s
            AND c.id NOT IN (
                SELECT DISTINCT capacitacion_id FROM evaluaciones_capacitacion
            )
            ORDER BY c.fecha DESC
        """, (nit_empresa,))

        capacitaciones = cursor.fetchall()
        return jsonify(capacitaciones)

    except mysql.connector.Error as e:
        print(f"⚠️ Error al obtener capacitaciones: {e}")
        return jsonify({"error": "Error al obtener capacitaciones"}), 500

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()


@capacitaciones_bp.route('/capacitaciones_pendientes/<nit_empresa>')
def capacitaciones_pendientes(nit_empresa):
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="gestussg"
        )
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT c.id, c.tema, DATE_FORMAT(c.fecha, '%d/%m/%Y') AS fecha
            FROM capacitaciones c
            WHERE c.nit_empresa = %s
            AND c.id NOT IN (SELECT DISTINCT capacitacion_id FROM evaluaciones_capacitacion)
            ORDER BY c.fecha DESC
        """, (nit_empresa,))

        capacitaciones = cursor.fetchall()
        return jsonify(capacitaciones)

    except mysql.connector.Error as e:
        print(f"⚠️ Error al obtener capacitaciones pendientes: {e}")
        return jsonify({"error": str(e)}), 500  # 👈 devuelve el error real al front

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()



@capacitaciones_bp.route('/reporte_capacitaciones')
def reporte_capacitaciones():
    """Vista del reporte de efectividad de capacitaciones"""
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))

    try:
        import mysql.connector

        # Conexión a base de datos
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="gestussg"
        )
        cursor = connection.cursor(dictionary=True)

        # Consulta de evaluaciones con sus resultados
        query = """
            SELECT ec.id, ec.participante, ec.resultado, 
                   c.tema, c.fecha, e.nombre AS empresa
            FROM evaluaciones_capacitacion ec
            JOIN capacitaciones c ON ec.capacitacion_id = c.id
            JOIN empresas e ON c.nit_empresa = e.nit_empresa
            ORDER BY c.fecha DESC
        """
        cursor.execute(query)
        evaluaciones = cursor.fetchall()

        print(f"✅ Evaluaciones recuperadas: {len(evaluaciones)}")
        return render_template('reporte.html', evaluaciones=evaluaciones)

    except Exception as e:
        print(f"❌ Error al cargar el reporte: {e}")
        # Mostrar mensaje genérico al usuario; detalles en el log
        flash('Error al cargar el reporte', 'danger')
        return redirect(url_for('capacitaciones.capacitaciones'))

    finally:
        if 'connection' in locals():
            connection.close()
            print("🔌 Conexión a BD cerrada.")



@capacitaciones_bp.route('/reporte_capacitaciones_pdf')
def reporte_capacitaciones_pdf():
    """Exportar reporte PDF de capacitaciones"""
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))
    
    try:
        from flask import send_file
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        import io
        import mysql.connector

        print("📡 Conectando a la base de datos...")
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="gestussg"
        )
        cursor = connection.cursor(dictionary=True)

        print("📋 Ejecutando query principal de capacitaciones...")
        query = """
            SELECT c.fecha, e.nombre as empresa, u.nombre_completo as responsable, c.estado,
            COUNT(ec.id) as total_evaluaciones,
            SUM(CASE WHEN ec.resultado = 'Aprobado' THEN 1 ELSE 0 END) as aprobados,
            ROUND((SUM(CASE WHEN ec.resultado = 'Aprobado' THEN 1 ELSE 0 END) / 
                    GREATEST(COUNT(ec.id), 1)) * 100, 2) as efectividad_porcentaje
        FROM capacitaciones c
        JOIN empresas e ON c.nit_empresa = e.nit_empresa
        JOIN usuarios u ON c.responsable_id = u.id
        LEFT JOIN evaluaciones_capacitacion ec ON c.id = ec.capacitacion_id
        GROUP BY c.id, c.fecha, e.nombre, u.nombre_completo, c.estado
        ORDER BY c.fecha DESC
        """
        cursor.execute(query)
        capacitaciones = cursor.fetchall()
        print(f"✅ Capacitaciones obtenidas: {len(capacitaciones)}")

        # Crear PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []

        styles = getSampleStyleSheet()
        elements.append(Paragraph("Reporte de Capacitaciones", styles['Title']))
        elements.append(Spacer(1, 12))

        data = [['Fecha', 'Empresa', 'Responsable', 'Estado', 'Evaluaciones', 'Aprobados', 'Efectividad']]
        
        for cap in capacitaciones:
            print(f"➡️ Procesando fila: {cap}")
            data.append([
                str(cap['fecha']) if cap['fecha'] else '',
                cap['empresa'],
                cap['responsable'],
                cap['estado'],
                str(cap['total_evaluaciones']),
                str(cap['aprobados']),
                f"{cap['efectividad_porcentaje']}%"
            ])

        print("🖨️ Construyendo tabla PDF...")
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        elements.append(table)
        doc.build(elements)

        buffer.seek(0)
        print("✅ PDF generado correctamente, enviando archivo...")
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='reporte_capacitaciones.pdf'
        )
        
    except Exception as e:
        print(f"❌ Error al generar PDF: {e}")
        flash('Error al generar el reporte PDF', 'error')
        return redirect(url_for('capacitaciones.capacitaciones'))
    finally:
        if 'connection' in locals():
            connection.close()
            print("🔌 Conexión a BD cerrada.")


@capacitaciones_bp.route('/reporte_capacitaciones_excel')
def reporte_capacitaciones_excel():
    """Exportar reporte Excel de capacitaciones"""
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('auth.iniciar_sesion'))
    
    try:
        import pandas as pd
        from io import BytesIO
        import mysql.connector

        print("📡 Conectando a la base de datos...")
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="gestussg"
        )

        query = """
            SELECT c.fecha, e.nombre as empresa, u.nombre_completo as responsable, c.estado,
            COUNT(ec.id) as total_evaluaciones,
            SUM(CASE WHEN ec.resultado = 'Aprobado' THEN 1 ELSE 0 END) as aprobados,
            ROUND((SUM(CASE WHEN ec.resultado = 'Aprobado' THEN 1 ELSE 0 END) / 
                    GREATEST(COUNT(ec.id), 1)) * 100, 2) as efectividad_porcentaje
        FROM capacitaciones c
        JOIN empresas e ON c.nit_empresa = e.nit_empresa
        JOIN usuarios u ON c.responsable_id = u.id
        LEFT JOIN evaluaciones_capacitacion ec ON c.id = ec.capacitacion_id
        GROUP BY c.id, c.fecha, e.nombre, u.nombre_completo, c.estado
        ORDER BY c.fecha DESC
        """
        print("📋 Ejecutando query principal...")
        df = pd.read_sql(query, connection)
        print(f"✅ Filas recuperadas: {len(df)}")

        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Capacitaciones', index=False)

            query_evaluaciones = """
                SELECT c.fecha as fecha_capacitacion, e.nombre as empresa, 
                    ec.participante, ec.pre_test, ec.post_test, ec.resultado
                FROM evaluaciones_capacitacion ec
                JOIN capacitaciones c ON ec.capacitacion_id = c.id
                JOIN empresas e ON c.nit_empresa = e.nit_empresa
                ORDER BY c.fecha DESC, ec.participante
            """
            print("📋 Ejecutando query detalle de evaluaciones...")
            df_evaluaciones = pd.read_sql(query_evaluaciones, connection)
            print(f"✅ Evaluaciones recuperadas: {len(df_evaluaciones)}")

            df_evaluaciones.to_excel(writer, sheet_name='Evaluaciones_Detalle', index=False)

        buffer.seek(0)
        print("✅ Excel generado correctamente, enviando archivo...")
        return send_file(
            BytesIO(buffer.read()),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='reporte_capacitaciones.xlsx'
        )
        
    except Exception as e:
        print(f"❌ Error al generar Excel: {e}")
        flash('Error al generar el reporte Excel', 'error')
        return redirect(url_for('capacitaciones.capacitaciones'))
    finally:
        if 'connection' in locals():
            connection.close()
            print("🔌 Conexión a BD cerrada.")


# Agregar también estas rutas AJAX para mejorar la experiencia de usuario

@capacitaciones_bp.route('/api/capacitaciones', methods=['GET'])
def api_capacitaciones():
    """API para obtener todas las capacitaciones con logs en consola"""
    print("➡️ Entrando a /api/capacitaciones")  # Log inicial
    
    try:
        # Conexión a la BD
        connection = mysql.connector.connect(
            host="localhost",
            user="root", 
            password="",
            database="gestussg"
        )
        cursor = connection.cursor(dictionary=True)
        
        # Consultar todas las capacitaciones
        cursor.execute("""
            SELECT id, nit_empresa, fecha, responsable_id, tema, estado
            FROM capacitaciones
            ORDER BY fecha DESC
        """)
        
        capacitaciones = cursor.fetchall()

        # 🔎 Logs en consola
        print(f"📚 Capacitaciones encontradas: {len(capacitaciones)}")
        for cap in capacitaciones[:10]:  # solo mostramos las 10 primeras
            print(f" - ID:{cap['id']} | Empresa:{cap['nit_empresa']} | "
                f"Tema:{cap['tema']} | Estado:{cap['estado']} | Responsable:{cap['responsable_id']}")

        # Si no hay capacitaciones registradas
        if not capacitaciones:
            print("ℹ️ No hay capacitaciones registradas en la base de datos")
            return jsonify({'capacitaciones': [], 'mensaje': 'No hay capacitaciones registradas'}), 200
        
        # Respuesta exitosa
        return jsonify({'capacitaciones': capacitaciones}), 200

    except mysql.connector.Error as e:
        print(f"❌ Error en /api/capacitaciones: {e}")
        flash("Error en la api capacitaciones")
        return jsonify({'error': str(e)}), 500
    
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

@capacitaciones_bp.route('/api/capacitaciones/<int:capacitacion_id>/evaluaciones')
def api_evaluaciones_capacitacion(capacitacion_id):
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root", 
            password="",
            database="gestussg"
        )
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT capacitacion_id, participante, pre_test, post_test
            FROM evaluaciones_capacitacion
            WHERE capacitacion_id = %s
        """, (capacitacion_id,))
        data = cursor.fetchall()
        return jsonify(data)
    except Exception as err:
        print("❌ Error al obtener evaluaciones:", err)
        return jsonify({"error": str(err)}), 500