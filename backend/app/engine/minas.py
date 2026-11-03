"""Minas navales del Cóndor (como en los simuladores de mando modernos).

- Sembrar (orden «minar»): un buque (patrullero, fragata, submarino, buque de desembarco) o una aeronave de ataque o de
  patrulla maritima va al punto y siembra un campo de MINAS_POR_CAMPO minas en un circulo de RADIO_KM (el buque tarda
  SIEMBRA_BUQUE_S; la aeronave, una pasada). Gasta MUNICION_POR_CAMPO % de su municion.
- Riesgo: todo buque que navega dentro de un campo (las minas no distinguen bandos) arriesga chocar una mina: la
  probabilidad crece con los kilometros que recorre adentro y con la densidad que le queda al campo. Un choque le
  quita entre DANO_MINA puntos de fuerza (con sus impactos criticos en los sistemas) y gasta una mina. Sin azar, el
  daño esperado.
- Quien sembro el campo lo conoce; el otro bando, recien cuando un buque suyo choca una mina o un cazaminas lo detecta
  (a DETECCION_CAZAMINAS_KM).
- Barrido (orden «barrer»): un cazaminas dentro del campo lo limpia de a BARRIDO_POR_HORA; con su sonar de minas
  corre poco riesgo (FACTOR_RIESGO_CAZAMINAS). Un campo sin minas desaparece.
"""

from __future__ import annotations

import hashlib
import json
import random

from app.engine import catalogo, geo

RADIO_KM = 3.0
MINAS_POR_CAMPO = 20
SIEMBRA_BUQUE_S = 1800.0
MUNICION_POR_CAMPO = 25.0
RIESGO_POR_KM = 0.04  # probabilidad de choque por km navegado dentro de un campo lleno
DANO_MINA = (30.0, 60.0)
DETECCION_CAZAMINAS_KM = 5.0
BARRIDO_POR_HORA = 0.25  # fraccion de las minas del campo que limpia un cazaminas por hora
FACTOR_RIESGO_CAZAMINAS = 0.1
FACTOR_RIESGO_SUBMARINO = 0.5  # a profundidad pasa por debajo de muchas minas de fondeo
MINADORES_NAVALES = ("patrullero", "fragata", "submarino", "buque_desembarco")
MINADORES_AEREOS = ("ataque",)
LLEGADA_KM = 1.0


def siembra(u) -> bool:
    """La unidad puede sembrar minas."""
    if getattr(u, "tipo", "") == "naval":
        return u.clase in MINADORES_NAVALES
    return getattr(u, "tipo", "") == "aerea" and u.clase in MINADORES_AEREOS and not getattr(u, "en_tierra", False)


def barre(u) -> bool:
    return getattr(u, "clase", None) == "cazaminas"


def conocido(campo, bando: str) -> bool:
    return bando not in ("azul", "rojo") or campo.bando == bando or bando in json.loads(campo.conocido_por or "[]")


def revelar(campo, bando: str) -> bool:
    """El bando conoce el campo desde ahora. True si no lo conocia."""
    if conocido(campo, bando):
        return False
    lista = json.loads(campo.conocido_por or "[]")
    lista.append(bando)
    campo.conocido_por = json.dumps(sorted(set(lista)))
    return True


def dentro(campo, lat: float, lon: float) -> bool:
    return geo.distancia_km(lat, lon, campo.lat, campo.lon) <= campo.radio_km


def km_dentro(campo, desde: tuple, hasta: tuple, muestras: int = 8) -> float:
    """Kilometros del tramo desde -> hasta que quedan dentro del campo (por muestras)."""
    total = geo.distancia_km(desde[0], desde[1], hasta[0], hasta[1])
    if total <= 0:
        return 0.0
    adentro = sum(1 for k in range(muestras) if dentro(campo, desde[0] + (hasta[0] - desde[0]) * (k + 0.5) / muestras,
                                                     desde[1] + (hasta[1] - desde[1]) * (k + 0.5) / muestras))
    return total * adentro / muestras


def riesgo(u, km: float, campo) -> float:
    """Probabilidad de chocar una mina al navegar `km` dentro del campo."""
    if km <= 0 or campo.densidad <= 0:
        return 0.0
    factor = FACTOR_RIESGO_CAZAMINAS if barre(u) else 1.0
    if getattr(u, "clase", None) == "submarino" and getattr(u, "profundidad", None) == "profunda":
        factor *= FACTOR_RIESGO_SUBMARINO
    return min(0.9, km * RIESGO_POR_KM * campo.densidad * factor)


def choque(semilla: int, u, campo, t: float, p: float, azar: bool) -> float:
    """Daño (puntos de fuerza) del paso por el campo: con azar, un choque o nada; sin azar, el esperado."""
    if p <= 0:
        return 0.0
    rng = random.Random(int.from_bytes(hashlib.sha256(f"{semilla}:mina:{u.id}:{campo.id}:{t:.0f}".encode()).digest()[:8], "big"))
    dano = rng.uniform(*DANO_MINA)
    if not azar:
        return p * sum(DANO_MINA) / 2.0
    return dano if rng.random() < p else 0.0


def gastar_mina(campo, cantidad: float = 1.0) -> None:
    campo.densidad = max(0.0, campo.densidad - cantidad / MINAS_POR_CAMPO)


def campos_para(db, escenario, rol: str) -> list[dict]:
    from app.models.mina import CampoMinas

    salida = []
    for c in db.query(CampoMinas).filter(CampoMinas.escenario_id == escenario.id, CampoMinas.densidad > 0):
        if conocido(c, rol):
            salida.append({"id": c.id, "bando": c.bando, "lat": c.lat, "lon": c.lon, "radio_km": c.radio_km,
                           "minas": round(c.densidad * MINAS_POR_CAMPO), "propio": rol in ("azul", "rojo") and c.bando == rol})
    return salida


def error_de_siembra(u) -> str | None:
    if not siembra(u):
        return ("Siembran minas los patrulleros, fragatas, submarinos y buques de desembarco, y los aviones de ataque en "
                "vuelo.")
    if u.municion < MUNICION_POR_CAMPO:
        return f"Sin munición suficiente para un campo de minas ({MUNICION_POR_CAMPO:.0f} %)."
    return None


def nombre_clase(u) -> str:
    return catalogo.obtener(u.clase, u.tipo).nombre
