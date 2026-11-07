"""Calculo de armamento (weaponeering), radio de escombros (dano colateral) y evaluacion de danos (BDA) en 3 niveles.

Metodo del documento "Targeting and Weaponeering" de la AMB: el area media de efecto (MAE) de cada bomba segun el
blanco, el criterio de dano y el angulo de impacto; se cubre el area de cada punto deseado de impacto (DMPI) con
los circulos de efecto (EFICIENCIA_COBERTURA = 0,3 reproduce el ejemplo del documento: un area de aviones
estacionados de 200 x 120 m, "imposibilita el despegue", MK-82 a 45 grados -> 6 bombas en el blanco) y se corrige
por la dispersion y la confiabilidad: x3 las armas no guiadas (6 -> 18 MK-82 a lanzar, como en el ejemplo) y x1,25
las guiadas. Las armas que no figuran en la tabla (rusas, misiles, cohetes) se asimilan a la bomba de efecto
parecido. Los radios de escombros son los del documento (MK-81 85 m, GBU-12 110 m, GBU-24 180 m, MK-82 240 m); los
de la MK-83 y la MK-84, estimados.

BDA: nivel 1, el dano fisico al blanco; nivel 2, el dano funcional al objetivo material (operativo, degradado,
neutralizado, destruido); nivel 3, el efecto sobre el sistema (su anillo de Warden y lo que pierde el bando); y la
recomendacion de re-ataque.
"""

from __future__ import annotations

import math

from app.engine import catalogo, geo, warden

FT2_A_M2 = 0.0929
EFICIENCIA_COBERTURA = 0.3
FACTOR_NO_GUIADA = 3.0
FACTOR_GUIADA = 1.25
ANGULOS = (30, 45, 60)

# MAE (pies cuadrados) por blanco, criterio y angulo: (MK-81, MK-82, MK-83, MK-84)
MAE = {
    ("aviones", "irreparable"): {30: (11100, 16900, 26400, 34000), 45: (13000, 18900, 31300, 39000), 60: (16500, 24900, 40500, 50400)},
    ("aviones", "despegue"): {30: (97000, 136000, 198000, 242000), 45: (115000, 144000, 250000, 288000), 60: (146000, 200000, 281800, 353000)},
    ("antiaerea", "neutraliza"): {30: (2340, 4060, 6820, 9000), 45: (2760, 4540, 8360, 10900), 60: (3530, 5860, 10000, 14600)},
    ("radar", "inoperable"): {30: (32800, 50100, 79300, 105000), 45: (38600, 53800, 97900, 122000), 60: (49800, 73900, 113000, 150000)},
}
CRITERIOS = {
    "aviones": [("despegue", "Imposibilita el despegue"), ("irreparable", "Daño irreparable")],
    "antiaerea": [("neutraliza", "Neutraliza el poder de fuego")],
    "radar": [("inoperable", "Inoperable")],
}
NOMBRE_BLANCO = {"aviones": "Aviones estacionados", "antiaerea": "Piezas antiaéreas", "radar": "Radar o vehículo"}
BOMBAS = ("MK-81", "MK-82", "MK-83", "MK-84")
# arma (codigo de la OTA) -> (bomba equivalente, escala del MAE, guiada, armas por aeronave, radio de escombros m)
EQUIVALENTE = {
    "BMK": ("MK-82", 1.0, False, 6, 240), "BKM": ("MK-84", 1.0, False, 2, 365), "BTK": ("MK-82", 1.0, False, 4, 240),
    "BOD": ("MK-84", 1.2, False, 2, 365), "BBU": ("MK-82", 1.0, True, 4, 110), "BGB": ("MK-84", 1.0, True, 2, 180),
    "JDM": ("MK-84", 1.0, True, 2, 365), "BKR": ("MK-83", 1.0, True, 4, 300), "BRK": ("MK-84", 1.6, True, 1, 450),
    "MA1": ("MK-83", 1.0, True, 2, 300), "MA4": ("MK-83", 1.0, True, 2, 300), "MA5": ("MK-83", 1.0, True, 1, 300),
    "MA2": ("MK-81", 1.0, True, 2, 85), "MA3": ("MK-81", 1.0, True, 2, 85), "HRM": ("MK-81", 1.0, True, 2, 85),
    "JSW": ("MK-82", 1.0, True, 2, 240), "HLF": ("MK-81", 0.25, True, 4, 40), "CKL": ("MK-81", 0.15, False, 4, 40),
    "CKH": ("MK-81", 0.05, False, 1, 20),
    "FAB": ("MK-83", 1.1, False, 4, 300), "MAV": ("MK-81", 0.6, True, 2, 85), "SCL": ("MK-84", 1.0, True, 2, 365),
    "TOW": ("MK-81", 0.2, True, 4, 40), "ATK": ("MK-81", 0.25, True, 4, 40), "VKR": ("MK-81", 0.25, True, 4, 40),
    "UMT": ("MK-81", 0.25, True, 4, 40), "MAM": ("MK-81", 0.2, True, 4, 40),
    "BA7": ("MK-81", 0.25, True, 4, 40),
}
# area de cada DMPI (m2) y DMPI por blanco
AREA_DMPI_M2 = {"aviones": 6000.0, "antiaerea": 200.0, "radar": 400.0}
DMPI_FIJOS = {"antiaerea": 4, "radar": 2}
UMBRAL = {"destruido": 0.0, "neutralizado": 30.0, "degradado": 70.0}  # fuerza que queda


def tipo_de_blanco(u) -> str:
    """Categoria del blanco para la tabla de efectos."""
    if u is None:
        return "radar"
    clase = catalogo.obtener(getattr(u, "clase", None), u.tipo)
    if u.tipo == "aerea" or catalogo.opera_aeronaves(u):
        return "aviones"
    if clase.defensa_aerea or (clase.id or "").startswith("antiaerea") or clase.id == "artilleria_antiaerea":
        return "antiaerea"
    return "radar"  # radares, vehiculos, lanzadores e instalaciones chicas


def dmpi_de(u, tipo: str) -> int:
    if u is None:
        return 1
    if tipo == "aviones":
        n = int(getattr(u, "aeronaves", 0) or 0) if u.tipo == "aerea" else 8
        return max(1, math.ceil(n / 2))  # un DMPI cada dos aviones estacionados
    return DMPI_FIJOS.get(tipo, 1)


def calcular(arma: str, tipo: str, criterio: str | None = None, angulo: int = 45, dmpi: int = 1, aeronaves: int = 0,
             area_m2: float | None = None, por_aeronave: int | None = None) -> dict | None:
    """Armas en el blanco y a lanzar para lograr el criterio de dano; None si el arma no es aire-superficie.
    `area_m2`: area del blanco (un solo DMPI que la cubre), en lugar de la tipica de cada DMPI. `por_aeronave`: las
    que lleva cada aeronave en la carga elegida (engine/armas.py), en lugar de las tipicas del arma."""
    eq = EQUIVALENTE.get(arma or "")
    if eq is None or tipo not in NOMBRE_BLANCO:
        return None
    bomba, escala, guiada, tipicas, escombros = eq
    por_aeronave = por_aeronave or tipicas
    criterio = criterio if (tipo, criterio) in MAE else CRITERIOS[tipo][0][0]
    angulo = min(ANGULOS, key=lambda a: abs(a - int(angulo or 45)))
    mae_m2 = MAE[(tipo, criterio)][angulo][BOMBAS.index(bomba)] * escala * FT2_A_M2
    if area_m2:
        dmpi = 1
    por_dmpi = max(1, math.ceil((area_m2 or AREA_DMPI_M2[tipo]) / (mae_m2 * EFICIENCIA_COBERTURA) - 1e-9))
    impactos = por_dmpi * max(1, dmpi)
    lanzar = math.ceil(impactos * (FACTOR_GUIADA if guiada else FACTOR_NO_GUIADA) - 1e-9)
    necesarias = math.ceil(lanzar / por_aeronave)
    out = {"arma": arma, "bomba_equivalente": bomba, "guiada": guiada, "blanco": tipo, "blanco_nombre": NOMBRE_BLANCO[tipo],
           "criterio": criterio, "criterio_nombre": dict(CRITERIOS[tipo])[criterio], "angulo": angulo,
           "mae_m2": round(mae_m2), "radio_efecto_m": round(math.sqrt(mae_m2 / math.pi)), "dmpi": max(1, dmpi),
           "impactos": impactos, "lanzar": lanzar, "por_aeronave": por_aeronave, "aeronaves_necesarias": necesarias,
           "radio_escombros_m": escombros}
    if aeronaves:
        out["lleva"] = aeronaves * por_aeronave
        out["suficiente"] = out["lleva"] >= lanzar
    return out


def colaterales(lat: float, lon: float, radio_m: float, unidades, bando_atacante: str, excluir_id=None) -> list:
    """Infraestructura civil y unidades propias dentro del radio de escombros del punto de impacto."""
    out = []
    for x in unidades:
        if x.id == excluir_id or x.estado == "destruida":
            continue
        civil = bool(catalogo.obtener(getattr(x, "clase", None), x.tipo).infraestructura)
        if not (civil or x.bando == bando_atacante):
            continue
        d = geo.distancia_km(lat, lon, x.lat, x.lon) * 1000.0
        if d <= radio_m:
            out.append((x, round(d)))
    return out


def estado_funcional(fuerza: float) -> str:
    if fuerza <= UMBRAL["destruido"]:
        return "destruido"
    if fuerza < UMBRAL["neutralizado"]:
        return "neutralizado"
    if fuerza < UMBRAL["degradado"]:
        return "degradado"
    return "operativo"


def bda(atacante, blanco, fuerza_antes: float, fuerza_despues: float, unidades) -> dict:
    """Evaluacion de danos del ataque en 3 niveles y la recomendacion de re-ataque."""
    perdida = max(0.0, fuerza_antes - fuerza_despues)
    estimado = int(round(perdida / 10.0)) * 10  # el A-2 lo estima por imagenes y reportes: de a 10 %
    estado = estado_funcional(fuerza_despues)
    anillo = warden.anillo(blanco)
    tipo = tipo_de_blanco(blanco)
    arma = getattr(atacante, "arma_elegida", None) or ""
    w = calcular(arma, tipo, dmpi=dmpi_de(blanco, tipo), aeronaves=max(1, int(getattr(atacante, "aeronaves", 1) or 1)))
    nivel3 = f"{warden.NOMBRE[anillo]}: {warden.EFECTO.get(anillo, '')}"
    if estado in ("destruido", "neutralizado"):
        recomendacion = "No re-atacar: se logró el efecto buscado; vigilar su reparación."
    elif w is not None and not w.get("suficiente", True):
        recomendacion = (f"Re-atacar: harían falta unas {w['lanzar']} {arma} ({w['aeronaves_necesarias']} aeronaves) para "
                         f"«{w['criterio_nombre'].lower()}»; el grupo llevó {w['lleva']}.")
    else:
        recomendacion = "Re-atacar en el próximo ciclo con armamento guiado o más salidas."
    colat = []
    if w is not None:
        colat = [f"{x.nombre} a {d} m" for x, d in colaterales(blanco.lat, blanco.lon, w["radio_escombros_m"], unidades,
                                                               atacante.bando, blanco.id)]
    return {"blanco": blanco.nombre, "nivel1": f"daño físico estimado {estimado} %", "nivel2": estado,
            "nivel3": nivel3, "recomendacion": recomendacion, "colaterales": colat, "anillo": anillo,
            "weaponeering": w}


def texto_bda(atacante, r: dict) -> str:
    t = (f"BDA de {atacante.nombre} sobre {r['blanco']}: nivel 1, {r['nivel1']}; nivel 2, {r['nivel2']}; "
         f"nivel 3, {r['nivel3']}. {r['recomendacion']}")
    if r["colaterales"]:
        t += " Riesgo de daño colateral (radio de escombros): " + ", ".join(r["colaterales"]) + "."
    return t
