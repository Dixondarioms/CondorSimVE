"""Plan de transmisiones (C-E): redes con su frecuencia primaria y secundaria, banda, indicativo y vigencia.

Cada bando tiene un plan con una red por funcion (mando y control, control de interceptacion, ataque y apoyo aereo
cercano, defensa aerea, logistica) mas la red de guardia, que es fija (121,5 y 243,0 MHz). El plan se verifica:
cada frecuencia dentro de su banda, primaria distinta de la secundaria, sin repetir ni pisar a otra red (separacion
minima de SEPARACION_MHZ), sin usar las de guardia y vigente (las frecuencias se cambian cada VIGENCIA_TURNOS por
seguridad de las comunicaciones).

Efecto en el motor (engine/orders.py, demora de las ordenes): un plan con errores o vencido suma DEMORA_PLAN_PCT a
la probabilidad de que una orden del bando no llegue a tiempo; con un plan valido, la red secundaria permite saltar
de frecuencia ante la interferencia enemiga y la demora que esta causa se reduce a la mitad.
"""

from __future__ import annotations

import json

BANDAS = {"HF": (2.0, 30.0), "VHF": (30.0, 174.0), "UHF": (225.0, 400.0)}
GUARDIA = (121.5, 243.0)
SEPARACION_MHZ = 0.025
VIGENCIA_TURNOS = 24
DEMORA_PLAN_PCT = 10.0
FACTOR_SALTO_FRECUENCIA = 0.5
REDES = (
    ("mando", "Mando y control (COA)"), ("gci", "Control de interceptación (GCI)"),
    ("ataque", "Ataque y apoyo aéreo cercano"), ("defensa", "Defensa aérea"), ("logistica", "Logística"),
)
SUGERIDO = {
    "azul": {"mando": ("HF", 8.150, 11.240), "gci": ("UHF", 251.300, 276.850), "ataque": ("UHF", 233.600, 262.150),
             "defensa": ("VHF", 46.250, 52.875), "logistica": ("VHF", 38.400, 41.725)},
    "rojo": {"mando": ("HF", 6.620, 9.315), "gci": ("UHF", 305.400, 328.950), "ataque": ("UHF", 285.750, 299.200),
             "defensa": ("VHF", 61.125, 66.450), "logistica": ("VHF", 70.300, 74.650)},
}


def sugerido(bando: str, turno: int) -> dict:
    s = SUGERIDO.get(bando, SUGERIDO["azul"])
    return {"desde": turno, "redes": [{"red": k, "nombre": n, "banda": s[k][0], "primaria": s[k][1], "secundaria": s[k][2],
                                       "indicativo": f"{bando[:1].upper()}{i + 1:02d}"} for i, (k, n) in enumerate(REDES)]}


def plan(escenario, bando: str) -> dict | None:
    try:
        d = json.loads(getattr(escenario, "transmisiones_json", None) or "{}")
    except ValueError:
        return None
    p = d.get(bando)
    return p if isinstance(p, dict) and p.get("redes") else None


def guardar(escenario, bando: str, redes: list[dict], turno: int) -> dict:
    try:
        d = json.loads(getattr(escenario, "transmisiones_json", None) or "{}")
    except ValueError:
        d = {}
    nombres = dict(REDES)
    d[bando] = {"desde": turno, "redes": [{**r, "nombre": nombres.get(r["red"], r["red"])} for r in redes]}
    escenario.transmisiones_json = json.dumps(d)
    return d[bando]


def errores(p: dict | None, turno: int) -> list[str]:
    """Problemas del plan (lista vacia si es valido; un plan inexistente no tiene errores: no se usa)."""
    if not p:
        return []
    out = []
    usadas: list[tuple[float, str]] = []
    presentes = {r["red"] for r in p["redes"]}
    for k, nombre in REDES:
        if k not in presentes:
            out.append(f"Falta la red {nombre}.")
    for r in p["redes"]:
        nombre = r.get("nombre") or r["red"]
        lo, hi = BANDAS.get(r.get("banda"), (0, 0))
        for campo in ("primaria", "secundaria"):
            f = r.get(campo)
            if f is None:
                out.append(f"{nombre}: falta la frecuencia {campo}.")
                continue
            f = float(f)
            if not lo <= f <= hi:
                out.append(f"{nombre}: la {campo} {f:.3f} MHz está fuera de la banda {r.get('banda')} ({lo:g} a {hi:g} MHz).")
            if any(abs(f - g) < 0.001 for g in GUARDIA):
                out.append(f"{nombre}: {f:.3f} MHz es una frecuencia de guardia (emergencia).")
            for g, otra in usadas:
                if abs(f - g) < SEPARACION_MHZ:
                    out.append(f"{nombre}: la {campo} {f:.3f} MHz pisa a {otra} ({g:.3f} MHz); deje {SEPARACION_MHZ * 1000:.0f} kHz.")
            usadas.append((f, f"{nombre} ({campo})"))
    vence = int(p.get("desde") or 0) + VIGENCIA_TURNOS
    if turno > vence:
        out.append(f"Plan vencido desde el turno {vence}: cambie las frecuencias (se renuevan cada {VIGENCIA_TURNOS} turnos).")
    return out


def demora_extra_pct(escenario, bando: str, turno: int) -> float:
    p = plan(escenario, bando)
    return DEMORA_PLAN_PCT if p and errores(p, turno) else 0.0


def factor_interferencia(escenario, bando: str, turno: int) -> float:
    """Con un plan valido (red secundaria), la demora por interferencia baja a la mitad (salto de frecuencia)."""
    p = plan(escenario, bando)
    return FACTOR_SALTO_FRECUENCIA if p and not errores(p, turno) else 1.0


def resumen(escenario, bando: str, turno: int) -> dict:
    p = plan(escenario, bando)
    return {"plan": p, "errores": errores(p, turno), "sugerido": sugerido(bando, turno) if p is None else None,
            "vence": (int(p.get("desde") or 0) + VIGENCIA_TURNOS) if p else None, "bandas": BANDAS,
            "guardia": list(GUARDIA), "redes": [list(r) for r in REDES]}


def lineas_spins(escenario, bando: str) -> str:
    p = plan(escenario, bando)
    if not p:
        return "FRECUENCIAS: sin plan de transmisiones; guardia 121,5 y 243,0 MHz."
    return "FRECUENCIAS (primaria/secundaria): " + "; ".join(
        f"{r.get('nombre') or r['red']} {r.get('indicativo') or ''} {float(r['primaria']):.3f}/{float(r['secundaria']):.3f} MHz".replace("  ", " ")
        for r in p["redes"]) + "; guardia 121,5 y 243,0 MHz."
