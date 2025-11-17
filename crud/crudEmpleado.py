import uuid
from datetime import datetime, timedelta
from .database import db, Database

db = Database()  # O como se llame tu clase
db._initialize_pool()

class RegistroHorario:
    def __init__(self, id_empleado, id_periodo, id_puesto, tipo, fecha, hora, estado=None, turno=None):
        self.id_empleado = id_empleado
        self.id_periodo = id_periodo
        self.id_puesto = id_puesto
        self.tipo = tipo
        self.fecha = fecha
        self.hora = hora
        self.estado = estado
        self.turno = turno

    @staticmethod
    def registrar_asistencia(id_empleado: int, fecha_hora: datetime):
        """
        Registra una asistencia biométrica si corresponde, validando condiciones horarias
        y evitando doble fichaje.

        Returns:
            RegistroHorario: registro creado
            None: si está fuera de rango permitido
        Raises:
            ValueError: si ya existe fichaje, o no se puede registrar
        """
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                # 🔍 Obtener datos laborales
                cur.execute("""
                    SELECT id_puesto, turno, hora_inicio_turno, hora_fin_turno
                    FROM informacion_laboral
                    WHERE id_empleado = %s
                """, (id_empleado,))
                resultado = cur.fetchone()
                if not resultado:
                    raise ValueError("No se encontró información laboral para el empleado")

                id_puesto, turno, hora_inicio, hora_fin = resultado

                fecha_actual = fecha_hora.date()
                hora_actual = fecha_hora.replace(second=0, microsecond=0).time()
                print(fecha_actual)
                # 🗓 Periodo
                cur.execute("SELECT obtener_o_crear_periodo_empleado(%s, %s);", (id_empleado, fecha_actual))
                id_periodo = cur.fetchone()[0]

                # 🕐 Fechas completas
                entrada_dt = datetime.combine(fecha_actual, hora_inicio)
                salida_dt = datetime.combine(fecha_actual, hora_fin)
                actual_dt = fecha_hora.replace(second=0, microsecond=0)

                #cargamos desde la db
                cur.execute("""
                    SELECT clave, valor
                    FROM configuracion_asistencia
                    WHERE clave IN ('entrada_temprana', 'tolerancia', 'retraso_min', 'salida_valida', 'salida_fuera')
                """)
                config_rows = cur.fetchall()
                config = {clave: valor for clave, valor in config_rows}

                #definimos desde las variables de la db
                entrada_temprana_delta = config.get('entrada_temprana', timedelta(hours=1))
                tolerancia = config.get('tolerancia', timedelta(minutes=5))
                retraso_min = config.get('retraso_min', timedelta(minutes=15))
                salida_valida = config.get('salida_valida', timedelta(minutes=30))
                salida_fuera = config.get('salida_fuera', timedelta(hours=2))

                entrada_temprana = entrada_dt - entrada_temprana_delta

            #configuracion_asistencia

                # 🧠 Lógica de tipo y estado
                if actual_dt < entrada_temprana:
                    return None  # demasiado temprano
                elif entrada_temprana <= actual_dt < entrada_dt:
                    tipo, estado = "Entrada", "Temprana"
                elif entrada_dt <= actual_dt <= entrada_dt + tolerancia:
                    tipo, estado = "Entrada", "A tiempo"
                elif entrada_dt + tolerancia < actual_dt <= entrada_dt + retraso_min:
                    tipo, estado = "Entrada", "Retraso mínimo"
                elif entrada_dt + retraso_min < actual_dt < salida_dt - timedelta(hours=3):
                    tipo, estado = "Entrada", "Tarde"
                elif actual_dt < salida_dt - salida_valida:
                    tipo, estado = "Salida", "Temprana"
                elif salida_dt - salida_valida <= actual_dt <= salida_dt + salida_valida:
                    tipo = "Salida"
                    estado = "A tiempo" if actual_dt == salida_dt else "Temprana" if actual_dt < salida_dt else "Tarde"
                elif salida_dt + salida_valida < actual_dt <= salida_dt + salida_fuera:
                    tipo, estado = "Salida", "Tarde"
                else:
                    tipo, estado = "Salida", "Fuera de rango"

                # ❌ Validar si ya fichó ese tipo hoy
                cur.execute("""
                    SELECT 1 FROM asistencia_biometrica
                    WHERE id_empleado = %s AND tipo = %s AND fecha = %s
                """, (id_empleado, tipo, fecha_actual))
                if cur.fetchone():
                    raise ValueError(f"Ya se registró una {tipo.lower()} hoy para este empleado.")

                if tipo == "Salida":
                    cur.execute("""
                        SELECT 1 FROM asistencia_biometrica
                        WHERE id_empleado = %s AND tipo = 'Entrada' AND fecha = %s
                    """, (id_empleado, fecha_actual))
                    if not cur.fetchone():
                        raise ValueError("No se puede registrar una salida sin haber registrado una entrada.")

                # ✅ Insertar registro
                cur.execute("""
                    INSERT INTO asistencia_biometrica (
                        id_empleado, id_periodo, id_puesto, tipo, fecha, hora,
                        estado_asistencia, turno_asistencia
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id_empleado, id_periodo, id_puesto, tipo, fecha, hora, estado_asistencia, turno_asistencia
                """, (
                    id_empleado, id_periodo, id_puesto, tipo,
                    fecha_actual, hora_actual, estado, turno
                ))
                resultado_insert = cur.fetchone()
                if not resultado_insert or len(resultado_insert) < 6:
                    raise ValueError(f"Error al insertar registro, datos incompletos: {resultado_insert}")
                registro_data = list(resultado_insert)
                registro_data[4] = datetime.strptime(registro_data[4], "%Y-%m-%d").date() if isinstance(registro_data[4], str) else registro_data[4]
                registro_data[5] = datetime.strptime(registro_data[5], "%H:%M:%S").time() if isinstance(registro_data[5], str) else registro_data[5]
                conn.commit()

                return RegistroHorario(*registro_data)

        except Exception as e:
            conn.rollback()
            raise ValueError(f"Error al registrar asistencia biométrica: {e}")

        finally:
            db.return_connection(conn)
