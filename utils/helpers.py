import json
import os

def guardar_json(ruta_archivo, data):
    """
    Guarda un diccionario/lista en un archivo JSON.
    Crea las carpetas necesarias si no existen.
    """
    # Crear carpeta si no existe
    os.makedirs(os.path.dirname(ruta_archivo), exist_ok=True)

    with open(ruta_archivo, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    return True
