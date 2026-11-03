"""Cargas de armamento por aeronave y existencias de armas en bases y buques (Cóndor).

Al despegar (o al planificar la mision) se elige la carga del grupo segun su modelo: aire-aire, ataque, antibuque,
SEAD o reconocimiento. Cada carga lleva una cantidad real de misiles y bombas por aeronave (los codigos de armamento
de la OTA, engine/ota.py), cada arma con su alcance y su probabilidad de impacto. El daño de cada pasada sigue saliendo
de la tabla de combate (engine/combat.py, decision del usuario: el balance no cambia); la carga decide cuantas pasadas
hay y con que arma: contra que se puede tirar, desde que distancia y la bonificacion del arma (guiada, antirradiacion;
engine/ota.py). Cada pasada gasta armas reales: un misil por aeronave, la mitad de las bombas o los cohetes. La
municion en % de la aeronave se calcula de lo que le queda (asi siguen valiendo el regreso sin armamento y los
informes). Las aeronaves sin carga (de ejercicios anteriores) siguen con la municion en %.

Las armas salen de las existencias de la base o del pañol del buque al despegar y al rearmar despues de aterrizar.
Las existencias son abundantes (EXISTENCIAS por tipo de arma, decision del usuario) y el director las puede cambiar.
"""

from __future__ import annotations

import json
import math

from app.engine import catalogo, ota

# tipo de arma -> nombre, probabilidad de impacto tipica y existencias iniciales en una base (varias recargas)
TIPOS = {"aa": "aire-aire", "as": "aire-superficie", "ar": "antirradiación", "ab": "antibuque", "bomba": "bomba",
         "helo": "cañón o cohetes"}
PK = {"M120": 0.6, "MAA": 0.55, "MAB": 0.45, "MAC": 0.4, "M9X": 0.75, "MAD": 0.7, "MPA": 0.65, "MPB": 0.6,
      "HRM": 0.65, "MA3": 0.6, "HPN": 0.75, "EXO": 0.75, "MA6": 0.7, "MA2": 0.7}
PK_TIPO = {"aa": 0.6, "as": 0.7, "ar": 0.6, "ab": 0.75, "bomba": 0.4, "helo": 0.3}
PK_GUIADA = 0.8  # bombas guiadas (laser, TV, GPS)
EXISTENCIAS = {"aa": 160, "as": 80, "ar": 40, "ab": 40, "bomba": 300, "helo": 400}
FACTOR_PANOL = 0.5  # el pañol de un buque guarda la mitad que una base
ALCANCE_BOMBA_KM = 3.0  # una bomba se suelta casi encima del blanco (las guiadas, desde su alcance)
NOMBRES_CARGA = {"aire_aire": "Aire-aire", "ataque": "Ataque", "antibuque": "Antibuque", "sead": "SEAD (antirradiación)",
                 "reconocimiento": "Reconocimiento"}
CANTIDAD = {"aa_largo": 4, "aa_corto": 2, "as": 2, "ar": 2, "ab": 2, "CKH": 6, "CKL": 4, "ALP": 6, "HLF": 4}


def _arma(codigo: str) -> tuple | None:
    return ota.ARMAMENTO.get(codigo)


def tipo(codigo: str) -> str:
    a = _arma(codigo)
    return a[1] if a else ""


def pk(codigo: str) -> float:
    a = _arma(codigo)
    if a is None:
        return 0.0
    if codigo in PK:
        return PK[codigo]
    return PK_GUIADA if a[1] == "bomba" and a[2] else PK_TIPO.get(a[1], 0.5)


def alcance_arma(codigo: str) -> float:
    a = _arma(codigo)
    if a is None:
        return 0.0
    return float(a[3]) if a[3] else ALCANCE_BOMBA_KM


def publico() -> dict:
    """Armas para la pantalla: nombre, tipo, alcance y probabilidad de impacto."""
    return {k: {"nombre": n, "tipo": t, "tipo_nombre": TIPOS.get(t, t), "guiada": g, "alcance_km": alcance_arma(k),
                "pk": pk(k)} for k, (n, t, g, _) in ota.ARMAMENTO.items()}


# ---------------------------------------------------------------------------------------------------- cargas
def cargas_de(modelo_id: str | None, clase=None) -> dict[str, dict[str, int]]:
    """Cargas que puede llevar el modelo: {nombre: {arma: cantidad por aeronave}} (en orden de preferencia)."""
    if clase is None and modelo_id in catalogo.MODELOS:
        m = catalogo.MODELOS[modelo_id]
        clase = catalogo.CLASES.get(m.clase)
    armas = list(ota.armas_de(modelo_id, clase))
    if (modelo_id not in ota.ARMAMENTO_POR_MODELO and clase is not None and clase.ataque_vs.get("naval", 0) > 0
            and clase.ataque_vs.get("aerea", 0) > 0):
        armas.append("HPN")  # cazas y aviones de ataque sin lista propia: el misil antibuque mas difundido
    aa = [a for a in armas if tipo(a) == "aa"]
    largo = sorted((a for a in aa if alcance_arma(a) >= 40), key=lambda a: -alcance_arma(a))
    corto = sorted((a for a in aa if alcance_arma(a) < 40), key=lambda a: -pk(a))
    autodefensa = {corto[0]: CANTIDAD["aa_corto"]} if corto else {}
    cargas: dict[str, dict[str, int]] = {}
    if aa:
        cargas["aire_aire"] = ({largo[0]: CANTIDAD["aa_largo"]} if largo else {}) | (
            {corto[0]: CANTIDAD["aa_corto"] if largo else CANTIDAD["aa_largo"]} if corto else {})
    helo = [a for a in armas if tipo(a) == "helo" or a == "HLF" and not aa]
    superficie = [a for a in armas if tipo(a) in ("as", "bomba")]
    guiadas = [a for a in superficie if _arma(a)[2]]
    if helo:
        cargas["ataque"] = {a: CANTIDAD.get(a, 4) for a in helo}
    elif superficie:
        principal = (guiadas or superficie)[0]
        from app.engine import weaponeering  # importacion tardia: weaponeering importa el catalogo

        n = weaponeering.EQUIVALENTE.get(principal, (None, 1, False, CANTIDAD["as"], 0))[3]
        cargas["ataque"] = {principal: n} | autodefensa
    ab = [a for a in armas if tipo(a) == "ab"]
    if ab:
        cargas["antibuque"] = {ab[0]: CANTIDAD["ab"]} | autodefensa
    ar = [a for a in armas if tipo(a) == "ar"]
    if ar:
        cargas["sead"] = {ar[0]: CANTIDAD["ar"]} | autodefensa
    cargas["reconocimiento"] = dict(autodefensa)
    return cargas


def carga_por_defecto(modelo_id: str | None, clase=None) -> str:
    cargas = cargas_de(modelo_id, clase)
    cid = getattr(clase, "id", "") or (catalogo.MODELOS[modelo_id].clase if modelo_id in catalogo.MODELOS else "")
    preferida = "aire_aire" if cid in ("caza", "caza_embarcado") else "ataque"
    return preferida if preferida in cargas else next(iter(cargas))


def datos(u) -> dict | None:
    try:
        d = json.loads(getattr(u, "armamento_json", None) or "null")
    except ValueError:
        return None
    return d if isinstance(d, dict) and d.get("quedan") is not None else None


def tiene_carga(u) -> bool:
    return getattr(u, "tipo", "") == "aerea" and datos(u) is not None


def _guardar(u, d: dict) -> None:
    u.armamento_json = json.dumps(d, separators=(",", ":"))


def completa(u, nombre: str) -> dict[str, int]:
    """Armas de la carga completa para todo el grupo."""
    por = cargas_de(getattr(u, "modelo", None), catalogo.perfil(u)).get(nombre, {})
    n = max(1, int(getattr(u, "aeronaves", 1) or 1))
    return {a: c * n for a, c in por.items()}


def aplica(u) -> bool:
    """Lleva carga de armamento: las aeronaves tripuladas y los drones (no la municion merodeadora ni los misiles)."""
    clase = catalogo.obtener(getattr(u, "clase", None), getattr(u, "tipo", ""))
    return getattr(u, "tipo", "") == "aerea" and not clase.se_consume and not catalogo.es_misil(u)


def armar(u, nombre: str | None, deposito=None) -> str:
    """Le pone la carga `nombre` (o la por defecto) al grupo, sacando las armas de las existencias del deposito (una
    base o un buque) si lo hay; con existencias insuficientes lleva lo que haya. Devuelve un texto para el evento."""
    if not aplica(u):
        return ""
    cargas = cargas_de(getattr(u, "modelo", None), catalogo.perfil(u))
    if nombre not in cargas:
        nombre = carga_por_defecto(getattr(u, "modelo", None), catalogo.perfil(u))
    llena = completa(u, nombre)
    faltas = []
    lleva = {}
    for a, n in llena.items():
        hay = tomar(deposito, a, n) if deposito is not None else n
        lleva[a] = hay
        if hay < n:
            faltas.append(f"{ota.ARMAMENTO[a][0]} {hay} de {n}")
    _guardar(u, {"nombre": nombre, "por_aeronave": cargas[nombre], "quedan": lleva})
    sincronizar(u)
    return (f"carga {NOMBRES_CARGA.get(nombre, nombre).lower()}"
            + (f" incompleta por falta de existencias ({', '.join(faltas)})" if faltas else ""))


def error_de_carga(modelo_id: str | None, nombre: str | None, aeronaves: int, deposito=None) -> str | None:
    """Motivo por el que no puede despegar con esa carga (None si puede): no es del modelo o la base no tiene nada."""
    if not nombre:
        return None
    clase = catalogo.CLASES.get(catalogo.MODELOS[modelo_id].clase) if modelo_id in catalogo.MODELOS else None
    cargas = cargas_de(modelo_id, clase)
    if nombre not in cargas:
        return f"Esa aeronave no lleva la carga «{NOMBRES_CARGA.get(nombre, nombre)}»."
    if deposito is not None:
        for a, n in cargas[nombre].items():
            if existencias(deposito).get(a, inicial(deposito, a)) <= 0 and n > 0:
                return f"{deposito.nombre} no tiene {ota.ARMAMENTO[a][0]} en sus existencias."
    return None


# ---------------------------------------------------------------------------------------------------- disparos
def _sirve(codigo: str, blanco, emite: bool) -> bool:
    t = tipo(codigo)
    if blanco.tipo == "aerea" and not getattr(blanco, "en_tierra", False):
        return t == "aa"
    if t == "aa":
        return False
    if t == "ar":
        return emite
    if t == "ab":
        return blanco.tipo == "naval"
    return True  # bombas, misiles aire-superficie, cañon y cohetes contra todo lo de superficie


def _emite(blanco) -> bool:
    from app.engine import guerra_electronica as ge_mod  # importacion tardia

    return bool(ge_mod.emite_radar(blanco))


def utiles(u, blanco) -> list[str]:
    """Armas que le quedan y sirven contra el blanco, de la preferida a la ultima (antibuque contra buques,
    antirradiacion contra radares que emiten; despues, la de mas alcance)."""
    d = datos(u)
    if d is None:
        return []
    emite = _emite(blanco)
    armas = [a for a, n in d["quedan"].items() if n > 0 and _sirve(a, blanco, emite)]
    orden = {"ab": 0, "ar": 0, "as": 1, "bomba": 2, "helo": 3, "aa": 1}
    return sorted(armas, key=lambda a: (orden.get(tipo(a), 4), -alcance_arma(a)))


def alcance(u, blanco) -> float:
    """Desde donde puede tirarle: el alcance de la mejor arma que le queda contra ese blanco (sin carga, el de la
    unidad; sin armas utiles, 0)."""
    if not tiene_carga(u):
        return u.alcance_km
    armas = utiles(u, blanco)
    return max((alcance_arma(a) for a in armas), default=0.0)


def elegir(u, blanco, distancia: float) -> str | None:
    """El arma de la pasada: la preferida entre las que llegan a esa distancia."""
    for a in utiles(u, blanco):
        if alcance_arma(a) >= distancia - 1e-6:
            return a
    return None


def por_pasada(u, codigo: str) -> int:
    """Armas que gasta el grupo en una pasada: un misil por aeronave; la mitad de las bombas o los cohetes."""
    d = datos(u) or {}
    n = max(1, int(getattr(u, "aeronaves", 1) or 1))
    por = int((d.get("por_aeronave") or {}).get(codigo, 1) or 1)
    if tipo(codigo) in ("bomba", "helo"):
        return n * max(1, math.ceil(por / 2))
    return n


def gastar(u, codigo: str) -> int:
    """Descuenta las armas de una pasada; devuelve cuantas tiro."""
    d = datos(u)
    if d is None or codigo not in d["quedan"]:
        return 0
    tiradas = min(d["quedan"][codigo], por_pasada(u, codigo))
    d["quedan"][codigo] -= tiradas
    _guardar(u, d)
    return tiradas


def municion_pct(u) -> float:
    """Municion en % segun las pasadas que le quedan respecto de la carga completa."""
    d = datos(u)
    if d is None:
        return u.municion
    llena = completa(u, d.get("nombre", ""))
    total = sum(math.ceil(n / max(1, por_pasada(u, a))) for a, n in llena.items())
    quedan = sum(math.ceil(n / max(1, por_pasada(u, a))) for a, n in d["quedan"].items() if n > 0)
    if total <= 0:
        return 0.0 if not d.get("nombre") == "reconocimiento" else u.municion
    return max(0.0, min(100.0, 100.0 * quedan / total))


def sincronizar(u) -> None:
    if tiene_carga(u):
        u.municion = municion_pct(u)


def texto(u) -> str:
    """«Aire-aire: AIM-120 AMRAAM 6/8, AIM-9X 4/4»."""
    d = datos(u)
    if d is None:
        return ""
    llena = completa(u, d.get("nombre", ""))
    partes = [f"{ota.ARMAMENTO[a][0]} {n}/{llena.get(a, n)}" for a, n in d["quedan"].items() if a in ota.ARMAMENTO]
    return f"{NOMBRES_CARGA.get(d.get('nombre'), d.get('nombre'))}: " + (", ".join(partes) if partes else "sin armas")


# ---------------------------------------------------------------------------------------------------- existencias
def deposito_de(u) -> bool:
    """Bases aereas y buques que operan aeronaves guardan armas para ellas."""
    return catalogo.opera_aeronaves(u)


def existencias(dep) -> dict[str, int]:
    try:
        d = json.loads(getattr(dep, "existencias_json", None) or "{}")
    except ValueError:
        d = {}
    return {k: int(v) for k, v in d.items()} if isinstance(d, dict) else {}


def inicial(dep, codigo: str) -> int:
    n = EXISTENCIAS.get(tipo(codigo), 50)
    return int(n * (FACTOR_PANOL if dep.tipo == "naval" else 1.0))


def tomar(dep, codigo: str, n: int) -> int:
    """Saca hasta `n` armas del deposito (si nunca se uso ese codigo, empieza con las existencias iniciales)."""
    ex = existencias(dep)
    if codigo not in ex:
        ex[codigo] = inicial(dep, codigo)
    sacadas = max(0, min(n, ex[codigo]))
    ex[codigo] -= sacadas
    dep.existencias_json = json.dumps(ex, sort_keys=True)
    return sacadas


def devolver(dep, armas: dict[str, int]) -> None:
    ex = existencias(dep)
    for a, n in armas.items():
        if n > 0:
            ex[a] = ex.get(a, inicial(dep, a)) + n
    dep.existencias_json = json.dumps(ex, sort_keys=True)


def rearmar(u, dep) -> str:
    """Al terminar el rearme en tierra: devuelve lo que no tiro y vuelve a cargar la misma carga desde el deposito."""
    d = datos(u)
    if d is None:
        return armar(u, None, dep) if dep is not None else ""
    if dep is not None:
        devolver(dep, d["quedan"])
    return armar(u, d.get("nombre"), dep)


def resumen_existencias(dep, unidades=()) -> dict[str, int]:
    """Existencias para mostrar: lo guardado y, de las armas que usan las aeronaves del bando, las iniciales."""
    ex = existencias(dep)
    for x in unidades:
        if x.tipo == "aerea" and x.bando == dep.bando and x.modelo:
            for carga in cargas_de(x.modelo, catalogo.perfil(x)).values():
                for a in carga:
                    ex.setdefault(a, inicial(dep, a))
    return dict(sorted(ex.items()))
