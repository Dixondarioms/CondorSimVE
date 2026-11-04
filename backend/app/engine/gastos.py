"""Perdidas y gastos del Cóndor (como el informe de perdidas y gastos de los simuladores de mando modernos).

Cada disparo o siembra que gasta armas reales queda anotado (tabla gastos_armas): misiles y bombas de las aeronaves,
misiles antiaereos e interceptores antimisil, defensa de punto, misiles de crucero y balisticos, torpedos, sonoboyas,
minas, bengalas y señuelos. El informe del ejercicio (engine/aar.py) suma por bando lo gastado, las perdidas (aeronaves,
buques, unidades de tierra e instalaciones destruidas) y el combustible consumido.
"""

from __future__ import annotations

from app.engine import armas as armas_mod
from app.engine import catalogo, ota

TIPO_ARMA = {"aa": "Misiles aire-aire", "as": "Misiles aire-superficie", "ar": "Misiles antirradiación",
             "ab": "Misiles antibuque", "bomba": "Bombas", "helo": "Cohetes y cañón", "torp": "Torpedos"}
PERDIDAS = ("Aeronaves", "Buques", "Unidades de tierra", "Instalaciones")


def anotar(db, esc, u, tipo: str, arma: str, cantidad: int, t: float | None = None) -> None:
    """Deja constancia de `cantidad` armas gastadas por la unidad `u` (no anota nada si no gasto)."""
    from app.models.gasto import GastoArma  # importacion tardia: evita el ciclo con los modelos

    if u is None or cantidad <= 0:
        return
    db.add(GastoArma(escenario_id=esc.id, bando=u.bando, unidad_id=u.id, tipo=tipo, arma=str(arma)[:80],
                     cantidad=int(cantidad), turno=esc.turno_actual,
                     sim_segundos=t if t is not None else esc.sim_segundos))


def arma_aerea(db, esc, u, codigo: str, cantidad: int, t: float | None = None) -> None:
    """Misiles, bombas o cohetes de la carga de una aeronave (codigos de la OTA, engine/ota.py)."""
    nombre = ota.ARMAMENTO[codigo][0] if codigo in ota.ARMAMENTO else codigo
    anotar(db, esc, u, TIPO_ARMA.get(armas_mod.tipo(codigo), "Otras armas"), nombre, cantidad, t)


def _categoria(u) -> str | None:
    if catalogo.es_misil(u) or u.clase == "torpedo" or catalogo.obtener(u.clase, u.tipo).civil:
        return None
    if u.tipo == "base":
        return "Instalaciones"
    return {"aerea": "Aeronaves", "naval": "Buques"}.get(u.tipo, "Unidades de tierra")


def resumen(db, esc) -> dict:
    """Por bando: perdidas (aeronaves por cantidad de aviones, buques, unidades de tierra e instalaciones), armas gastadas
    por tipo y arma, y el combustible consumido (en tanques llenos, sumando el % que gasto cada unidad)."""
    from app.models.aar import RegistroLogistico
    from app.models.gasto import GastoArma
    from app.models.unidad import Unidad

    salida = {b: {"perdidas": {k: 0 for k in PERDIDAS}, "gastos": [], "combustible_tanques": 0.0} for b in ("azul", "rojo")}
    for u in db.query(Unidad).filter(Unidad.escenario_id == esc.id, Unidad.estado == "destruida"):
        cat = _categoria(u)
        if cat and u.bando in salida:
            salida[u.bando]["perdidas"][cat] += max(1, u.aeronaves or 1) if cat == "Aeronaves" else 1
    sumas: dict[tuple, int] = {}
    for g in db.query(GastoArma).filter(GastoArma.escenario_id == esc.id):
        if g.bando in salida:
            sumas[(g.bando, g.tipo, g.arma)] = sumas.get((g.bando, g.tipo, g.arma), 0) + g.cantidad
    for (b, tipo, arma), n in sorted(sumas.items()):
        salida[b]["gastos"].append({"tipo": tipo, "arma": arma, "cantidad": n})
    for r in db.query(RegistroLogistico).filter(RegistroLogistico.escenario_id == esc.id,
                                               RegistroLogistico.variable == "combustible"):
        if r.bando in salida and r.despues < r.antes:
            salida[r.bando]["combustible_tanques"] += (r.antes - r.despues) / 100.0
    for r in salida.values():
        r["combustible_tanques"] = round(r["combustible_tanques"], 1)
    return salida
