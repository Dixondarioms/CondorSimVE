"""Guerra electronica: interferencia (jamming) y escucha (ESM), con sus efectos sobre sensores, defensa
antiaerea y enlaces de drones. Abstraccion didactica, no un modelo de propagacion.

- Interferir: una unidad con capacidad de interferencia (GE terrestre o avion de GE en vuelo) emite sobre un punto
  a su alcance y crea una zona (radio segun su clase). La zona rige en el turno en que se resuelve la orden y
  durante la planificacion del siguiente; para mantenerla hay que volver a ordenarla.
- Dentro de una zona, contra el bando contrario: sus sensores ven al 30 % de su distancia (los radares al 20 %;
  a ojo, 3 km siempre); su antiaerea guiada por radar pierde el 60 % de su efecto contra aeronaves; y sus drones
  pierden el enlace de datos y no aceptan ordenes (mantienen su posicion o su patrulla).
- Interferir delata: mientras emite, el interferidor es visible para el bando contrario.
- Escucha: las unidades de GE localizan emisores enemigos (radares, antiaerea guiada por radar e interferidores
  activos) mucho mas lejos que su deteccion normal.
"""

from app.engine import catalogo, geo
from app.models.interferencia import Interferencia

FACTOR_SENSOR = 0.3
FACTOR_RADAR = 0.2
RADIO_VISUAL_KM = 3.0
FACTOR_ANTIAEREA = 0.4
MOTIVO_SIN_ENLACE = (
    "Sin enlace de datos: el dron esta dentro de una zona de interferencia enemiga y no recibe ordenes."
)


class Contexto:
    """Zonas de interferencia vigentes y unidades que estan emitiendo."""

    def __init__(self, zonas=()):
        self.zonas = list(zonas)
        self.emisores = {z.unidad_id for z in self.zonas if z.unidad_id is not None}

    def zonas_sobre(self, u) -> list:
        """Zonas del bando contrario a `u` que la cubren."""
        return [
            z for z in self.zonas
            if z.bando != u.bando and geo.distancia_km(u.lat, u.lon, z.lat, z.lon) <= z.radio_km
        ]

    def interferido(self, u) -> bool:
        return bool(self.zonas_sobre(u))

    def emite(self, u) -> bool:
        return getattr(u, "id", None) in self.emisores


def contexto(db, escenario, en_resolucion: bool = False) -> Contexto:
    """Durante la resolucion rigen las zonas creadas en este turno; en la planificacion, las del turno anterior."""
    turno = escenario.turno_actual if en_resolucion else escenario.turno_actual - 1
    return Contexto(
        db.query(Interferencia)
        .filter(Interferencia.escenario_id == escenario.id, Interferencia.turno == turno)
        .order_by(Interferencia.id)
        .all()
    )


def error_de_interferencia(u, punto) -> str | None:
    """Motivo por el que `u` no puede interferir sobre `punto` [lat, lon] (None si puede)."""
    clase = catalogo.obtener(u.clase, u.tipo)
    if clase.interferencia_km <= 0:
        return "Solo las unidades de guerra electronica pueden interferir."
    if u.estado != "activa":
        return "La unidad no esta activa."
    if u.tipo == "aerea" and u.en_tierra:
        return "La aeronave esta en tierra: debe despegar para interferir."
    if not punto:
        return "Indique el centro de la zona a interferir."
    d = geo.distancia_km(u.lat, u.lon, punto[0], punto[1])
    if d > u.alcance_km:
        return f"El punto esta fuera del alcance del interferidor ({d:.0f} km > {u.alcance_km:.0f} km)."
    return None


def enlace_perdido(u, ge: Contexto) -> bool:
    return catalogo.obtener(u.clase, u.tipo).dron and ge.interferido(u)


def serializar(z: Interferencia) -> dict:
    return {"id": z.id, "bando": z.bando, "unidad_id": z.unidad_id, "lat": z.lat, "lon": z.lon,
            "radio_km": z.radio_km, "turno": z.turno}
