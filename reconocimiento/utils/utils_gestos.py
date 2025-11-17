import dlib
import cv2
import numpy as np

import os

predictor_path = os.path.join(os.path.dirname(__file__), "shape_predictor_68_face_landmarks.dat")
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor(predictor_path)



def detectar_sonrisa(image_np):
    gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
    caras = detector(gray)

    if not caras:
        return False

    for cara in caras:
        shape = predictor(gray, cara)
        coords = np.array([[shape.part(i).x, shape.part(i).y] for i in range(68)])

        # Altura y ancho de la boca
        mouth_height = np.linalg.norm(coords[66] - coords[62])  # vertical entre labios
        mouth_width = np.linalg.norm(coords[54] - coords[48])  # horizontal boca

        # Distancia entre ojos (para normalizar)
        eye_distance = np.linalg.norm(coords[45] - coords[36])

        # Ratio normalizado
        ratio = (mouth_height / mouth_width) * (mouth_width / eye_distance)
        print(f"🙂 Smile ratio (normalizado): {ratio:.2f}")

        return ratio > 0.08  # Ajustado empíricamente

    return False




def detectar_giro(image_np):
    gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
    caras = detector(gray)

    if not caras:
        return False

    for cara in caras:
        shape = predictor(gray, cara)
        coords = np.array([[shape.part(i).x, shape.part(i).y] for i in range(68)])

        nariz = coords[30]
        ojo_izq = coords[36]
        ojo_der = coords[45]
        centro_ojos = ((ojo_izq[0] + ojo_der[0]) / 2, (ojo_izq[1] + ojo_der[1]) / 2)
        dx = nariz[0] - centro_ojos[0]

        print(f"↪️ Desplazamiento nariz vs ojos: {dx:.2f}")
        return abs(dx) > 20  # umbral más alto para evitar falsos positivos

    return False

def detectar_cejas_levantadas(image_np):
    gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
    caras = detector(gray)

    if not caras:
        return False

    for cara in caras:
        shape = predictor(gray, cara)
        coords = np.array([[shape.part(i).x, shape.part(i).y] for i in range(68)])

        # Promedios verticales
        ceja_izq_y = np.mean(coords[17:22, 1])  # ceja izquierda
        ojo_izq_y = np.mean(coords[36:42, 1])   # ojo izquierdo

        # Distancia normalizada
        distancia_ceja_ojo = ojo_izq_y - ceja_izq_y
        eye_distance = np.linalg.norm(coords[45] - coords[36])
        ratio = distancia_ceja_ojo / eye_distance

        print(f"👀 Ceja-ojo ratio: {ratio:.2f}")
        return ratio > 0.30  # Ajustar según pruebas

    return False

