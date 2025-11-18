import numpy as np
import base64
import cv2
from io import BytesIO
from datetime import datetime
from PIL import Image
import random

from crud.crudEmpleado import RegistroHorario

from reconocimiento.service.reconocimiento import identificar_persona, identificar_gesto, buscar_mejor_match
from reconocimiento.utils.utilsVectores import guardar_vector

from fastapi.websockets import WebSocketState

# --- INICIO DE LA IMPLEMENTACIÓN DE CARGA PEREZOSA PARA face_recognition ---
_face_recognition_instance = None

def _get_face_recognition_instance():
    """
    Retorna la instancia de face_recognition, cargándola solo la primera vez.
    """
    global _face_recognition_instance
    if _face_recognition_instance is None:
        print("INFO: Cargando modelos de face_recognition por primera vez en serverReconocimiento.py. Esto puede tardar unos segundos.")
        import face_recognition # <-- ¡La importación ocurre AQUI, LA PRIMERA VEZ QUE SE LLAMA ESTA FUNCION!
        _face_recognition_instance = face_recognition
        print("INFO: Modelos de face_recognition cargados.")
    return _face_recognition_instance
# --- FIN DE LA IMPLEMENTACIÓN DE CARGA PEREZOSA ---


async def safe_send(ws, msg):
    if ws.client_state == WebSocketState.CONNECTED:
        await ws.send_text(msg)

async def registrar_empleado(websocket, data, id_empleado):
    """Registra un empleado pidiendo imágenes de a una, validando gesto por gesto."""
    fr = _get_face_recognition_instance() # Obtén la instancia de face_recognition
    gestos_requeridos = [("normal", None), ("sonrisa", "sonrisa"), ("giro", "giro")]
    vectores_guardar = {}  # Diccionario para almacenar los vectores temporales

    for tipo, gesto in gestos_requeridos:
        primer_intento = True
        while True:
            if primer_intento:
                await websocket.send_text(f"📸 Por favor, envía imagen del gesto: '{tipo}'")
                primer_intento = False  # Ya pedimos la imagen

            data_imagen = await websocket.receive_json() # Asume que el frontend envía la imagen correcta en cada loop

            try:
                image_data = base64.b64decode(data_imagen[f"imagen_{tipo}"])
                image = np.array(Image.open(BytesIO(image_data)))
                rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

                # Usa 'fr' que obtuviste de la carga perezosa
                face_encodings = fr.face_encodings(rgb_image)

                if not face_encodings:
                    await websocket.send_text(f"❌ No se detectó rostro en imagen '{tipo}', intenta de nuevo")
                    continue

                vector_actual = face_encodings[0].astype(np.float64)

                if gesto:
                    if not identificar_gesto(rgb_image, gesto):
                        await websocket.send_text(f"🚫 El gesto '{gesto}' no fue detectado correctamente, intenta de nuevo")
                        continue  # 👈 volver a pedir imagen sin mandar alerta nueva

                # ✅ Gesto validado: almacenar vector
                vectores_guardar[tipo] = vector_actual
                break  # 👉 pasar al siguiente gesto

            except Exception as e:
                await websocket.send_text(f"⚠️ Error procesando imagen '{tipo}': {e}")
                continue
    # Si todos los gestos fueron validados, guardar los vectores
    if len(vectores_guardar) == len(gestos_requeridos):
        for tipo, vector in vectores_guardar.items():
            guardar_vector(id_empleado, tipo, vector)
        await websocket.send_text(f"✅ Persona '{id_empleado}' registrada correctamente con gestos")
        print(f"✅ Persona '{id_empleado}' registrada")
    else:
        await websocket.send_text(f"❌ No se completaron todos los gestos requeridos, registro cancelado")


async def verificar_identidad(websocket, data):
    fr = _get_face_recognition_instance() # Obtén la instancia de face_recognition
    image_data = base64.b64decode(data["imagen"])
    image = np.array(Image.open(BytesIO(image_data)))
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # Usa 'fr' que obtuviste de la carga perezosa
    face_encodings = fr.face_encodings(rgb_image)

    if not face_encodings:
        await websocket.send_text("🚫 No se detectó un rostro válido")
        return

    vector = face_encodings[0].astype(np.float64)
    id_empleado, distancia = buscar_mejor_match(vector)

    if not id_empleado:
        await websocket.send_text("🚫 Persona no reconocida")
        return

    fecha_hora = datetime.fromisoformat(data["fecha_hora"])
    gesto_requerido = random.choice(["sonrisa", "giro", "cejas"])

    for intento in range(3):
        if intento == 0:  # Solo en la primera iteración se envía este mensaje
            await safe_send(websocket, f"🔄 Por favor, realiza el gesto: {gesto_requerido}")
        if intento > 0:
            await safe_send(websocket, f"🚫 Gesto incorrecto. Por favor, realiza el gesto: {gesto_requerido}")
        try:
            nueva_data = await websocket.receive_json()
        except Exception as e:
            await safe_send(websocket, f"⚠️ La conexión fue cerrada inesperadamente: {e}")
            return

        try:
            image_data_gesto = base64.b64decode(nueva_data["imagen"])
            image_gesto = np.array(Image.open(BytesIO(image_data_gesto)))
            rgb_gesto = cv2.cvtColor(image_gesto, cv2.COLOR_BGR2RGB)

            # Usa 'fr' para face_encodings_gesto
            face_encodings_gesto = fr.face_encodings(rgb_gesto)

            if not face_encodings_gesto:
                await safe_send(websocket, "❌ No se detectó rostro en la imagen del gesto")
                continue

            if not identificar_gesto(rgb_gesto, gesto_requerido): # Asumo que esto no usa face_recognition directamente
                continue

            # 🎉 Gesto válido -> registrar
            try:
                registro = RegistroHorario.registrar_asistencia(int(id_empleado), fecha_hora)
                if registro is None:
                    await safe_send(websocket, "⚠️ Entrada fuera del rango permitido.")
                    return

                await safe_send(websocket,
                    f"✅ Se registró la {registro.tipo} del empleado {id_empleado} "
                    f"a las {registro.hora.strftime('%H:%M')} del {registro.fecha.strftime('%Y-%m-%d')}"
                )
                return

            except ValueError as e:
                await safe_send(websocket, f"❌ {e}")
                return

        except Exception as e:
            await safe_send(websocket, f"⚠️ Error procesando imagen del gesto: {e}")
            return

    await safe_send(websocket, "🚫 Verificación fallida luego de 3 intentos.")