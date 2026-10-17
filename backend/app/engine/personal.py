"""Personal de cada unidad: dotacion (efectivos al inicio) y efectivos que le quedan.

La dotacion la fija el instructor al crear la unidad (Unidad.personal) o sale de esta tabla: por escalon en las
unidades terrestres, por tripulacion de cada aeronave en los grupos aereos y por buque o instalacion en el resto. Los
efectivos actuales siguen a la fuerza de la unidad (una compania al 60 % conserva el 60 % de su gente); la diferencia
son las bajas (muertos, heridos y desaparecidos, sin distinguir). Las cifras son didacticas, no plantillas oficiales.
La infraestructura civil (centrales, refinerias, puentes) no lleva personal militar.
"""

from app.engine import catalogo, defensa_aerea, plataformas

# unidades terrestres: efectivos por escalon
POR_ESCALON = {
    "equipo": 4, "escuadra": 9, "seccion": 30, "peloton": 40, "compania": 120, "batallon": 500,
    "regimiento": 1500, "brigada": 3500, "division": 12000,
}
# aeronaves: tripulacion de cada una (los drones se operan desde tierra: su gente no esta en riesgo en el aire)
POR_AERONAVE = {
    "caza": 1, "ataque": 2, "helicoptero": 4, "helicoptero_artillado": 4, "avion_ge": 6, "alerta_temprana": 15,
    "cisterna": 4,
}
# buques, sensores e instalaciones: dotacion fija
POR_CLASE = {
    "fragata": 180, "patrullero": 35, "destructor": 280, "portaaviones": 4500, "submarino": 35,
    "buque_desembarco": 250, "radar": 25, "base_aerea": 600, "deposito": 120, "puerto": 500, "punto_recobre": 30,
}
RAMAS = ("terrestre", "aerea", "naval", "base")
NOMBRE_RAMA = {"terrestre": "Fuerzas terrestres", "aerea": "Aviación (tripulaciones)", "naval": "Fuerzas navales",
               "base": "Bases y sensores"}


def dotacion_por_defecto(u) -> int:
    sistema = defensa_aerea.sistema(u)
    if sistema is not None:  # bateria de defensa aerea: su dotacion (ver engine/defensa_aerea.py)
        return sistema.personal
    clase = catalogo.obtener(getattr(u, "clase", None), u.tipo)
    if clase.infraestructura or clase.misil or clase.dron:
        return 0
    if u.tipo == "aerea":
        modelo = catalogo.MODELOS.get(getattr(u, "modelo", "") or "")
        ficha = plataformas.ficha_de_modelo(modelo)
        por = ficha.tripulacion if ficha is not None else POR_AERONAVE.get(modelo.clase if modelo else clase.id, 1)
        return por * max(1, int(getattr(u, "aeronaves", 1) or 1))
    if clase.id in POR_CLASE:
        return POR_CLASE[clase.id]
    return POR_ESCALON.get(getattr(u, "echelon", "") or clase.escalon, 30)


def inicial(u) -> int:
    """Efectivos con que empezo la unidad: los que fijo el instructor o los de la tabla."""
    p = getattr(u, "personal", None)
    return int(p) if p is not None else dotacion_por_defecto(u)


def actual(u) -> int:
    if getattr(u, "estado", "activa") == "destruida":
        return 0
    return round(inicial(u) * max(0.0, min(100.0, u.fuerza or 0.0)) / 100.0)


def resumen(unidades, bando: str) -> dict:
    """Efectivos iniciales y actuales, bajas y unidades por rama, y el total del bando (incluye las destruidas)."""
    ramas = {r: {"rama": r, "nombre": NOMBRE_RAMA[r], "inicial": 0, "actual": 0, "unidades": 0} for r in RAMAS}
    for u in unidades:
        if u.bando != bando:
            continue
        ini = inicial(u)
        if ini <= 0:
            continue
        r = ramas[u.tipo if u.tipo in ramas else "base"]
        r["inicial"] += ini
        r["actual"] += actual(u)
        r["unidades"] += 1
    filas = []
    for r in ramas.values():
        if r["inicial"]:
            r["bajas"] = r["inicial"] - r["actual"]
            r["operativo_pct"] = round(100 * r["actual"] / r["inicial"], 1)
            filas.append(r)
    ini = sum(r["inicial"] for r in filas)
    act = sum(r["actual"] for r in filas)
    return {"ramas": filas, "inicial": ini, "actual": act, "bajas": ini - act,
            "operativo_pct": round(100 * act / ini, 1) if ini else None}
