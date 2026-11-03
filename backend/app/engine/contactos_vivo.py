"""Contactos del Cóndor: clasificacion por etapas e incertidumbre de la posicion (como en los simuladores de mando
modernos).

Cada bando sigue a cada enemigo que detecta y junta puntos de seguimiento mientras lo tiene a la vista: con radar y de
cerca, rapido; de lejos, lento; solo por escucha electronica, mas lento todavia y sin pasar de clasificado.
- desconocido: se sabe que hay algo (en el aire o en superficie), no que es;
- clasificado: se conoce la clase (caza, buque, bateria antiaerea...), no la unidad;
- identificado: se conoce la unidad. Recien entonces le tiran las armas en estado restringido (engine/doctrina.py).
La etapa no se pierde al perder el contacto. A menos de IDENTIFICACION_VISUAL_KM se identifica a ojo, en el acto; las
bases y la infraestructura fija se conocen de antemano.

El trafico civil (engine/trafico.py) emite su transpondedor (o el AIS de los buques): seguido por radar se clasifica
como civil en unos minutos (TASA_TRANSPONDEDOR).

La posicion que ve el bando cae dentro de un circulo de incertidumbre: chico con radar de cerca, grande de lejos o solo
por escucha. Si se pierde el contacto, el circulo crece con lo que la unidad pudo moverse desde que se la vio.
Las pistas viven en memoria (Mundo.pistas) y se guardan con los contactos (Contacto.etapa, puntos, incertidumbre_km)
para rehacerse si el servidor se reinicia.
"""

import math
import random

from app.engine import catalogo, geo, relieve, vision

ETAPAS = ("desconocido", "clasificado", "identificado")
NOMBRES_ETAPA = {"desconocido": "Desconocido", "clasificado": "Clasificado", "identificado": "Identificado"}
PUNTOS_CLASIFICADO = 3.0
PUNTOS_IDENTIFICADO = 10.0
IDENTIFICACION_VISUAL_KM = 8.0
TASA_ESCUCHA = 0.15  # puntos por minuto solo por escucha electronica
INCERTIDUMBRE_MIN_KM = 0.2
INCERTIDUMBRE_ESCUCHA_MIN_KM = 3.0
INCERTIDUMBRE_MAX_KM = 100.0
TASA_TRANSPONDEDOR = 1.2  # puntos por minuto de un avion o buque civil seguido por radar: se clasifica en ~2,5 min
ACTUALIZAR_CADA_S = 30.0  # cada cuanto tiempo simulado se suman puntos (el seguimiento es lento: no hace falta mas)
DESPLAZAR_CADA_S = 120.0  # cada cuanto cambia la posicion aproximada dentro del circulo


def _mundo(esc):
    from app.engine.tiempo_real import mundo_de  # importacion tardia: el motor importa este modulo

    return mundo_de(esc.id)


def fija(u) -> bool:
    """Bases e infraestructura fija: se conocen de antemano (inteligencia previa)."""
    return u.tipo == "base" or bool(catalogo.obtener(u.clase, u.tipo).infraestructura)


def cargar(db, esc, m=None) -> dict:
    """Pistas del escenario (de memoria; la primera vez, de los contactos guardados)."""
    m = m or _mundo(esc)
    if not m.pistas_cargadas:
        from app.models.contacto import Contacto

        for c in db.query(Contacto).filter(Contacto.escenario_id == esc.id, Contacto.etapa.isnot(None)):
            m.pistas.setdefault((c.bando, c.unidad_id), {"puntos": c.puntos or 0.0, "etapa": c.etapa,
                                                         "inc": c.incertidumbre_km, "visto": None})
        m.pistas_cargadas = True
    return m.pistas


def _medicion(detectores, x, terreno, clima, ge):
    """(puntos por minuto, incertidumbre en km, a ojo, solo por escucha) de la mejor deteccion del bando sobre `x`."""
    tasa, inc, visual, radar = 0.0, None, False, False
    for d in detectores:
        dist = geo.distancia_km(d.lat, d.lon, x.lat, x.lon)
        r = vision.radio_efectivo(d, x, terreno, clima, ge)
        if dist <= r and relieve.linea_de_vista(terreno, d, x):
            frac = 1.0 - dist / r if r > 0 else 1.0
            tasa = max(tasa, 0.3 + 1.7 * frac)
            i = max(INCERTIDUMBRE_MIN_KM, dist * (0.01 + 0.04 * (1.0 - frac)))
            radar = True
            visual = visual or dist <= IDENTIFICACION_VISUAL_KM
        elif vision.escucha(d, x, ge, terreno):
            tasa = max(tasa, TASA_ESCUCHA)
            i = max(INCERTIDUMBRE_ESCUCHA_MIN_KM, 0.2 * dist)
        else:
            continue
        inc = i if inc is None else min(inc, i)
    if inc is None:  # se lo ve sin un detector propio que lo mida (un interferidor que se delata al emitir)
        cerca = min((geo.distancia_km(d.lat, d.lon, x.lat, x.lon) for d in detectores), default=50.0)
        tasa, inc = TASA_ESCUCHA, max(INCERTIDUMBRE_ESCUCHA_MIN_KM, 0.2 * cerca)
    return tasa, min(inc, INCERTIDUMBRE_MAX_KM), visual, not radar


def _etapa_por_puntos(puntos: float) -> str:
    return "identificado" if puntos >= PUNTOS_IDENTIFICADO else "clasificado" if puntos >= PUNTOS_CLASIFICADO else "desconocido"


def actualizar(ctx, bando: str, ids: set) -> None:
    """Suma puntos de seguimiento a los enemigos que el bando ve ahora y sube su etapa (desde _detectar)."""
    m = ctx.mundo
    pistas = cargar(ctx.db, ctx.esc, m)
    antes = m.pistas_en.get(bando)
    if antes is not None and 0 <= ctx.t - antes < ACTUALIZAR_CADA_S and all((bando, i) in pistas for i in ids):
        return
    minutos = (ctx.t - antes) / 60.0 if antes is not None and ctx.t >= antes else 0.0
    m.pistas_en[bando] = ctx.t
    detectores = [d for d in ctx.lista if d.bando == bando and d.estado == "activa" and d.transporte_id is None]
    for uid in ids:
        x = ctx.unidades.get(uid)
        if x is None:
            continue
        p = pistas.get((bando, uid))
        nueva = p is None
        if nueva:
            p = pistas[(bando, uid)] = {"puntos": 0.0, "etapa": "desconocido", "inc": None, "visto": ctx.t}
        previa = p["etapa"]
        if fija(x):
            p.update(etapa="identificado", inc=0.0, visto=ctx.t)
            continue
        tasa, inc, visual, solo_escucha = _medicion(detectores, x, ctx.terreno, ctx.clima, ctx.ge)
        if not solo_escucha and catalogo.obtener(x.clase, x.tipo).civil:
            tasa = max(tasa, TASA_TRANSPONDEDOR)  # el transpondedor (o el AIS de un buque) lo delata como civil
        if not nueva:
            p["puntos"] = min(PUNTOS_IDENTIFICADO, p["puntos"] + tasa * minutos)
        etapa = _etapa_por_puntos(p["puntos"])
        if solo_escucha and etapa == "identificado":
            etapa = "clasificado"  # la escucha dice que emisor es, no que unidad lo lleva
        if visual and not solo_escucha:
            etapa = "identificado"
        if ETAPAS.index(etapa) > ETAPAS.index(previa):
            p["etapa"] = etapa
            ctx.informe.cambios = True
            if not nueva:
                clase = catalogo.obtener(x.clase, x.tipo).nombre
                ctx.evento("radar", bando, f"Contacto identificado: {x.nombre} ({clase.lower()})." if etapa == "identificado"
                           else f"Contacto clasificado: {clase.lower()}.")
        p["inc"], p["visto"] = inc, ctx.t


def a_ojo(unidades, bando: str, x, terreno) -> bool:
    """Alguna unidad propia lo tiene a la vista a menos de IDENTIFICACION_VISUAL_KM (se identifica en el acto)."""
    return any(d.bando == bando and d.estado == "activa" and d.transporte_id is None
               and geo.distancia_km(d.lat, d.lon, x.lat, x.lon) <= IDENTIFICACION_VISUAL_KM
               and relieve.linea_de_vista(terreno, d, x) for d in unidades)


def identificado(ctx, bando: str, x) -> bool:
    """El bando ve a `x` y lo tiene identificado (las propias y, sin niebla de guerra, todo lo visible, tambien)."""
    if not ctx.visible_para(x, bando):
        return False
    if x.bando == bando or not ctx.esc.niebla or fija(x):
        return True
    p = cargar(ctx.db, ctx.esc, ctx.mundo).get((bando, x.id))
    return p is not None and p["etapa"] == "identificado"


def pista(db, esc, bando: str, uid: int) -> dict | None:
    return cargar(db, esc).get((bando, uid))


def incertidumbre(p: dict | None, u, t: float, perdido: bool = False) -> float:
    """Radio del circulo de incertidumbre (km); perdido el contacto, crece con lo que la unidad pudo moverse."""
    if p is None:
        return 0.0
    inc = p.get("inc") or 0.0
    if perdido and p.get("visto") is not None and t > p["visto"] and not fija(u):
        inc += (u.velocidad_kmh or 0.0) * (t - p["visto"]) / 3600.0
    return round(min(inc, INCERTIDUMBRE_MAX_KM), 2)


def aproximar(semilla: int, bando: str, uid: int, lat: float, lon: float, inc_km: float, t: float) -> tuple[float, float]:
    """Posicion aproximada dentro del circulo (al azar, pero la misma para todos durante DESPLAZAR_CADA_S)."""
    if inc_km <= 0:
        return lat, lon
    rng = random.Random(f"{semilla}:{bando}:{uid}:{int(t // DESPLAZAR_CADA_S)}")
    ang = rng.random() * 2.0 * math.pi
    r = inc_km * math.sqrt(rng.random())
    dlat = r * math.cos(ang) / 111.32
    dlon = r * math.sin(ang) / (111.32 * max(0.1, math.cos(math.radians(lat))))
    return lat + dlat, lon + dlon


def generico(u) -> str:
    return "Contacto aéreo desconocido" if u.tipo == "aerea" else "Contacto de superficie desconocido"


def enmascarar(d: dict, u, etapa: str) -> None:
    """Quita del dato de la unidad enemiga lo que el bando todavia no sabe de ella (segun la etapa)."""
    d["etapa"] = etapa
    if etapa == "identificado":
        return
    clase = catalogo.obtener(u.clase, u.tipo)
    d["modelo"] = None
    if etapa == "clasificado":
        d["nombre"] = f"{clase.nombre} (sin identificar)"
        return
    d["nombre"] = generico(u)
    d["clase"] = None
    d["echelon"] = ""
    d["aeronaves"] = None
    sidc = d.get("sidc") or "SHGP"
    d["sidc"] = f"SU{sidc[2] if len(sidc) > 2 else 'G'}P"
