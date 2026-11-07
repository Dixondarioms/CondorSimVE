"""Trafico civil y neutral del Cóndor (como en los simuladores de mando modernos).

El director genera trafico civil en una zona (la vista del mapa): aviones comerciales que vuelan por aerovias (rectas
que cruzan la zona, fijas para el escenario), buques mercantes que la atraviesan por el agua y pesqueros que van de un
punto a otro dentro de ella. Son unidades del bando «neutral» sin armas ni sensores; el motor mantiene la cantidad
pedida: el que sale de la zona se retira (estado "retirada") y entra otro.

Para cada bando son contactos desconocidos hasta que los clasifica: con las armas «libres» se les puede tirar por
error mientras sean desconocidos; con «restringidas», nunca (exigen identificar). Tirarle a una unidad neutral es daño
colateral: alerta al bando que tiro, evento para el informe y penalizacion en el puntaje (engine/objetivos.py).
El bando «neutral» tambien sirve para las fuerzas de un pais que no participa (las ubica el director).
"""

from __future__ import annotations

import json
import zlib
import math
import random

from app.engine import catalogo

CLASES = {"aviones": "avion_comercial", "mercantes": "buque_mercante", "pesqueros": "pesquero"}
MAXIMO = {"aviones": 40, "mercantes": 30, "pesqueros": 30}
AEROVIAS = 5  # aerovias por zona
MANTENER_CADA_S = 120.0
MUESTRAS_AGUA = 12  # puntos de una derrota que deben ser agua
PENALIDAD_ATAQUE = 10  # puntos que pierde un bando por cada unidad neutral que ataca
PENALIDAD_POR_FUERZA = 5  # y uno mas por cada esta cantidad de fuerza que le quita
AEROLINEAS = ("AVA", "CMP", "LAN", "AAL", "IBE", "TAP", "DAL", "AFR", "KLM", "UAE", "CNV", "AEA", "LPE", "GLO")
NOMBRES_BUQUE = ("Atlántico", "Caribe Star", "Orinoco Trader", "Margarita", "Pacific Spirit", "Aurora", "Esperanza",
                 "Cordillera", "Paraguaná", "Nueva Esparta", "Boca de Serpiente", "Golfo Triste", "Los Roques", "Tamarindo")
NOMBRES_PESQUERO = ("Don Pedro", "La Chinita", "Virgen del Valle", "San Rafael", "El Tiburón", "Mar Azul", "La Perla",
                    "Doña Carmen", "Juan Griego", "El Pargo")


def config(esc) -> dict:
    try:
        d = json.loads(getattr(esc, "trafico_json", None) or "{}")
    except ValueError:
        d = {}
    return d if isinstance(d, dict) else {}


def es_civil(u) -> bool:
    return bool(catalogo.obtener(getattr(u, "clase", None), getattr(u, "tipo", "")).civil)


def neutral(u) -> bool:
    return getattr(u, "bando", "") == "neutral"


def _borde(rng: random.Random, z: list) -> tuple[float, float, int]:
    """Punto al azar sobre el borde de la zona [lat_min, lon_min, lat_max, lon_max] y en que lado (0-3)."""
    lado = rng.randrange(4)
    a = rng.random()
    if lado == 0:
        return z[0], z[1] + a * (z[3] - z[1]), lado
    if lado == 1:
        return z[2], z[1] + a * (z[3] - z[1]), lado
    if lado == 2:
        return z[0] + a * (z[2] - z[0]), z[1], lado
    return z[0] + a * (z[2] - z[0]), z[3], lado


def _cruce(rng: random.Random, z: list) -> list[list[float]]:
    """Recta que cruza la zona de un lado a otro."""
    a = _borde(rng, z)
    b = _borde(rng, z)
    while b[2] == a[2]:
        b = _borde(rng, z)
    return [[round(a[0], 4), round(a[1], 4)], [round(b[0], 4), round(b[1], 4)]]


def configurar(esc, aviones: int, mercantes: int, pesqueros: int, zona: list[float]) -> dict:
    """Guarda lo que pidio el director (y las aerovias de la zona, fijas para el escenario)."""
    z = [min(zona[0], zona[2]), min(zona[1], zona[3]), max(zona[0], zona[2]), max(zona[1], zona[3])]
    previa = config(esc)
    rng = random.Random(f"{esc.semilla}:aerovias:{z}")
    aerovias = previa.get("aerovias") if previa.get("zona") == z else [_cruce(rng, z) for _ in range(AEROVIAS)]
    d = {"aviones": max(0, min(MAXIMO["aviones"], aviones)), "mercantes": max(0, min(MAXIMO["mercantes"], mercantes)),
         "pesqueros": max(0, min(MAXIMO["pesqueros"], pesqueros)), "zona": z, "aerovias": aerovias}
    esc.trafico_json = json.dumps(d)
    return d


def _en_agua(terreno, a: list, b: list) -> bool:
    return all(terreno.clase(a[0] + (b[0] - a[0]) * k / MUESTRAS_AGUA, a[1] + (b[1] - a[1]) * k / MUESTRAS_AGUA) == "agua"
               for k in range(MUESTRAS_AGUA + 1))


def _punto_agua(rng, z, terreno, intentos=40):
    for _ in range(intentos):
        p = [z[0] + rng.random() * (z[2] - z[0]), z[1] + rng.random() * (z[3] - z[1])]
        if terreno.clase(*p) == "agua":
            return p
    return None


def _nueva(esc, tipo: str, rng: random.Random, terreno, al_borde: bool = False):
    """Unidad civil nueva para la zona (sin agregarla a la sesion), o None si no hay por donde (sin agua, p. ej.).
    La primera tanda aparece en cualquier punto de su derrota; las que reponen a las que salieron entran por el borde
    de la zona (como el trafico real, que llega de afuera: los radares la ven entrar)."""
    from app.models.unidad import Unidad

    d = config(esc)
    z = d["zona"]
    clase = catalogo.CLASES[CLASES[tipo]]
    if tipo == "aviones":
        via = rng.choice(d.get("aerovias") or [_cruce(rng, z)])
        a, b = (via if rng.random() < 0.5 else list(reversed(via)))
        t = 0.0 if al_borde else rng.random() * 0.7
        inicio = [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
        ruta, nombre = [b], f"Vuelo {rng.choice(AEROLINEAS)}{rng.randrange(100, 9999)}"
    elif tipo == "mercantes":
        for _ in range(30):
            a, b = _cruce(rng, z)
            if _en_agua(terreno, a, b):
                break
        else:
            return None
        t = 0.0 if al_borde else rng.random() * 0.6
        inicio = [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
        ruta, nombre = [b], f"M/V {rng.choice(NOMBRES_BUQUE)}"
    else:
        inicio = _punto_agua(rng, z, terreno)
        destino = _punto_agua(rng, z, terreno)
        if inicio is None or destino is None:
            return None
        ruta, nombre = [destino], f"Pesquero {rng.choice(NOMBRES_PESQUERO)}"
    u = Unidad(escenario_id=esc.id, nombre=nombre, bando="neutral", tipo=clase.tipo, clase=clase.id,
               lat=inicio[0], lon=inicio[1], fuerza=100.0, velocidad_kmh=clase.velocidad_kmh, alcance_km=0.0,
               deteccion_km=0.0, autonomia_km=clase.autonomia_km, combustible=100.0, municion=0.0,
               sidc=catalogo.generar_sidc("neutral", clase), estado="activa", echelon="")
    if tipo == "aviones":  # un avion comercial real del catalogo (por su nombre: no consume el generador al azar)
        civiles = sorted(m.id for m in catalogo.MODELOS.values() if m.clase == clase.id)
        if civiles:
            u.modelo = civiles[zlib.crc32(nombre.encode("utf-8")) % len(civiles)]
    u.ruta_json = json.dumps([[round(p[0], 5), round(p[1], 5)] for p in ruta])
    u.rumbo = _rumbo(inicio, ruta[0])
    return u


def _rumbo(a, b) -> float:
    y = math.sin(math.radians(b[1] - a[1])) * math.cos(math.radians(b[0]))
    x = (math.cos(math.radians(a[0])) * math.sin(math.radians(b[0]))
         - math.sin(math.radians(a[0])) * math.cos(math.radians(b[0])) * math.cos(math.radians(b[1] - a[1])))
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def mantener(ctx) -> None:
    """Retira el trafico que llego a su destino (salio de la zona), da otro destino a los pesqueros y completa la
    cantidad que pidio el director (a lo sumo unos pocos por vez, para que no aparezcan todos juntos)."""
    d = config(ctx.esc)
    if not d.get("zona"):
        return
    rng = random.Random(f"{ctx.esc.semilla}:trafico:{int(ctx.t)}")
    activos = {t: [] for t in CLASES}
    tipo_de = {c: t for t, c in CLASES.items()}
    hubo = {t: False for t in CLASES}  # ya hubo trafico de ese tipo: los nuevos entran por el borde
    for u in ctx.lista:
        if not es_civil(u) or u.clase not in tipo_de:
            continue
        hubo[tipo_de[u.clase]] = True
        if u.estado != "activa":
            continue
        sin_ruta = not u.ruta_json and u.orden_id is None
        if sin_ruta and u.clase == CLASES["pesqueros"]:
            destino = _punto_agua(rng, d["zona"], ctx.terreno, 10)
            if destino is not None:
                u.ruta_json = json.dumps([destino])
        elif sin_ruta or (u.tipo == "aerea" and u.mision == "espera" and u.orden_id is None):
            u.estado = "retirada"  # salio de la zona
            ctx.informe.cambios = True
            continue
        activos[tipo_de[u.clase]].append(u)
    for tipo, lista in activos.items():
        faltan = int(d.get(tipo, 0)) - len(lista)
        for _ in range(min(faltan, 3)):
            u = _nueva(ctx.esc, tipo, rng, ctx.terreno, al_borde=hubo[tipo])
            if u is None:
                break
            ctx.db.add(u)
            ctx.db.flush()
            ctx.unidades[u.id] = u
            ctx.lista.append(u)
            ctx.informe.cambios = True
        for u in lista[max(0, int(d.get(tipo, 0))):]:  # el director bajo la cantidad: se retiran los que sobran
            u.estado = "retirada"
            ctx.informe.cambios = True


def retirar_todo(db, esc) -> int:
    from app.models.unidad import Unidad

    n = 0
    for u in db.query(Unidad).filter(Unidad.escenario_id == esc.id, Unidad.estado == "activa", Unidad.bando == "neutral"):
        if es_civil(u):
            u.estado = "retirada"
            n += 1
    return n


def penalidad(perdidas_por_defensor: dict) -> int:
    """Puntos que pierde un bando por las unidades neutrales que ataco: {defensor_id: fuerza que le quito}."""
    return sum(PENALIDAD_ATAQUE + int(p // PENALIDAD_POR_FUERZA) for p in perdidas_por_defensor.values())


def zona_publica(esc) -> dict | None:
    d = config(esc)
    return {k: d[k] for k in ("aviones", "mercantes", "pesqueros", "zona", "aerovias") if k in d} if d.get("zona") else None
