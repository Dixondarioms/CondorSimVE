"""Apoyo aereo de alto valor (HVA): reabastecimiento en vuelo con tiempos de transferencia y control aerotransportado
(AEW), con la escolta defensiva que exigen.

Reabastecimiento en vuelo: cada turno (60 min) la cisterna atiende, uno por uno, a los receptores propios en vuelo a
su alcance (primero los de menos combustible). Cada aeronave ocupa el tiempo de aproximacion y enganche
(CONTACTO_MIN) mas el de transferir lo que le falta a la tasa del sistema de la cisterna (pertiga ~2900 kg/min;
manguera y cesta ~1100 kg/min). Lo transferido sale de su carga transferible (ficha tecnica, 100 % = llena) y la
cisterna la recarga en una base aerea propia. Los que no alcanzan a pasar en el turno esperan al siguiente.

Escolta: la cisterna y el avion de alerta temprana son activos de alto valor; van con ESCOLTAS_MINIMAS cazas propios
a <= RADIO_ESCOLTA_KM. Sin esa escolta, ante cazas enemigos detectados a <= RADIO_AMENAZA_KM la cisterna suspende
el reabastecimiento (se repliega) y el control del AEW no se da.

Control aerotransportado: los cazas propios que interceptan a <= RADIO_CONTROL_AEW_KM de un AEW propio en vuelo
(escoltado) ganan FACTOR_CONTROL_AEW (vectoreo y alerta temprana).
"""

from __future__ import annotations

from app.engine import catalogo, geo, plataformas

MINUTOS_TURNO = 60.0
CONTACTO_MIN = 6.0  # aproximacion, enganche y separacion de cada receptor
TASA_KG_MIN = {"pertiga": 2900.0, "manguera": 1100.0}
SISTEMA_CISTERNA = {"kc135": "pertiga"}  # el resto: manguera y cesta (probe and drogue)
TRANSFERIBLE_POR_DEFECTO_KG = 30000.0
COMBUSTIBLE_POR_DEFECTO_KG = 5000.0
LLENO = 97.0  # por encima de esto no se reabastece
ESCOLTAS_MINIMAS = 2
RADIO_ESCOLTA_KM = 30.0
RADIO_AMENAZA_KM = 150.0
RADIO_CONTROL_AEW_KM = 300.0
FACTOR_CONTROL_AEW = 1.1


def es_cisterna(u) -> bool:
    c = catalogo.obtener(u.clase, u.tipo)
    return u.tipo == "aerea" and bool(c.nodo_movil_km) and "aerea" in c.suministra


def es_aew(u) -> bool:
    return u.tipo == "aerea" and (u.clase or "") == "alerta_temprana"


def en_vuelo(u) -> bool:
    return u.tipo == "aerea" and u.estado == "activa" and not u.en_tierra


def aeronaves_efectivas(u) -> int:
    return max(1, round(max(1, int(u.aeronaves or 1)) * max(0.0, u.fuerza or 0.0) / 100.0))


def tasa(cisterna) -> float:
    return TASA_KG_MIN[SISTEMA_CISTERNA.get(cisterna.modelo or "", "manguera")]


def transferible_kg(cisterna) -> float:
    f = plataformas.ficha(cisterna)
    return float(f.transferible_kg) if f is not None and f.transferible_kg else TRANSFERIBLE_POR_DEFECTO_KG


def capacidad_kg(u) -> float:
    f = plataformas.ficha(u)
    return float(f.combustible_kg) if f is not None and f.combustible_kg else COMBUSTIBLE_POR_DEFECTO_KG


def minutos_por_aeronave(cisterna_tasa: float, kg: float) -> float:
    return CONTACTO_MIN + max(0.0, kg) / cisterna_tasa


def escoltas(hva, unidades) -> int:
    """Cazas propios en vuelo junto al activo de alto valor."""
    return sum(aeronaves_efectivas(x) for x in unidades
               if x is not hva and x.bando == hva.bando and en_vuelo(x) and not catalogo.es_misil(x)
               and catalogo.perfil(x).ataque_vs.get("aerea", 0.0) > 0
               and geo.distancia_km(hva.lat, hva.lon, x.lat, x.lon) <= RADIO_ESCOLTA_KM)


def amenaza(hva, unidades, visible) -> object | None:
    """Caza enemigo en vuelo detectado por el bando cerca del activo de alto valor (None si no hay)."""
    cerca = [x for x in unidades
             if x.bando != hva.bando and en_vuelo(x) and not catalogo.es_misil(x)
             and catalogo.perfil(x).ataque_vs.get("aerea", 0.0) > 0
             and geo.distancia_km(hva.lat, hva.lon, x.lat, x.lon) <= RADIO_AMENAZA_KM and visible(x, hva.bando)]
    return min(cerca, key=lambda x: geo.distancia_km(hva.lat, hva.lon, x.lat, x.lon), default=None)


def protegido(hva, unidades, visible) -> tuple[bool, str]:
    """(puede operar, motivo): sin la escolta minima y con una amenaza aerea detectada, no opera."""
    n = escoltas(hva, unidades)
    if n >= ESCOLTAS_MINIMAS:
        return True, ""
    x = amenaza(hva, unidades, visible)
    if x is None:
        return True, ""
    return False, (f"{hva.nombre} se repliega: {x.nombre} a {geo.distancia_km(hva.lat, hva.lon, x.lat, x.lon):.0f} km "
                   f"y solo {n} de {ESCOLTAS_MINIMAS} escoltas.")


def reabastecer(cisterna, unidades, bit, visible) -> dict:
    """Reabastecimiento en vuelo de un turno. Devuelve {receptores: [(nombre, aeronaves, kg)], kg, minutos, motivo}."""
    out = {"receptores": [], "kg": 0.0, "minutos": 0.0, "motivo": ""}
    if not en_vuelo(cisterna):
        return out
    clase = catalogo.obtener(cisterna.clase, cisterna.tipo)
    ok, motivo = protegido(cisterna, unidades, visible)
    if not ok:
        out["motivo"] = motivo
        return out
    total = transferible_kg(cisterna)
    disponible = max(0.0, cisterna.carga or 0.0) / 100.0 * total
    v = tasa(cisterna)
    minutos = MINUTOS_TURNO
    receptores = sorted(
        (r for r in unidades
         if r is not cisterna and r.bando == cisterna.bando and en_vuelo(r) and not catalogo.es_misil(r)
         and not catalogo.obtener(r.clase, r.tipo).se_consume and not es_cisterna(r) and (r.combustible or 0) < LLENO
         and geo.distancia_km(cisterna.lat, cisterna.lon, r.lat, r.lon) <= clase.nodo_movil_km),
        key=lambda r: (r.combustible, r.id))
    for r in receptores:
        if disponible <= 1 or minutos < CONTACTO_MIN + 1:
            break
        n = aeronaves_efectivas(r)
        cap = capacidad_kg(r)
        falta_ac = (100.0 - r.combustible) / 100.0 * cap
        por_ac = minutos_por_aeronave(v, falta_ac)
        atendidas = min(n, int(minutos // por_ac))
        kg_ac = falta_ac
        if atendidas == 0:  # no alcanza el tiempo para llenar una: se le pasa lo que entra en el tiempo que queda
            atendidas, kg_ac = 1, max(0.0, (minutos - CONTACTO_MIN) * v)
            por_ac = minutos
        kg = min(disponible, kg_ac * atendidas)
        if kg <= 1:
            continue
        sube = kg / (cap * n) * 100.0  # el combustible del grupo es el promedio de sus aeronaves
        bit.poner(r, "combustible", min(100.0, r.combustible + sube), "reabastecimiento en vuelo")
        disponible -= kg
        minutos -= min(minutos, por_ac * atendidas)
        out["receptores"].append((r.nombre, atendidas, round(kg)))
        out["kg"] += kg
    if out["kg"] > 0:
        bit.poner(cisterna, "carga", max(0.0, (cisterna.carga or 0.0) - out["kg"] / total * 100.0), "reabastecimiento en vuelo")
    out["minutos"] = round(MINUTOS_TURNO - minutos)
    return out


def factor_control(atacante, blanco, unidades, visible) -> float:
    """Intercepcion dirigida por un AEW propio en vuelo, escoltado o sin amenaza cerca."""
    if atacante.tipo != "aerea" or blanco.tipo != "aerea" or not en_vuelo(blanco):
        return 1.0
    for a in unidades:
        if (a.bando == atacante.bando and es_aew(a) and en_vuelo(a)
                and geo.distancia_km(a.lat, a.lon, atacante.lat, atacante.lon) <= RADIO_CONTROL_AEW_KM
                and protegido(a, unidades, visible)[0]):
            return FACTOR_CONTROL_AEW
    return 1.0


def estimar_aar(modelo, aeronaves: int, combustible_llegada_pct: float, sistema: str = "manguera") -> dict:
    """Para la planificacion: kg a transferir y minutos de la cisterna para llenar el grupo en el punto de
    reabastecimiento."""
    f = plataformas.ficha_de_modelo(modelo)
    cap = float(f.combustible_kg) if f is not None and f.combustible_kg else COMBUSTIBLE_POR_DEFECTO_KG
    n = max(1, int(aeronaves or 1))
    kg_ac = max(0.0, 100.0 - combustible_llegada_pct) / 100.0 * cap
    v = TASA_KG_MIN[sistema]
    return {"kg": round(kg_ac * n), "kg_por_aeronave": round(kg_ac), "minutos": round(n * minutos_por_aeronave(v, kg_ac)),
            "tasa_kg_min": v, "contacto_min": CONTACTO_MIN}
