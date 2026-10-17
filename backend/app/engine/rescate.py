"""Recuperacion de personal: tripulaciones derribadas, busqueda y rescate (SAR) y rescate en combate (CSAR).

Cuando un grupo aereo pierde aeronaves en vuelo, sus tripulantes se eyectan: sobreviven EYECCION_EXITOSA de ellos y
quedan "aislados" en el lugar del derribo, a la espera del rescate. Cada turno:
  - una mision CSAR propia (helicopteros) que orbita a <= RADIO_RESCATE_KM los rescata (hasta su capacidad);
  - si hay unidades terrestres enemigas a <= RADIO_CAPTURA_KM, pueden capturarlos (PROB_CAPTURA por turno; menos si
    un AEW propio coordina el rescate y hay cazas propios cubriendo la zona);
  - pasado su tiempo de supervivencia (en el agua, mucho menor) se dan por perdidos.
Cada bando ve sus tripulaciones; las del enemigo, solo las que sus unidades tienen cerca (vieron el derribo).
Los sorteos son reproducibles (semilla del escenario). Valores didacticos, ajustables.
"""

from __future__ import annotations

import hashlib
import json
import math
import random

from app.engine import catalogo, geo, plataformas

EYECCION_EXITOSA = 0.8
RADIO_RESCATE_KM = 5.0
RADIO_CAPTURA_KM = 10.0
RADIO_AVISTAMIENTO_KM = 25.0
PROB_CAPTURA = 0.35
FACTOR_CAPTURA_CUBIERTO = 0.5  # con cazas propios a <= RADIO_COBERTURA_KM de la tripulacion
RADIO_COBERTURA_KM = 40.0
SUPERVIVENCIA_TURNOS = {"agua": 12, "tierra": 72}
CAPACIDAD_RESCATE = {"helicoptero": 4, "helicoptero_artillado": 10}  # tripulantes por aeronave
CLASES_RESCATE = tuple(CAPACIDAD_RESCATE)
ESTADOS = ("aislado", "rescatado", "capturado", "perdido")


def _rng(escenario, *claves) -> random.Random:
    h = hashlib.sha256(":".join(str(c) for c in (getattr(escenario, "semilla", 0), "rescate", *claves)).encode()).digest()
    return random.Random(int.from_bytes(h[:8], "big"))


def lista(escenario) -> list[dict]:
    try:
        d = json.loads(getattr(escenario, "derribados_json", None) or "[]")
    except ValueError:
        return []
    return d if isinstance(d, list) else []


def _guardar(escenario, datos: list) -> None:
    escenario.derribados_json = json.dumps(datos)


def puede_rescatar(u) -> bool:
    return u.tipo == "aerea" and (u.clase or "") in CLASES_RESCATE


def registrar(escenario, u, aeronaves_perdidas: float, turno: int, terreno=None) -> dict | None:
    """Tripulacion de las aeronaves derribadas de un grupo en vuelo (None si no sobrevive nadie o no lleva gente)."""
    clase = catalogo.obtener(u.clase, u.tipo)
    if clase.dron or clase.misil or clase.se_consume or aeronaves_perdidas < 0.5:
        return None
    f = plataformas.ficha(u)
    por_aeronave = f.tripulacion if f is not None else 1
    tripulantes = int(math.floor(round(aeronaves_perdidas) * por_aeronave * EYECCION_EXITOSA + 0.5))
    if tripulantes <= 0:
        return None
    datos = lista(escenario)
    medio = "agua" if terreno is not None and terreno.clase(u.lat, u.lon) == "agua" else "tierra"
    d = {"id": len(datos) + 1, "bando": u.bando, "lat": round(u.lat, 5), "lon": round(u.lon, 5), "turno": turno,
         "tripulantes": tripulantes, "grupo": u.nombre, "medio": medio, "estado": "aislado", "turno_fin": None, "por": ""}
    datos.append(d)
    _guardar(escenario, datos)
    return d


def rescatar(escenario, helo, turno: int) -> list[dict]:
    """El grupo de rescate recoge a las tripulaciones propias aisladas a su alcance (hasta su capacidad)."""
    if not puede_rescatar(helo):
        return []
    datos = lista(escenario)
    lugar = max(1, round((helo.aeronaves or 1) * max(0.0, helo.fuerza) / 100.0)) * CAPACIDAD_RESCATE[helo.clase]
    hechos = []
    for d in sorted(datos, key=lambda x: geo.distancia_km(helo.lat, helo.lon, x["lat"], x["lon"])):
        if d["estado"] != "aislado" or d["bando"] != helo.bando or d["tripulantes"] > lugar:
            continue
        if geo.distancia_km(helo.lat, helo.lon, d["lat"], d["lon"]) > RADIO_RESCATE_KM:
            continue
        d.update(estado="rescatado", turno_fin=turno, por=helo.nombre)
        lugar -= d["tripulantes"]
        hechos.append(d)
    if hechos:
        _guardar(escenario, datos)
    return hechos


def avanzar(escenario, unidades, turno: int) -> list[tuple[dict, str]]:
    """Captura y supervivencia de las tripulaciones aisladas. Devuelve [(tripulacion, nuevo estado)]."""
    datos = lista(escenario)
    cambios = []
    for d in datos:
        if d["estado"] != "aislado":
            continue
        enemigos = [x for x in unidades if x.bando != d["bando"] and x.estado == "activa" and x.tipo == "terrestre"
                    and geo.distancia_km(x.lat, x.lon, d["lat"], d["lon"]) <= RADIO_CAPTURA_KM]
        if enemigos and d["medio"] != "agua":
            cubiertos = any(x.bando == d["bando"] and x.tipo == "aerea" and x.estado == "activa" and not x.en_tierra
                            and catalogo.perfil(x).ataque_vs.get("terrestre", 0) > 0
                            and geo.distancia_km(x.lat, x.lon, d["lat"], d["lon"]) <= RADIO_COBERTURA_KM
                            for x in unidades)
            p = PROB_CAPTURA * (FACTOR_CAPTURA_CUBIERTO if cubiertos else 1.0)
            if _rng(escenario, d["id"], turno).random() < p:
                captor = min(enemigos, key=lambda x: geo.distancia_km(x.lat, x.lon, d["lat"], d["lon"]))
                d.update(estado="capturado", turno_fin=turno, por=captor.nombre)
                cambios.append((d, "capturado"))
                continue
        if turno - d["turno"] >= SUPERVIVENCIA_TURNOS[d["medio"]]:
            d.update(estado="perdido", turno_fin=turno)
            cambios.append((d, "perdido"))
    if cambios:
        _guardar(escenario, datos)
    return cambios


def visibles(escenario, rol: str, unidades) -> list[dict]:
    """Las propias (todas) y las enemigas aisladas que alguna unidad del bando tiene cerca; el instructor, todas."""
    datos = lista(escenario)
    if rol not in ("azul", "rojo"):
        return datos
    propias = [d for d in datos if d["bando"] == rol]
    ajenas = [d for d in datos if d["bando"] != rol and d["estado"] == "aislado"
              and any(x.bando == rol and x.estado == "activa"
                      and geo.distancia_km(x.lat, x.lon, d["lat"], d["lon"]) <= RADIO_AVISTAMIENTO_KM for x in unidades)]
    return propias + [{k: v for k, v in d.items() if k not in ("grupo", "por")} for d in ajenas]


def resumen(escenario, bando: str) -> dict:
    datos = [d for d in lista(escenario) if d["bando"] == bando]
    out = {e: sum(d["tripulantes"] for d in datos if d["estado"] == e) for e in ESTADOS}
    out["eventos"] = len(datos)
    return out
