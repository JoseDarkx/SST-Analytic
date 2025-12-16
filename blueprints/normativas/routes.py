from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from extensions import get_db
from utils.permisos import requiere_roles
from datetime import datetime
import mysql.connector

normativas_bp = Blueprint('normativas', __name__, url_prefix='/normativas')

def conectar_bd():
    return get_db()  # 🔄 Conexión centralizada

@normativas_bp.route('/')
def listar_normativas():
    # Obtener datos del usuario logueado
    conexion = conectar_bd()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("""
        SELECT u.nombre_completo, r.nombre AS rol
        FROM usuarios u
        JOIN roles r ON u.rol_id = r.id
        WHERE u.id = %s
    """, (session['usuario_id'],))
    usuario = cursor.fetchone()

    cursor.execute("SELECT * FROM normativas ORDER BY id DESC")
    normativas = cursor.fetchall()
    cursor.close()
    conexion.close()
    return render_template('listar_normas.html', normativas=normativas, usuario_actual=usuario)

# agregar normativa

@normativas_bp.route('/agregar', methods=['GET', 'POST'])
@requiere_roles("Super Administrador", "Administrador")
def agregar_normativa():
    if request.method == 'POST':
        nombre = request.form['nombre']
        tipo = request.form['tipo']
        descripcion = request.form['descripcion']
        url_oficial = request.form['url_oficial']

        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            INSERT INTO normativas (nombre, tipo, descripcion, url_oficial)
            VALUES (%s, %s, %s, %s)
        """, (nombre, tipo, descripcion, url_oficial))
        conexion.commit()
        cursor.close()
        conexion.close()
        flash('✅ Normativa registrada correctamente', 'success')
        return redirect(url_for('normativas.listar_normativas'))

    return render_template('agregar_normas.html')

#ver normativa

@normativas_bp.route('/<int:id_normativa>')
def ver_normativa(id_normativa):
    conexion = conectar_bd()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT * FROM normativas WHERE id = %s", (id_normativa,))
    normativa = cursor.fetchone()
    cursor.close()
    conexion.close()
    return render_template('ver_normas.html', normativa=normativa)



@normativas_bp.route('/editar/<int:id_normativa>', methods=['GET', 'POST'])
@requiere_roles("Super Administrador", "Administrador")
def editar_normativa(id_normativa):
    conexion = conectar_bd()
    cursor = conexion.cursor(dictionary=True)

    try:
        # Obtener datos actuales de la normativa
        cursor.execute("SELECT * FROM normativas WHERE id = %s", (id_normativa,))
        normativa = cursor.fetchone()

        if not normativa:
            flash('⚠️ Normativa no encontrada', 'danger')
            return redirect(url_for('normativas.listar_normativas'))

        rol = session.get('rol')

        if request.method == 'POST':
            data = request.form
            print("📋 Datos recibidos:", dict(data))
            
            # ---------------------------
            # Campos editables según rol
            # ---------------------------
            campos_super = ['titulo', 'descripcion', 'url_oficial']
            campos_admin = ['url_oficial']

            campos_permitidos = campos_super if rol == "Super Administrador" else campos_admin

            # Construcción de UPDATE dinámico
            updates = []
            values = []

            for campo in campos_permitidos:
                if campo in data:
                    updates.append(f"{campo} = %s")
                    values.append(data.get(campo))

            # Fecha de actualización solo si es super admin
            #if rol == "Super Administrador":
            #    fecha_actualizacion = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            #    updates.append("fecha_actualizacion = %s")
            #    values.append(fecha_actualizacion)

            if updates:
                query = f"UPDATE normativas SET {', '.join(updates)} WHERE id = %s"
                values.append(id_normativa)
                print("🔧 Ejecutando query:", query, values)
                cursor.execute(query, values)
                conexion.commit()
                flash('✅ Normativa actualizada correctamente', 'success')
            else:
                flash('⚠️ No hay campos permitidos para actualizar', 'warning')

            return redirect(url_for('normativas.listar_normativas'))

        # GET -> renderizar formulario
        return render_template('editar_normas.html', normativa=normativa)

    except Exception as e:
        conexion.rollback()
        print("❌ Error al editar normativa:", str(e))
        flash('❌ Error al actualizar normativa', 'danger')
        return redirect(url_for('normativas.listar_normativas'))

    finally:
        cursor.close()
        conexion.close()


@normativas_bp.route('/api/normativas/<int:id_normativa>')
def obtener_normativa_api(id_normativa):
    conexion = conectar_bd()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT * FROM normativas WHERE id = %s", (id_normativa,))
    normativa = cursor.fetchone()
    cursor.close()
    conexion.close()

    if not normativa:
        return jsonify({"error": "Normativa no encontrada"}), 404

    return jsonify(normativa)


