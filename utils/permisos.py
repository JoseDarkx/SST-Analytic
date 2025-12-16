from functools import wraps
from flask import session, redirect, url_for, flash, current_app, g
from extensions import get_db

# --- Ajusta los nombres exactos de roles si en tu BD varían ---
# Mapa para evitar errores por mayúsculas/minúsculas al comparar
ROLES_VALIDOS = {
    "Super Administrador": "Super Administrador",
    "Administrador Empresa": "Administrador de la Empresa",
    "Representante Legal": "Representante Legal",
    "Auditor": "Auditor",
    "Vigia": "Vigia",
    "Copasst": "COPASST"
}

def obtener_usuario_desde_session():
    """
    Devuelve diccionario con info mínima del usuario (id, rol, nit_empresa)
    - Debes asegurar en el login que session tenga: usuario_id, rol, nit_empresa (si aplica).
    - Si no, este helper intenta cargar desde BD.
    """
    usuario = {
        "id": session.get("usuario_id"),
        "rol": session.get("rol"),
        "nit_empresa": session.get("nit_empresa")  # nullable para super admin
    }

    # Si falta información importante, intentar cargar desde BD
    if not usuario["rol"] or not usuario["nit_empresa"] and usuario["id"]:
        try:
            conn = get_db()
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT u.id, u.nombre_completo, r.nombre AS rol, u.nit_empresa
                FROM usuarios u
                LEFT JOIN roles r ON u.rol_id = r.id
                WHERE u.id = %s
            """, (usuario["id"],))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row:
                usuario["rol"] = usuario["rol"] or row.get("rol")
                usuario["nit_empresa"] = usuario["nit_empresa"] or row.get("nit_empresa")
        except Exception as e:
            current_app.logger.exception("Error cargando usuario desde DB: %s", e)

    return usuario

# --------------- Decorador: login_required ---------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'usuario_id' not in session:
            flash("Debes iniciar sesión primero.", "warning")
            return redirect(url_for('auth.iniciar_sesion'))
        # Cargar usuario al g para acceso rápido
        g.usuario = obtener_usuario_desde_session()
        return f(*args, **kwargs)
    return decorated

# --------------- Decorador: requiere_roles ---------------
def requiere_roles(*roles_permitidos):
    """
    Uso: @requiere_roles('Super Administrador','Administrador de la Empresa')
    Compara role name exacto (case-sensitive según lo guardes) — aquí normalizamos.
    """
    roles_permitidos_norm = set(r.strip().lower() for r in roles_permitidos)
    def wrapper(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            usuario = obtener_usuario_desde_session()
            rol_usuario = (usuario.get('rol') or "").strip().lower()
            if rol_usuario not in roles_permitidos_norm:
                flash("No tienes permisos para realizar esta acción.", "danger")
                return redirect(url_for('auth.dashboard'))
            g.usuario = usuario
            return f(*args, **kwargs)
        return decorated
    return wrapper
