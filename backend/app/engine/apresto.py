"""Apresto Operacional y Puesta en Completo Apresto Operacional (PCAO).

Fuente: Manual de Apresto Operacional de la FANB y Milicia Bolivariana (CEO-MC-159, Comando Estrategico Operacional,
Direccion Conjunta de Operaciones, 25 de marzo de 2015).

Calificacion (Cap. I, Seccion B): la unidad "tiene" o "no tiene" Apresto Operacional. Tiene si alcanza el minimo de
cada literal de la tabla: A personal 75 %, B armamento y municion 90 %, C equipamiento 85 %, D adiestramiento 85 %,
E comando, control y comunicaciones 90 % (relacion de lo disponible x 100 / TOE). Ademas, las exigencias del Anexo A
para cada tipo de unidad, cuyos indices eliminatorios se aplican aqui:
  - grupo aereo o escuadron (A.20): 75 % del personal de vuelo, 80 % de las aeronaves disponibles y 75 % del personal
    de mantenimiento; por apreciacion, el 50 % de la primera carga basica de armamento listo;
  - GADAA ZU-23-2 (A.15): 75 % del personal y 75 % del equipo de combate operativo, con su carga basica;
  - CMDAA (A.16): 75 % del personal; S-125 Pechora con al menos 2 rampas listas; Buk con el 75 % de rampas y
    cargadores operativos;
  - escuadron de vigilancia y control (A.17): 75 % del personal y radares operativos con el 80 % de repuestos.

Grados (Cap. II): Apresto en tiempo de paz, Elevado Apresto (fases amarilla, naranja y roja) y Completo Apresto. La
PCAO (Cap. II, Seccion B y C) se cumple en 5 eventos: 1 activacion del plan de localizacion (aviso), 2 incorporacion
del personal y los recursos, 3 organizacion y formacion de las unidades, 4 preparacion del material de guerra para su
empleo y 5 adiestramiento y cohesion de combate; la suma de sus plazos es el plazo total de la PCAO.

En el simulador (cada turno, una hora):
  - hasta terminar el evento 2, las reservas activas y la milicia no cubren el deficit (engine/toe.py);
  - hasta terminar el evento 4, solo una parte de las aeronaves esta lista (el resto, preservadas): 60 % en tiempo
    de paz, 70/80/90 % en las fases 1/2/3 del elevado apresto;
  - el adiestramiento del bando sube durante el evento 5 hasta la meta; por debajo del 85 % las unidades combaten peor.
"""

from __future__ import annotations

import json
import math

from app.engine import catalogo, defensa_aerea, infraestructura

FUENTE = ("Manual de Apresto Operacional de la FANB y Milicia Bolivariana (CEO-MC-159, CEOFANB, 25MAR2015)")
GRADOS = ("paz", "elevado", "completo")
NOMBRE_GRADO = {"paz": "Apresto Operacional en tiempo de paz", "elevado": "Elevado Apresto Operacional",
                "completo": "Completo Apresto Operacional"}
FASES = {1: "amarilla", 2: "naranja", 3: "roja"}
# Tabla para calificacion del nivel de Apresto Operacional (literales A a E): ponderacion minima (%)
MINIMOS = {"personal": 75, "armamento": 90, "equipamiento": 85, "adiestramiento": 85, "c3": 90}
NOMBRE_ASPECTO = {"personal": "A. Personal", "armamento": "B. Armamento y munición", "equipamiento": "C. Equipamiento",
                  "adiestramiento": "D. Adiestramiento", "c3": "E. Comando, control y comunicaciones"}
EVENTOS = (
    ("aviso", "1. Activación del plan de localización (aviso)"),
    ("incorporacion", "2. Incorporación del personal y los recursos"),
    ("organizacion", "3. Organización y formación de las unidades"),
    ("material", "4. Preparación del material de guerra para su empleo"),
    ("adiestramiento", "5. Adiestramiento y cohesión de combate"),
)
PLAZOS_POR_DEFECTO = {"aviso": 2, "incorporacion": 24, "organizacion": 24, "material": 24, "adiestramiento": 72}
AERONAVES_LISTAS = {"paz": 0.6, 1: 0.7, 2: 0.8, 3: 0.9, "completo": 1.0}  # fraccion lista hasta el evento 4
POR_DEFECTO = {"grado": "completo", "fase": 1, "adiestramiento": 90, "adiestramiento_meta": 95,
               "plazos": PLAZOS_POR_DEFECTO, "pcao_inicio": None}
FACTOR_ADIESTRAMIENTO_MIN = 0.8  # potencia de una unidad sin adiestramiento (sube lineal hasta 1 en el 85 %)


# ---------------------------------------------------------------------------------------------------- configuracion
def _datos(escenario) -> dict:
    try:
        d = json.loads(getattr(escenario, "apresto_json", None) or "{}")
    except ValueError:
        d = {}
    return d if isinstance(d, dict) else {}


def config(escenario, bando: str) -> dict:
    c = {**POR_DEFECTO, **(_datos(escenario).get(bando) or {})}
    c["plazos"] = {**PLAZOS_POR_DEFECTO, **(c.get("plazos") or {})}
    return c


def guardar(escenario, bando: str, **cambios) -> dict:
    d = _datos(escenario)
    c = config(escenario, bando)
    for k, v in cambios.items():
        if v is None:
            continue
        if k == "plazos":
            c["plazos"] = {**c["plazos"], **{e: max(0, int(n)) for e, n in v.items() if e in PLAZOS_POR_DEFECTO}}
        else:
            c[k] = v
    d[bando] = c
    escenario.apresto_json = json.dumps(d)
    return c


def iniciar_pcao(escenario, bando: str, turno: int, plazos: dict | None = None) -> dict:
    """Ordena la PCAO: desde este turno corren los 5 eventos con sus plazos."""
    return guardar(escenario, bando, pcao_inicio=turno, plazos=plazos)


# ---------------------------------------------------------------------------------------------------- PCAO
def progreso(escenario, bando: str, turno: int) -> dict:
    """Evento en curso de la PCAO (o None si no esta en marcha) y lo que falta."""
    c = config(escenario, bando)
    inicio = c.get("pcao_inicio")
    filas, t = [], inicio or 0
    for clave, nombre in EVENTOS:
        plazo = int(c["plazos"][clave])
        filas.append({"evento": clave, "nombre": nombre, "plazo": plazo, "desde": t, "hasta": t + plazo})
        t += plazo
    if inicio is None:
        return {"activa": False, "terminada": c["grado"] == "completo", "eventos": filas, "actual": None,
                "total": t, "restan": None}
    transcurrido = turno - inicio
    actual = next((i for i, f in enumerate(filas) if turno < f["hasta"]), None)
    for i, f in enumerate(filas):
        f["estado"] = "cumplido" if turno >= f["hasta"] else ("en curso" if i == actual else "pendiente")
    return {"activa": actual is not None, "terminada": actual is None, "eventos": filas, "actual": actual,
            "total": t - inicio, "transcurrido": max(0, transcurrido), "restan": max(0, t - turno)}


def _cumplido(escenario, bando: str, turno: int, evento: str) -> bool:
    c = config(escenario, bando)
    if c["grado"] == "completo":
        return True
    p = progreso(escenario, bando, turno)
    if not p["activa"] and not (c.get("pcao_inicio") is not None and p["terminada"]):
        return False
    return next(f for f in p["eventos"] if f["evento"] == evento).get("estado") == "cumplido"


def reservas_incorporadas(escenario, bando: str, turno: int | None = None) -> bool:
    """Las reservas y la milicia cubren el deficit solo despues del evento 2 (o en completo apresto)."""
    if escenario is None or not getattr(escenario, "apresto_json", None):
        return True
    return _cumplido(escenario, bando, turno if turno is not None else (escenario.turno_actual or 1), "incorporacion")


def fraccion_aeronaves_listas(escenario, bando: str, turno: int | None = None) -> float:
    """Aeronaves listas para despegar (el resto, preservadas) segun el grado, hasta terminar el evento 4."""
    if escenario is None or not getattr(escenario, "apresto_json", None):
        return 1.0
    turno = turno if turno is not None else (escenario.turno_actual or 1)
    if _cumplido(escenario, bando, turno, "material"):
        return 1.0
    c = config(escenario, bando)
    return AERONAVES_LISTAS.get("paz" if c["grado"] == "paz" else int(c.get("fase") or 1), 1.0)


def adiestramiento(escenario, bando: str, turno: int | None = None) -> float:
    """% de adiestramiento del bando: el de base, que sube durante el evento 5 hasta la meta."""
    c = config(escenario, bando)
    base, meta = float(c["adiestramiento"]), max(float(c["adiestramiento"]), float(c["adiestramiento_meta"]))
    if getattr(escenario, "apresto_json", None) is None or c.get("pcao_inicio") is None:
        return base
    turno = turno if turno is not None else (escenario.turno_actual or 1)
    ev = next(f for f in progreso(escenario, bando, turno)["eventos"] if f["evento"] == "adiestramiento")
    if turno >= ev["hasta"]:
        return meta
    if turno <= ev["desde"] or ev["plazo"] <= 0:
        return base
    return base + (meta - base) * (turno - ev["desde"]) / ev["plazo"]


def factor_adiestramiento(escenario, bando: str) -> float:
    """Potencia de combate segun el adiestramiento: 1 desde el minimo del manual (85 %); por debajo, menos."""
    if escenario is None or not getattr(escenario, "apresto_json", None):
        return 1.0
    a = adiestramiento(escenario, bando)
    if a >= MINIMOS["adiestramiento"]:
        return 1.0
    return FACTOR_ADIESTRAMIENTO_MIN + (1 - FACTOR_ADIESTRAMIENTO_MIN) * max(0.0, a) / MINIMOS["adiestramiento"]


# ---------------------------------------------------------------------------------------------------- calificacion
def _pct(v) -> float:
    return round(max(0.0, min(100.0, float(v or 0.0))), 1)


def _c3(escenario, bando: str, unidades, turno: int) -> float:
    """Comando, control y comunicaciones: los centros de comunicaciones en pie y el plan de transmisiones."""
    from app.engine import transmisiones  # importacion tardia: evita un ciclo

    cap = infraestructura.capacidad(unidades, bando, "comunicaciones")
    valor = 100.0 * (1.0 if cap is None else cap)
    if transmisiones.errores(transmisiones.plan(escenario, bando), turno):
        valor *= 0.85  # plan de transmisiones con errores o vencido
    return valor


def _tipo(u) -> str:
    clase = catalogo.obtener(getattr(u, "clase", None), u.tipo)
    if u.tipo == "aerea" and not (clase.misil or clase.se_consume or clase.dron):
        return "aviacion"
    s = defensa_aerea.sistema(u)
    if s is not None:
        return {"zu23_2": "gadaa", "pechora_2m": "pechora", "buk_m2e": "buk"}.get(getattr(u, "modelo", "") or "", "gadaa")
    if clase.id == "radar":
        return "radar"
    return "general"


def calificar(u, fila_toe: dict | None, escenario, unidades, turno: int) -> dict:
    """Calificacion de una unidad: aspectos de la tabla (A-E), exigencias de su tipo (Anexo A) y resultado."""
    bando = u.bando
    tipo = _tipo(u)
    cats = (fila_toe or {}).get("categorias") or {}
    aut = sum(c["autorizado"] for c in cats.values())
    hay = sum(c["existente"] + c["reserva"] + c["milicia"] for c in cats.values())
    personal = 100.0 * hay / aut if aut else _pct(u.fuerza)
    fuerza = _pct(u.fuerza)
    municion = _pct(getattr(u, "municion", 100.0))
    aspectos = {
        "personal": _pct(personal),
        "armamento": min(fuerza, municion),
        "equipamiento": fuerza,
        "adiestramiento": _pct(adiestramiento(escenario, bando, turno)),
        "c3": _pct(_c3(escenario, bando, unidades, turno)),
    }
    exigencias = []  # (texto, valor, minimo, eliminatoria)
    if tipo == "aviacion":
        pilotos = 100.0 * (fila_toe or {}).get("cobertura_pilotos", 1.0)
        tecnicos = 100.0 * (fila_toe or {}).get("cobertura_tecnicos", 1.0)
        listas = 100.0 * fraccion_aeronaves_listas(escenario, bando, turno) * fuerza / 100.0
        if getattr(escenario, "fallas", False):
            from app.engine import disponibilidad  # importacion tardia

            listas *= disponibilidad.tasa_disponibilidad(getattr(u, "modelo", None) or "") * (0.5 + 0.5 * tecnicos / 100.0)
        aspectos["equipamiento"] = _pct(listas)
        exigencias += [("Personal de vuelo presente (A.20.a)", _pct(pilotos), 75, True),
                       ("Aeronaves disponibles para el vuelo (A.20.b)", _pct(listas), 80, True),
                       ("Personal de mantenimiento técnico (A.20.c)", _pct(tecnicos), 75, True),
                       ("Primera carga básica de armamento lista (A.20.i)", municion, 50, False)]
    elif tipo == "gadaa":
        exigencias += [("Personal presente (A.15.a)", aspectos["personal"], 75, True),
                       ("Equipo de combate operativo (A.15.d)", fuerza, 75, True),
                       ("Carga básica de municiones (A.15.e)", municion, 90, True)]
    elif tipo in ("pechora", "buk"):
        s = defensa_aerea.sistema(u)
        cargados = defensa_aerea.cargas(u, s)
        listos = sum(cargados[a.id] for a in s.armas if a.tipo.startswith("misil"))  # misiles en las rampas
        exigencias.append(("Personal presente (A.16.a)", aspectos["personal"], 75, True))
        if tipo == "pechora":
            exigencias.append(("Rampas de lanzamiento listas, al menos 2 (A.16.c.1)", float(listos), 2, True))
        else:
            exigencias.append(("Rampas y cargadores operativos (A.16.c.4)", fuerza, 75, True))
    elif tipo == "radar":
        exigencias += [("Personal presente (A.17.a)", aspectos["personal"], 75, True),
                       ("Radares operativos con repuestos (A.17.b)", fuerza, 80, True)]
    motivos = [f"{NOMBRE_ASPECTO[k]}: {v:g} % (mínimo {MINIMOS[k]} %)" for k, v in aspectos.items() if v < MINIMOS[k]]
    motivos += [f"{t}: {v:g} (mínimo {m})" for t, v, m, elim in exigencias if elim and v < m]
    observaciones = [f"{t}: {v:g} (mínimo {m}; se califica por apreciación)" for t, v, m, elim in exigencias
                     if not elim and v < m]
    return {"unidad_id": u.id, "nombre": u.nombre, "tipo": tipo, "aspectos": aspectos,
            "exigencias": [{"texto": t, "valor": v, "minimo": m, "eliminatoria": e, "cumple": v >= m}
                           for t, v, m, e in exigencias],
            "tiene": not motivos, "motivos": motivos, "observaciones": observaciones}


def resumen(escenario, bando: str, unidades, partes_toe: dict | None = None) -> dict:
    """Grado, PCAO y calificacion de cada unidad del bando (para la pestaña Situacion)."""
    from app.engine import toe  # importacion tardia: toe consulta este modulo

    turno = escenario.turno_actual or 1
    partes_toe = partes_toe or toe.partes(unidades, escenario, bando)
    por_id = {f["unidad_id"]: f for f in partes_toe["unidades"]}
    filas = [calificar(u, por_id.get(u.id), escenario, unidades, turno)
             for u in sorted(unidades, key=lambda x: x.id)
             if u.bando == bando and u.estado == "activa" and u.id in por_id
             and not catalogo.obtener(u.clase, u.tipo).infraestructura]
    c = config(escenario, bando)
    return {"config": c, "grado_nombre": NOMBRE_GRADO[c["grado"]], "fase_nombre": FASES.get(int(c.get("fase") or 1)),
            "pcao": progreso(escenario, bando, turno), "unidades": filas,
            "tienen": sum(1 for f in filas if f["tiene"]), "total": len(filas),
            "aeronaves_listas_pct": round(100 * fraccion_aeronaves_listas(escenario, bando, turno)),
            "reservas_incorporadas": reservas_incorporadas(escenario, bando, turno),
            "minimos": MINIMOS, "aspectos": NOMBRE_ASPECTO, "eventos": [list(e) for e in EVENTOS], "fuente": FUENTE}


def avanzar(escenario, turno: int) -> list[tuple[str, str]]:
    """Eventos de la PCAO que terminan en este turno, y el paso a Completo Apresto: [(bando, texto)]."""
    out = []
    for b in ("azul", "rojo"):
        c = config(escenario, b)
        if c.get("pcao_inicio") is None or c["grado"] == "completo":
            continue
        p = progreso(escenario, b, turno + 1)
        for f in p["eventos"]:
            if f["hasta"] == turno + 1 and f["plazo"] > 0:
                out.append((b, f"PCAO: se cumplió el evento {f['nombre']}."))
        if p["terminada"]:
            guardar(escenario, b, grado="completo")
            out.append((b, "PCAO cumplida: el bando alcanzó el Completo Apresto Operacional."))
    return out


def plazos_del_plan(contenido: dict | None) -> dict | None:
    """Plazos (turnos) de los 5 eventos tomados de la tabla del Plan de PCAO del bando, si los tiene."""
    filas = (contenido or {}).get("eventos") or []
    plazos = {}
    for (clave, _), fila in zip(EVENTOS, filas):
        try:
            plazos[clave] = max(0, int(math.floor(float(str(fila.get("plazo", "")).replace(",", ".")))))
        except (TypeError, ValueError):
            return None
    return plazos if len(plazos) == len(EVENTOS) else None
