"""Puntos medios de impacto (PMI) sobre las pistas enemigas: Operaciones (A-3) los pide e Inteligencia (A-2) los
entrega (routers/pmi.py).

Para inutilizar una pista no hace falta destruirla entera: alcanza con cortarla en tramos mas cortos que la carrera
de despegue de un caza (la franja minima de operacion, MOS_M). Inteligencia ubica los PMI sobre el eje de la pista,
repartidos para que ningun tramo sano llegue a MOS_M, con la pista real del plano del aerodromo (engine/plataformas.py;
sin plano, una pista estimada centrada en la base). Con los PMI entregados, el ataque a la pista de esa base hace todo
su daño; sin ellos, las bombas caen dispersas y solo hacen FACTOR_SIN_PMI del daño a la pista (engine/tiempo_real.py).
"""

from __future__ import annotations

import json
import math

from app.engine import catalogo, geo, plataformas

MOS_M = 800.0  # franja minima de operacion: carrera de despegue de un caza cargado (ningun tramo sano debe llegar)
FACTOR_SIN_PMI = 0.5  # daño a la pista de un ataque sin los PMI de Inteligencia
MAX_PUNTOS = 12
RADIO_MAX_KM = 3.0  # un PMI ajustado a mano no puede quedar a mas de esto de la base
RUMBO_ESTIMADO = 90.0  # pista sin plano: este-oeste, centrada en la base


def es_base_con_pista(u) -> bool:
    return u is not None and getattr(u, "clase", "") == "base_aerea"


def pista_de(base) -> dict:
    """La pista sobre la que se calculan los PMI: la del plano del aerodromo o una estimada (con `estimada`)."""
    plano = plataformas.pista_con_extremos(base.lat, base.lon)
    if plano:
        return {"ref": plano.get("ref") or "", "largo_m": float(plano.get("largo_m") or 0.0), "ancho_m": float(plano.get("ancho_m") or 45.0),
                "rumbo": float(plano.get("rumbo") or 0.0), "extremos": plano["extremos"], "estimada": False}
    largo = plataformas.largo_pista(base) or plataformas.PISTA_POR_DEFECTO_M
    a = geo.destino(base.lat, base.lon, (RUMBO_ESTIMADO + 180.0) % 360.0, largo / 2000.0)
    b = geo.destino(base.lat, base.lon, RUMBO_ESTIMADO, largo / 2000.0)
    return {"ref": "", "largo_m": float(largo), "ancho_m": 45.0, "rumbo": RUMBO_ESTIMADO,
            "extremos": [list(a), list(b)], "estimada": True}


def cortes(largo_m: float) -> int:
    """Cuantos cortes hacen falta para que ningun tramo sano llegue a la franja minima de operacion."""
    return max(1, math.ceil(largo_m / MOS_M) - 1)


def proponer(base) -> tuple[list[dict], dict]:
    """PMI propuestos sobre el eje de la pista, repartidos en partes iguales, y la pista usada."""
    pista = pista_de(base)
    (la, loa), (lb, lob) = pista["extremos"]
    n = cortes(pista["largo_m"])
    tramo = pista["largo_m"] / (n + 1)
    puntos = []
    for k in range(1, n + 1):
        f = k / (n + 1)
        puntos.append({
            "id": f"PMI-{k:02d}", "lat": round(la + (lb - la) * f, 6), "lon": round(loa + (lob - loa) * f, 6),
            "nota": f"Corte {k} de {n} sobre el eje de la pista, a {f * pista['largo_m']:.0f} m de la cabecera",
        })
    pista["tramo_m"] = round(tramo)
    return puntos, pista


def validar(puntos: list[dict], base) -> str | None:
    """Motivo por el que los PMI no sirven (None si sirven)."""
    if not puntos:
        return "Indique al menos un punto medio de impacto."
    if len(puntos) > MAX_PUNTOS:
        return f"A lo sumo {MAX_PUNTOS} puntos medios de impacto por pista."
    for p in puntos:
        lat, lon = p.get("lat"), p.get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return "Coordenadas fuera de rango."
        if geo.distancia_km(base.lat, base.lon, lat, lon) > RADIO_MAX_KM:
            return f"{p.get('id') or 'Un punto'} queda a más de {RADIO_MAX_KM:.0f} km de {base.nombre}: no está sobre su pista."
    return None


def normalizar(puntos: list[dict]) -> list[dict]:
    return [{"id": (str(p.get("id") or f"PMI-{i + 1:02d}"))[:12], "lat": round(float(p["lat"]), 6), "lon": round(float(p["lon"]), 6),
             "nota": str(p.get("nota") or "")[:120]} for i, p in enumerate(puntos)]


def entregados(db, escenario_id: int) -> set[tuple[str, int]]:
    """(bando, base) con PMI entregados por Inteligencia."""
    from app.models.pmi import PedidoPmi

    return {(p.bando, p.base_id) for p in db.query(PedidoPmi).filter(PedidoPmi.escenario_id == escenario_id,
                                                                      PedidoPmi.estado == "entregado")}


def factor_pista(bando: str, base_id: int, con_pmi: set) -> float:
    """Fraccion del daño a la pista que hace un ataque de ese bando a esa base."""
    return 1.0 if (bando, base_id) in con_pmi else FACTOR_SIN_PMI


def serializar(p, base) -> dict:
    return {
        "id": p.id, "bando": p.bando, "base_id": p.base_id, "base_nombre": base.nombre if base is not None else f"#{p.base_id}",
        "estado": p.estado, "pedido_por": p.pedido_por, "entregado_por": p.entregado_por, "turno": p.turno,
        "puntos": json.loads(p.puntos_json or "[]"), "pista": json.loads(p.pista_json or "{}"), "nota": p.nota,
        "pedido_seg": p.pedido_seg, "entregado_seg": p.entregado_seg,
        "destruida": base is None or base.estado == "destruida",
        "es_base": base is not None and catalogo.opera_aeronaves(base),
    }


def bases_conocidas(db, escenario, rol: str) -> list[dict]:
    """Bases aereas enemigas a las que se les pueden pedir PMI: se conocen de antemano (inteligencia previa, como las
    trata engine/contactos_vivo.py), aunque el bando no las tenga a la vista. Solo el id y el nombre."""
    from app.models.unidad import Unidad

    if rol not in ("azul", "rojo"):
        return []
    q = db.query(Unidad).filter(Unidad.escenario_id == escenario.id, Unidad.bando != rol, Unidad.clase == "base_aerea",
                                Unidad.estado != "destruida")
    return [{"id": u.id, "nombre": u.nombre} for u in q.order_by(Unidad.nombre)]


def visibles_para(db, escenario, rol: str) -> list[dict]:
    """Pedidos del bando (el instructor y el observador ven los de los dos), de los mas nuevos a los mas viejos."""
    from app.models.pmi import PedidoPmi
    from app.models.unidad import Unidad

    q = db.query(PedidoPmi).filter(PedidoPmi.escenario_id == escenario.id, PedidoPmi.estado != "cancelado")
    if rol in ("azul", "rojo"):
        q = q.filter(PedidoPmi.bando == rol)
    return [serializar(p, db.get(Unidad, p.base_id)) for p in q.order_by(PedidoPmi.id.desc()).limit(40)]
