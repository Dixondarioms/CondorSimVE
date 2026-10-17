"""Inteligencia: pasadas de satelite con su tiempo de procesamiento e informes automaticos (INTSUM) del A-2.

Satelites: cada bando puede tener hasta MAX_SATELITES (lo fija el instructor), opticos o radar (SAR). Cada satelite
pasa cada REVISITA_TURNOS (dos veces por dia), con un desfase propio, por una franja norte-sur de ANCHO_FRANJA_KM a
cada lado de su traza (la traza cambia en cada pasada). Fotografia las unidades enemigas de superficie y las
aeronaves en tierra dentro de la franja; el optico no ve de noche ni bajo nubes, lluvia o tormenta; el radar, si.
Las imagenes tardan PROCESAMIENTO_TURNOS en procesarse: el turno siguiente el bando recibe el informe y los contactos
con la posicion que tenian al momento de la pasada.

INTSUM: cada REPORTE_TURNOS el A-2 de cada bando recibe un resumen automatico: contactos enemigos conocidos por rama y
lo recientes que son, las amenazas cerca de sus bases aereas, las pasadas de satelite y lo que se sabe del enemigo
por anillos de Warden.
"""

from __future__ import annotations

import hashlib
import json
import math
import random

from app.engine import catalogo, geo, warden
from app.engine import clima as clima_mod

MAX_SATELITES = 4
TIPOS = ("optico", "radar")
REVISITA_TURNOS = 12
ANCHO_FRANJA_KM = 120.0
DESPLAZAMIENTO_TRAZA_KM = 300.0
PROCESAMIENTO_TURNOS = 1
REPORTE_TURNOS = 6
RADIO_AMENAZA_BASE_KM = 150.0
POR_DEFECTO = {"satelites": 0, "tipo": "optico"}
NO_VE_OPTICO = ("lluvia", "tormenta", "nublado")


def _rng(escenario, *claves) -> random.Random:
    h = hashlib.sha256(":".join(str(c) for c in (getattr(escenario, "semilla", 0), "intel", *claves)).encode()).digest()
    return random.Random(int.from_bytes(h[:8], "big"))


def _datos(escenario) -> dict:
    try:
        d = json.loads(getattr(escenario, "inteligencia_json", None) or "{}")
    except ValueError:
        d = {}
    return d if isinstance(d, dict) else {}


def config(escenario, bando: str) -> dict:
    return {**POR_DEFECTO, **(_datos(escenario).get(bando) or {})}


def configurar(escenario, bando: str, satelites: int | None = None, tipo: str | None = None) -> dict:
    d = _datos(escenario)
    c = config(escenario, bando)
    if satelites is not None:
        c["satelites"] = max(0, min(MAX_SATELITES, int(satelites)))
    if tipo in TIPOS:
        c["tipo"] = tipo
    d[bando] = c
    escenario.inteligencia_json = json.dumps(d)
    return c


def pasadas(escenario, bando: str, turno: int) -> list[int]:
    """Indices de los satelites del bando que pasan en este turno."""
    n = int(config(escenario, bando)["satelites"] or 0)
    return [i for i in range(n) if (turno + i * (REVISITA_TURNOS // max(1, n)) + (0 if bando == "azul" else 3)) % REVISITA_TURNOS == 0]


def traza(escenario, bando: str, i: int, turno: int, unidades) -> float:
    """Longitud de la traza de la pasada: cerca del centro del teatro, corrida al azar."""
    if not unidades:
        return 0.0
    lon0 = sum(u.lon for u in unidades) / len(unidades)
    lat0 = sum(u.lat for u in unidades) / len(unidades)
    km = _rng(escenario, bando, i, turno).uniform(-DESPLAZAMIENTO_TRAZA_KM, DESPLAZAMIENTO_TRAZA_KM)
    return lon0 + km / (111.32 * max(0.2, abs(math.cos(math.radians(lat0)))))


def fotografiar(escenario, bando: str, turno: int, unidades, clima) -> list[dict]:
    """Lo que ven las pasadas del turno: [{unidad_id, lat, lon, nombre, clase, satelite}]."""
    tipo = config(escenario, bando)["tipo"]
    noche = getattr(clima, "periodo", "dia") == "noche"
    out, vistos = [], set()
    for i in pasadas(escenario, bando, turno):
        lon_t = traza(escenario, bando, i, turno, unidades)
        for u in unidades:
            if u.bando == bando or u.estado == "destruida" or u.id in vistos:
                continue
            if u.tipo == "aerea" and not u.en_tierra:
                continue
            if catalogo.obtener(u.clase, u.tipo).dron and u.tipo == "aerea":
                continue
            if geo.distancia_km(u.lat, lon_t, u.lat, u.lon) > ANCHO_FRANJA_KM:
                continue
            if tipo == "optico" and (noche or clima_mod.resolver(clima, u.lat, u.lon) in NO_VE_OPTICO):
                continue
            vistos.add(u.id)
            out.append({"unidad_id": u.id, "lat": round(u.lat, 4), "lon": round(u.lon, 4), "nombre": u.nombre,
                        "clase": u.clase or u.tipo, "satelite": i + 1})
    return out


def registrar_pasadas(escenario, turno: int, unidades, clima) -> None:
    """Guarda las imagenes del turno para entregarlas procesadas mas adelante."""
    d = _datos(escenario)
    pendientes = d.get("pendientes", [])
    for b in ("azul", "rojo"):
        if not pasadas(escenario, b, turno):
            continue
        tomas = fotografiar(escenario, b, turno, unidades, clima)
        pendientes.append({"bando": b, "turno": turno, "listo": turno + PROCESAMIENTO_TURNOS, "tomas": tomas,
                           "pasadas": len(pasadas(escenario, b, turno)), "tipo": config(escenario, b)["tipo"]})
    d["pendientes"] = pendientes
    escenario.inteligencia_json = json.dumps(d)


def entregar(escenario, turno: int) -> list[dict]:
    """Las imagenes que terminaron de procesarse este turno (y las quita de pendientes)."""
    d = _datos(escenario)
    listas = [p for p in d.get("pendientes", []) if p["listo"] <= turno]
    if listas:
        d["pendientes"] = [p for p in d.get("pendientes", []) if p["listo"] > turno]
        d.setdefault("historial", []).extend({k: v for k, v in p.items() if k != "tomas"} | {"vistas": len(p["tomas"])}
                                             for p in listas)
        d["historial"] = d["historial"][-40:]
        escenario.inteligencia_json = json.dumps(d)
    return listas


def texto_entrega(p: dict) -> str:
    n = len(p["tomas"])
    sat = "satélite óptico" if p["tipo"] == "optico" else "satélite radar"
    if not n:
        return (f"Inteligencia de imágenes ({sat}, pasada del T{p['turno']}): sin unidades enemigas en la franja "
                f"fotografiada{' (nubes o noche)' if p['tipo'] == 'optico' else ''}.")
    por_clase: dict[str, int] = {}
    for t in p["tomas"]:
        por_clase[t["clase"]] = por_clase.get(t["clase"], 0) + 1
    detalle = ", ".join(f"{k} {v}" for k, v in sorted(por_clase.items(), key=lambda x: -x[1]))
    return (f"Inteligencia de imágenes ({sat}, pasada del T{p['turno']}, procesada): {n} unidad(es) enemiga(s) "
            f"localizadas ({detalle}). Sus posiciones son las de la hora de la pasada.")


def intsum(bando: str, turno: int, contactos: list, unidades_por_id: dict, propias: list, entregas: int) -> str:
    """Informe de inteligencia periodico del bando (texto)."""
    recientes = [c for c in contactos if turno - c.turno_visto <= REPORTE_TURNOS]
    ramas: dict[str, int] = {}
    for c in recientes:
        u = unidades_por_id.get(c.unidad_id)
        if u is None:
            continue
        ramas[u.tipo] = ramas.get(u.tipo, 0) + 1
    nombres = {"terrestre": "terrestres", "aerea": "aéreas", "naval": "navales", "base": "instalaciones"}
    partes = [f"{v} {nombres.get(k, k)}" for k, v in sorted(ramas.items())]
    bases = [b for b in propias if catalogo.opera_aeronaves(b) and b.tipo == "base" and b.estado == "activa"]
    amenazas = []
    for b in bases:
        cerca = [c for c in recientes if geo.distancia_km(b.lat, b.lon, c.lat, c.lon) <= RADIO_AMENAZA_BASE_KM]
        if cerca:
            amenazas.append(f"{b.nombre} ({len(cerca)} a {RADIO_AMENAZA_BASE_KM:.0f} km o menos)")
    conocidos = [(unidades_por_id[c.unidad_id], c in recientes) for c in contactos if c.unidad_id in unidades_por_id]
    anillos = [f"anillo {f['anillo']}: {f['objetivos']}" for f in warden.resumen(conocidos, bando) if f["objetivos"]]
    return (f"INTSUM T{turno} (A-2): contactos enemigos de las últimas {REPORTE_TURNOS} h: "
            f"{', '.join(partes) if partes else 'ninguno'}; total conocidos {len(contactos)}. "
            f"Amenazas cerca de bases aéreas propias: {'; '.join(amenazas) if amenazas else 'ninguna'}. "
            f"Objetivos conocidos por anillo de Warden: {', '.join(anillos) if anillos else 'ninguno'}. "
            f"Informes de imágenes recibidos en el período: {entregas}.")


def resumen(escenario, bando: str) -> dict:
    d = _datos(escenario)
    return {"config": config(escenario, bando),
            "pendientes": [{"turno": p["turno"], "listo": p["listo"]} for p in d.get("pendientes", []) if p["bando"] == bando],
            "historial": [p for p in d.get("historial", []) if p["bando"] == bando][-10:],
            "revisita_turnos": REVISITA_TURNOS, "procesamiento_turnos": PROCESAMIENTO_TURNOS}


def procesar_turno(db, escenario) -> None:
    """Al cerrar la resolucion: pasadas de satelite del turno, imagenes procesadas (contactos e informes) e INTSUM."""
    from app.models.contacto import Contacto  # importacion tardia: los modelos no dependen del motor
    from app.models.evento import Evento
    from app.models.unidad import Unidad

    turno = escenario.turno_actual
    unidades = db.query(Unidad).filter(Unidad.escenario_id == escenario.id).all()
    por_id = {u.id: u for u in unidades}
    registrar_pasadas(escenario, turno, unidades, clima_mod.contexto(db, escenario))
    entregadas = entregar(escenario, turno)
    for p in entregadas:
        existentes = {c.unidad_id: c for c in db.query(Contacto).filter(Contacto.escenario_id == escenario.id,
                                                                         Contacto.bando == p["bando"])}
        for t in p["tomas"]:
            if t["unidad_id"] not in por_id or por_id[t["unidad_id"]].estado == "destruida":
                continue
            c = existentes.get(t["unidad_id"])
            if c is None:
                db.add(Contacto(escenario_id=escenario.id, bando=p["bando"], unidad_id=t["unidad_id"], lat=t["lat"],
                                lon=t["lon"], turno_visto=p["turno"]))
            elif c.turno_visto < p["turno"]:
                c.lat, c.lon, c.turno_visto = t["lat"], t["lon"], p["turno"]
        db.add(Evento(escenario_id=escenario.id, turno=turno, tipo="inteligencia", bando_destino=p["bando"],
                      descripcion=texto_entrega(p)))
    if turno % REPORTE_TURNOS == 0:
        db.flush()
        d = _datos(escenario)
        for b in ("azul", "rojo"):
            contactos = db.query(Contacto).filter(Contacto.escenario_id == escenario.id, Contacto.bando == b).all()
            recibidas = sum(1 for h in d.get("historial", []) if h["bando"] == b and turno - h["listo"] < REPORTE_TURNOS)
            propias = [u for u in unidades if u.bando == b]
            db.add(Evento(escenario_id=escenario.id, turno=turno, tipo="inteligencia", bando_destino=b,
                          descripcion=intsum(b, turno, contactos, por_id, propias, recibidas)))
