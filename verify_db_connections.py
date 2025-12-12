import os
from database import get_connection
import re

# Directorio base del proyecto
BASE_DIR = os.getcwd()

# Patrones a buscar
patterns = {
    "mysql.connector.connect": re.compile(r"mysql\.connector\.connect"),
    "localhost": re.compile(r"['\"]localhost['\"]"),
    "root_user": re.compile(r"user\s*=\s*['\"]root['\"]"),
    "gestussg_db": re.compile(r"['\"]gestussg['\"]"),
}

def analyze_file(path):
    report = []
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for i, line in enumerate(lines, start=1):
        for key, pat in patterns.items():
            if pat.search(line):
                report.append((i, key, line.strip()))
    return report


def start_verification():
    print("🔍 Analizando archivos .py para verificar conexiones antiguas...\n")
    
    total_matches = 0
    results = {}

    for root, dirs, files in os.walk(BASE_DIR):
        for filename in files:
            if filename.endswith(".py") and filename not in ("fix_db_connections.py", "verify_db_connections.py"):
                path = os.path.join(root, filename)
                report = analyze_file(path)

                if report:
                    results[path] = report
                    total_matches += len(report)

    if total_matches == 0:
        print("🎉 TODO LISTO: No existe ninguna conexión antigua restante.")
        return

    print(f"⚠️ Se encontraron {total_matches} coincidencias sospechosas.\n")
    for filepath, issues in results.items():
        print(f"📁 Archivo: {filepath}")
        for line, key, text in issues:
            print(f"   • Línea {line:3} | {key:20} → {text}")
        print()

    print("📌 Revisa estos archivos. Puedo ayudarte a corregirlos si me envías el listado.")


if __name__ == "__main__":
    start_verification()
