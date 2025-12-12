import os
import re

BASE_DIR = os.getcwd()

# Detecta conexiones mysql directas
pattern_connect = re.compile(
    r'mysql\.connector\.connect\s*\(([^)]*)\)',
    re.DOTALL
)

def fix_file(path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    if "mysql.connector.connect" not in content:
        return False

    print(f"✔ Corrigiendo: {path}")

    # Reemplazar SOLO la conexión
    new_content = pattern_connect.sub("get_connection()", content)

    # Insertar import correcto si no existe
    if "from database import get_connection" not in new_content:
        new_content = re.sub(
            r"^(import .+\n|from .+\n)",
            r"\1from database import get_connection\n",
            new_content,
            count=1
        )

    # Guardar cambios
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return True


def start_fix():
    print("🔍 Buscando archivos .py...")
    changed_files = []

    for root, dirs, files in os.walk(BASE_DIR):
        for filename in files:
            if filename.endswith(".py") and filename != "fix_db_connections.py":
                path = os.path.join(root, filename)
                if fix_file(path):
                    changed_files.append(path)

    print("\n🎉 Completado.")
    print(f"📝 Archivos modificados: {len(changed_files)}")
    for f in changed_files:
        print(" ➤", f)


if __name__ == "__main__":
    start_fix()
