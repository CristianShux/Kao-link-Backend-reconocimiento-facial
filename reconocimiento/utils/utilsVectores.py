import json
import os
import numpy as np
from crud.database import db
from reconocimiento.utils.cifrado import cifrar_vector, descifrar_vector

# Configuración
UMBRAL = 0.5
CARPETA_VECTORES = "vectores"
os.makedirs(CARPETA_VECTORES, exist_ok=True)


TIPO_MAP = {
    "normal": "Neutro",
    "sonrisa": "Sonrisa",
    "giro": "Giro"
}


#ESTA VERSION ES LA QUE ANDABA



def guardar_vector(id_empleado: int, tipo_gesto_raw: str, vector_np):
    """
    Guarda un vector biométrico cifrado en la base de datos.
    Si ya existe para ese id_empleado y tipo_vector, lo actualiza.
    """
    tipo_vector_db = TIPO_MAP.get(tipo_gesto_raw.lower())

    if tipo_vector_db is None:
        print(f"❌ Error (guardar_vector): Tipo de gesto desconocido '{tipo_gesto_raw}'.")
        return False

    try:
        conn = db.get_connection()
        cur = conn.cursor()

        vector_cifrado = cifrar_vector(vector_np)  # Cifrado aquí

        query = """
            INSERT INTO dato_biometrico_facial (id_empleado, tipo_vector, vector_biometrico)
            VALUES (%s, %s, %s)
            ON CONFLICT (id_empleado, tipo_vector) DO UPDATE
            SET vector_biometrico = EXCLUDED.vector_biometrico
        """
        cur.execute(query, (id_empleado, tipo_vector_db, vector_cifrado))
        conn.commit()
        print(f"✅ Vector '{tipo_vector_db}' cifrado y guardado para empleado {id_empleado}")
        return True

    except Exception as e:
        print(f"❌ Error al guardar/actualizar vector cifrado: {e}")
        return False

    finally:
        cur.close()
        db.return_connection(conn)

def obtener_vector(id_empleado: int, tipo_gesto_raw: str):
    tipo_vector_db = TIPO_MAP.get(tipo_gesto_raw.lower())

    try:
        conn = db.get_connection()
        cur = conn.cursor()

        query = """
            SELECT vector_biometrico
            FROM dato_biometrico_facial
            WHERE id_empleado = %s AND tipo_vector = %s
        """
        cur.execute(query, (id_empleado, tipo_vector_db))
        row = cur.fetchone()

        if row is None:
            print("⚠️ Vector no encontrado.")
            return None

        vector_cifrado = row[0]
        vector_np = descifrar_vector(vector_cifrado)
        return vector_np

    except Exception as e:
        print(f"❌ Error al obtener/descifrar vector: {e}")
        return None

    finally:
        cur.close()
        db.return_connection(conn)

def cargar_vectores():
    """
    Carga todos los vectores biométricos de la base utilizando connection pooling.
    Devuelve un dict con la estructura:
    {
        id_empleado_1: {'neutro': vector1, 'sonrisa': vector2, ...},
        id_empleado_2: {'neutro': vector3, 'sonrisa': vector4, ...},
        ...
    }
    """
    try:
        conn = db.get_connection()
        cur = conn.cursor()

        query = """
            SELECT id_empleado, tipo_vector, vector_biometrico
            FROM dato_biometrico_facial
        """
        cur.execute(query)
        resultados = cur.fetchall()

        todos_los_vectores = {}

        for id_empleado, tipo_vector, vector_texto in resultados:
            clave_tipo = tipo_vector.lower()

            try:
                vector_list = json.loads(vector_texto)
                vector_np = np.array([float(x) for x in vector_list], dtype=np.float64)
            except Exception as e:
                print(f"⚠️ Error convirtiendo vector para {id_empleado}, tipo {tipo_vector}: {e}")
                continue

            if id_empleado not in todos_los_vectores:
                todos_los_vectores[id_empleado] = {}

            todos_los_vectores[id_empleado][clave_tipo] = vector_np

        return todos_los_vectores

    except Exception as e:
        print(f"❌ Error al cargar vectores: {e}")
        return {}

    finally:
        cur.close()
        db.return_connection(conn)

def cargar_vectores_por_tipo(tipo: str = 'neutro'):
    """
    Carga los vectores de un tipo específico (por defecto 'neutro').
    """
    try:
        conn = db.get_connection()
        cur = conn.cursor()

        query = """
            SELECT id_empleado, vector_biometrico
            FROM dato_biometrico_facial
            WHERE tipo_vector = %s
        """
        cur.execute(query, (tipo,))
        resultados = cur.fetchall()

        vectores = {}
        for id_empleado, vector_cifrado in resultados:
            try:
                vector_np = descifrar_vector(vector_cifrado)
                vectores[id_empleado] = vector_np
            except Exception as e:
                print(f"⚠️ Error descifrando vector de {id_empleado}: {e}")
                continue

        return vectores

    except Exception as e:
        print(f"❌ Error al cargar vectores: {e}")
        return {}

    finally:
        cur.close()
        db.return_connection(conn)



