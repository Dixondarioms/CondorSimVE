"""Efectos del clima. El instructor fija un clima general por escenario y, ademas, puede colocar zonas
meteorologicas (nublado, lluvia o tormenta) con centro, radio, deriva y duracion: frentes que se desplazan
turno a turno. El clima efectivo en un punto es el peor entre el general y las zonas que lo cubren.

Las funciones de factor aceptan un nombre de clima ("lluvia") o un contexto `ClimaLocal` mas la posicion
(lat, lon) donde se aplica: asi el resto del motor puede pasar el contexto donde antes pasaba la cadena."""

import math

from app.engine import geo

CLIMAS = ("despejado", "nublado", "lluvia", "tormenta")
SEVERIDAD = {c: i for i, c in enumerate(CLIMAS)}

# Multiplicador del radio de deteccion de todas las unidades.
DETECCION = {"despejado": 1.0, "nublado": 0.9, "lluvia": 0.7, "tormenta": 0.5}
# Multiplicador de velocidad segun el tipo de unidad.
MOVIMIENTO = {
    "terrestre": {"despejado": 1.0, "nublado": 1.0, "lluvia": 0.8, "tormenta": 0.6},
    "naval": {"despejado": 1.0, "nublado": 1.0, "lluvia": 0.9, "tormenta": 0.5},
    "aerea": {"despejado": 1.0, "nublado": 1.0, "lluvia": 0.9, "tormenta": 0.6},
}
# Multiplicador de la efectividad de los ataques realizados por unidades aereas.
ATAQUE_AEREO = {"despejado": 1.0, "nublado": 0.95, "lluvia": 0.8, "tormenta": 0.5}

RADIO_ZONA_MIN_KM, RADIO_ZONA_MAX_KM = 5.0, 600.0
DERIVA_MAX_KMH = 120.0


# ---- ciclo de dia y noche (Venezuela, ~10 grados norte: el sol sale hacia las 06:00 y se pone hacia las 18:30) ----
PERIODOS = ("dia", "crepusculo", "noche")
# fraccion del radio de deteccion que conserva cada tipo de sensor; el radar no depende de la luz
NOCHE_VISUAL = {"dia": 1.0, "crepusculo": 0.75, "noche": 0.5}  # a simple vista (tropas, vehiculos, buques)
NOCHE_OPTRONICO = {"dia": 1.0, "crepusculo": 0.9, "noche": 0.8}  # camaras termicas de aeronaves, drones y reconocimiento


def periodo_del_dia(hora_inicio_min: int, turno: int) -> str:
    """Periodo de la hora simulada del turno (cada turno = 1 h desde hora_inicio_min)."""
    hora = ((hora_inicio_min or 0) + max(0, (turno or 1) - 1) * 60) % 1440 // 60
    if 7 <= hora < 18:
        return "dia"
    if hora in (6, 18):
        return "crepusculo"
    return "noche"


def periodo_de(escenario) -> str:
    if not getattr(escenario, "dia_noche", False):
        return "dia"
    return periodo_del_dia(escenario.hora_inicio_min, escenario.turno_actual)


def factor_nocturno(clase, periodo: str) -> float:
    """Cuanto conserva de su deteccion un sensor de esa clase en ese periodo del dia."""
    if periodo == "dia" or clase.emisor or clase.solo_aereo:
        return 1.0
    if clase.tipo == "aerea" or clase.dron or clase.id == "reconocimiento":
        return NOCHE_OPTRONICO.get(periodo, 1.0)
    return NOCHE_VISUAL.get(periodo, 1.0)


class ClimaLocal:
    """Clima general del escenario mas sus zonas (objetos con tipo, lat, lon, radio_km) y el periodo del dia."""

    def __init__(self, general: str = "despejado", zonas=(), periodo: str = "dia"):
        self.general = general if general in SEVERIDAD else "despejado"
        self.zonas = list(zonas)
        self.periodo = periodo if periodo in PERIODOS else "dia"

    def en(self, lat: float, lon: float) -> str:
        peor = self.general
        for z in self.zonas:
            if z.tipo in SEVERIDAD and SEVERIDAD[z.tipo] > SEVERIDAD[peor] \
                    and geo.distancia_km(lat, lon, z.lat, z.lon) <= z.radio_km:
                peor = z.tipo
        return peor

    def __str__(self) -> str:  # compatibilidad con quien lo trata como cadena (informes)
        return self.general


def resolver(clima, lat=None, lon=None) -> str:
    """Nombre del clima que rige: la cadena dada, o el del contexto en (lat, lon) (o su general si no hay punto)."""
    if isinstance(clima, ClimaLocal):
        return clima.en(lat, lon) if lat is not None and lon is not None else clima.general
    return clima if clima in SEVERIDAD else "despejado"


def factor_deteccion(clima, lat=None, lon=None) -> float:
    return DETECCION.get(resolver(clima, lat, lon), 1.0)


def factor_movimiento(clima, tipo: str, lat=None, lon=None) -> float:
    return MOVIMIENTO.get(tipo, {}).get(resolver(clima, lat, lon), 1.0)


def factor_ataque_aereo(clima, lat=None, lon=None) -> float:
    return ATAQUE_AEREO.get(resolver(clima, lat, lon), 1.0)


def desplazar(lat: float, lon: float, rumbo: float, km: float) -> tuple[float, float]:
    """Punto a `km` de (lat, lon) con rumbo `rumbo` (grados desde el norte)."""
    r = math.radians(rumbo)
    dlat = km * math.cos(r) / 110.574
    dlon = km * math.sin(r) / (111.32 * max(0.2, math.cos(math.radians(lat))))
    return lat + dlat, lon + dlon


# ------------------------------------------------------------------ zonas persistidas
def zonas_de(db, escenario) -> list:
    from app.models.zona_clima import ZonaClima

    return db.query(ZonaClima).filter(ZonaClima.escenario_id == escenario.id).order_by(ZonaClima.id).all()


def contexto(db, escenario) -> ClimaLocal:
    periodo = periodo_de(escenario)
    if not getattr(escenario, "efectos_clima", True):  # direccion: efectos del clima apagados
        return ClimaLocal("despejado", periodo=periodo)
    return ClimaLocal(escenario.clima, zonas_de(db, escenario), periodo)


def error_de_zona(tipo: str, radio_km: float, deriva_kmh: float) -> str | None:
    if tipo not in SEVERIDAD or tipo == "despejado":
        return "El tipo de la zona debe ser nublado, lluvia o tormenta."
    if not RADIO_ZONA_MIN_KM <= radio_km <= RADIO_ZONA_MAX_KM:
        return f"El radio debe estar entre {RADIO_ZONA_MIN_KM:.0f} y {RADIO_ZONA_MAX_KM:.0f} km."
    if not 0 <= deriva_kmh <= DERIVA_MAX_KMH:
        return f"La deriva debe estar entre 0 y {DERIVA_MAX_KMH:.0f} km/h."
    return None


def avanzar(db, escenario, turno: int) -> list:
    """Al terminar el turno: cada zona se desplaza segun su deriva (una hora) y las vencidas se borran.
    Devuelve las zonas que caducaron."""
    caducadas = []
    for z in zonas_de(db, escenario):
        if z.hasta_turno is not None and turno >= z.hasta_turno:
            caducadas.append(z)
            db.delete(z)
            continue
        if z.deriva_kmh > 0:
            z.lat, z.lon = desplazar(z.lat, z.lon, z.deriva_rumbo, z.deriva_kmh * 1.0)
    return caducadas


def serializar(z) -> dict:
    return {
        "id": z.id, "tipo": z.tipo, "lat": round(z.lat, 5), "lon": round(z.lon, 5), "radio_km": z.radio_km,
        "deriva_rumbo": z.deriva_rumbo, "deriva_kmh": z.deriva_kmh, "hasta_turno": z.hasta_turno, "nombre": z.nombre or "",
    }
