
from fastapi import FastAPI, HTTPException, WebSocket
from typing import Optional
from datetime import datetime, date, time

from pydantic import BaseModel

from reconocimiento.serverReconocimiento import registrar_empleado, verificar_identidad
from crud.database import db
from fastapi.middleware.cors import CORSMiddleware


class AsistenciaManual(BaseModel):
    id_empleado: int
    tipo: str
    fecha: date
    hora: time
    estado_asistencia: Optional[str] = None


app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:3000",  
    "http://localhost:5173",
    "https://kao-link-frontend.vercel.app"  
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite todos los orígenes
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos los métodos (GET, POST, etc.)
    allow_headers=["*"],  # Permite todos los headers
)


@app.get("/health")
def health_check():
    """
    Verifica el estado de la API y conexión a la base de datos
    Returns:
        {
            "status": "healthy"|"unhealthy",
            "database": true|false,
            "timestamp": "ISO-8601",
            "details": {
                "database_status": "string"
            }
        }
    """
    try:
        # Verificar conexión a la base de datos
        db_ok = db.health_check()

        status = "healthy" if db_ok else "unhealthy"

        return {
            "status": status,
            "database": db_ok,
            "timestamp": datetime.utcnow().isoformat(),
            "details": {
                "database_status": "Connected" if db_ok else "Disconnected"
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

@app.websocket("/ws/")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket abierto, esperando imágenes...")

    while True:
        try:
            data = await websocket.receive_json()
            id_empleado = data.get("id_empleado")
            registrar = data.get("registrar", False)

            if registrar and id_empleado:
                await registrar_empleado(websocket, data, id_empleado)
            else:
                await verificar_identidad(websocket, data)

        except Exception as e:
            print("❌ Error en el procesamiento:", e)
            break
