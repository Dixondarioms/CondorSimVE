"""Interceptacion aerea y naval (Cóndor): una aeronave o un buque sale al encuentro de una aeronave o un buque enemigo.

A diferencia de la orden de ataque, que persigue al blanco en linea recta, el interceptor vuela (o navega) con
punteria adelantada: hacia el punto donde se encontrara con el blanco segun el rumbo y la velocidad que este lleva
(`solucion`). Antes de emitir la orden se estima si lo alcanza, en cuanto tiempo, donde y con cuanto combustible queda
para volver (`estimar`). En vuelo pasa por fases:

  1. vectoreo: hacia el punto de encuentro, con la ultima posicion conocida del blanco;
  2. contacto: los sensores propios lo detectan;
  3. identificacion: se acerca a la distancia de identificacion visual (engine/contactos_vivo.py) cuando la accion
     elegida o las reglas de enfrentamiento lo exigen;
  4. accion: «seguir» (lo escolta a distancia y lo mantiene a la vista del bando) o «neutralizar» (lo ataca con sus armas,
     como la orden de ataque).

Si se pierde el contacto, sigue la estima (rumbo y velocidad del blanco) y despues busca sobre el ultimo punto conocido;
pasado BUSQUEDA_S la interceptacion se aborta. El combustible critico la aborta como cualquier vuelo (regresa solo). Un
buque no alcanza a una aeronave: los buques interceptan buques; las aeronaves, aeronaves y buques.
"""

from __future__ import annotations

import json
import math

from app.engine import catalogo, geo, relieve

ACCIONES = {
    "seguir": "Identificar y seguir",
    "neutralizar": "Identificar y neutralizar",
    "directo": "Neutralizar sin esperar la identificación",
}
DISTANCIA_SEGUIMIENTO_KM = {"aerea": 5.0, "naval": 9.0}  # a cuanto se pone el interceptor al seguir al blanco
FASES = {"alerta": "alerta en tierra (despegando)", "vectoreo": "vectoreo", "contacto": "contacto",
         "identificacion": "identificación", "seguimiento": "seguimiento", "ataque": "ataque",
         "estima": "estima (contacto perdido)", "busqueda": "búsqueda sobre el último punto"}
ALERTA_TIERRA_S = 300.0  # alerta por defecto (5 min); cada aeronave tiene la suya: aeronaves.despegue_s
TRAZA_MIN_S = 20.0  # la velocidad del blanco se estima con dos posiciones separadas al menos este tiempo
BUSQUEDA_S = 1200.0  # sin contacto ni estima util, busca sobre el ultimo punto conocido este tiempo y aborta
ESTIMA_S = 600.0  # durante este tiempo sin contacto sigue la estima del rumbo y la velocidad del blanco
KM_LAT = 110.57


def tipo_blanco(u) -> str:
    """aerea (en vuelo) o naval; cualquier otra cosa no se intercepta."""
    if u.tipo == "aerea" and not getattr(u, "en_tierra", False):
        return "aerea"
    return "naval" if u.tipo == "naval" else ""


def puede_interceptar(interceptor, blanco, accion: str) -> str | None:
    """Motivo por el que no puede (None si puede)."""
    if interceptor.tipo not in ("aerea", "naval") or catalogo.es_misil(interceptor):
        return "Solo las aeronaves y los buques interceptan."
    tb = tipo_blanco(blanco)
    if not tb:
        return "Solo se interceptan aeronaves en vuelo y buques."
    if interceptor.tipo == "naval" and tb == "aerea":
        return "Un buque no alcanza a una aeronave: contra ella, su antiaérea tira sola según la doctrina."
    if accion not in ACCIONES:
        return "Elija qué hacer al interceptar."
    if accion != "seguir" and catalogo.perfil(interceptor).ataque_vs.get(tb, 0.0) <= 0:
        quien = "aeronaves" if tb == "aerea" else "buques"
        return f"{catalogo.perfil(interceptor).nombre} no tiene armas contra {quien}: elija «Identificar y seguir»."
    return None


def codificar(accion: str, fase: str = "vectoreo", **extra) -> str:
    return json.dumps({"accion": accion, "fase": fase, **extra}, separators=(",", ":"))


def decodificar(detalle: str | None) -> dict:
    try:
        d = json.loads(detalle or "{}")
    except ValueError:
        return {}
    return d if isinstance(d, dict) else {}


def necesita_identificar(accion: str, estado_armas: str) -> bool:
    """Seguir y neutralizar identifican siempre; «directo» solo si las armas estan en estado restringido (la doctrina
    exige identificar antes de tirar)."""
    return accion in ("seguir", "neutralizar") or estado_armas == "restringido"


def dominio(blanco) -> str:
    """Estado de armas de la doctrina que rige contra el blanco."""
    return "armas_aire" if tipo_blanco(blanco) == "aerea" else "armas_superficie"


def punto_de_mira(ilat: float, ilon: float, vi_kmh: float, tlat: float, tlon: float, ve: float, vn: float):
    """(lat, lon, alcanzable): el punto de encuentro o, si el blanco se aleja mas rapido, el blanco mismo (persecucion)."""
    s = solucion(ilat, ilon, vi_kmh, tlat, tlon, ve, vn)
    if s is None:
        return tlat, tlon, False
    return s[1], s[2], True


def estimada(lat: float, lon: float, ve: float, vn: float, segundos: float) -> tuple[float, float]:
    """Donde estara el blanco dentro de `segundos` si mantiene rumbo y velocidad (la estima)."""
    h = segundos / 3600.0
    return _grados(lat, lon, ve * h, vn * h)


def velocidad_de(u) -> tuple[float, float]:
    """Velocidad (este, norte) en km/h que se le estima al blanco: la de su marcha si va a algun lado; cero si orbita,
    espera o esta detenido (se apunta a donde esta)."""
    en_marcha = bool(getattr(u, "ruta_json", None)) or (u.tipo == "aerea" and getattr(u, "orden_id", None) and not getattr(u, "mision", ""))
    if not en_marcha or not u.velocidad_kmh:
        return 0.0, 0.0
    rumbo = u.rumbo or 0.0
    ruta = json.loads(u.ruta_json) if getattr(u, "ruta_json", None) else []
    if ruta:  # hacia su proximo punto (el rumbo guardado puede ser el de antes de recibir la orden)
        x, y = _km(u.lat, u.lon, ruta[0][0], ruta[0][1])
        if math.hypot(x, y) > 0.05:
            rumbo = math.degrees(math.atan2(x, y))
    r = math.radians(rumbo)
    v = float(u.velocidad_kmh)
    return v * math.sin(r), v * math.cos(r)


def _km(lat0: float, lon0: float, lat: float, lon: float) -> tuple[float, float]:
    """(este, norte) en km de (lat, lon) respecto de (lat0, lon0), en un plano local."""
    return (lon - lon0) * 111.32 * math.cos(math.radians(lat0)), (lat - lat0) * KM_LAT


def _grados(lat0: float, lon0: float, x: float, y: float) -> tuple[float, float]:
    return lat0 + y / KM_LAT, lon0 + x / (111.32 * math.cos(math.radians(lat0)))


def solucion(ilat: float, ilon: float, vi_kmh: float, tlat: float, tlon: float, ve: float, vn: float):
    """Punto de encuentro con punteria adelantada: (horas, lat, lon), o None si el blanco se aleja mas rapido.

    Resuelve |P + V t| = vi t con P la posicion del blanco respecto del interceptor y V su velocidad."""
    if vi_kmh <= 0:
        return None
    px, py = _km(ilat, ilon, tlat, tlon)
    a = ve * ve + vn * vn - vi_kmh * vi_kmh
    b = 2.0 * (px * ve + py * vn)
    c = px * px + py * py
    if c < 1e-6:
        return 0.0, tlat, tlon
    if abs(a) < 1e-9:
        if b >= 0:
            return None
        t = -c / b
    else:
        disc = b * b - 4 * a * c
        if disc < 0:
            return None
        raices = [x for x in ((-b - math.sqrt(disc)) / (2 * a), (-b + math.sqrt(disc)) / (2 * a)) if x > 0]
        if not raices:
            return None
        t = min(raices)
    lat, lon = _grados(ilat, ilon, px + ve * t, py + vn * t)
    return t, lat, lon


def consumo_por_km(u) -> float:
    """Puntos de combustible por km recorrido (como engine/movimiento.py)."""
    return 100.0 / (max(u.autonomia_km, 1e-9) / relieve.factor_consumo(u))


def estimar(interceptor, blanco, unidades=()) -> dict:
    """Lo que se espera de la interceptacion: si alcanza al blanco, cuando, donde y con cuanto combustible queda para
    volver a la base propia mas cercana (aeronaves) o cuanto le queda (buques). Una aeronave en tierra suma lo que
    tarda en despegar (su apresto, aeronaves.despegue_s), durante el cual el blanco sigue avanzando."""
    from app.engine import aeronaves as aeronaves_mod

    ve, vn = velocidad_de(blanco)
    vb = math.hypot(ve, vn)
    demora = aeronaves_mod.despegue_s(interceptor) if getattr(interceptor, "en_tierra", False) else 0.0
    tlat, tlon = estimada(blanco.lat, blanco.lon, ve, vn, demora)
    s = solucion(interceptor.lat, interceptor.lon, interceptor.velocidad_kmh, tlat, tlon, ve, vn)
    salida = {"alcanzable": s is not None, "velocidad_blanco_kmh": round(vb), "velocidad_propia_kmh": round(interceptor.velocidad_kmh or 0),
              "despegue_min": round(demora / 60)}
    if s is None:
        salida["motivo"] = (f"El blanco va a {vb:.0f} km/h y se aleja: a {interceptor.velocidad_kmh:.0f} km/h no se lo alcanza "
                            "(se lo perseguirá por si cambia de rumbo).")
        return salida
    t, lat, lon = s
    km = geo.distancia_km(interceptor.lat, interceptor.lon, lat, lon)
    llegada = interceptor.combustible - km * consumo_por_km(interceptor)
    salida.update(minutos=round(t * 60 + demora / 60), lat=round(lat, 5), lon=round(lon, 5), km=round(km),
                  combustible_llegada=round(llegada, 1))
    if interceptor.tipo == "aerea":
        # la base propia con plazas mas cercana a donde esta ahora (a la que volveria despues de interceptar)
        base = aeronaves_mod.base_mas_cercana(interceptor, list(unidades)) if unidades else None
        if base is not None:
            vuelta = geo.distancia_km(lat, lon, base.lat, base.lon) * consumo_por_km(interceptor)
            salida.update(base=base.nombre, combustible_regreso=round(llegada - vuelta, 1))
            if llegada - vuelta < 0:
                salida["motivo"] = f"No le alcanza el combustible para volver a {base.nombre} después de interceptar."
    if llegada < 0:
        salida["motivo"] = "No le alcanza el combustible para llegar al punto de encuentro."
    return salida
