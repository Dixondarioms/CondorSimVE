"""Misiones aereas: un ROL y una RUTA de navegacion para un grupo aereo (una orden de tareas aereas simplificada).

La ruta es una lista de puntos:
- paso: se sobrevuela sin detenerse;
- orbita: el grupo llega y la mantiene N turnos (sin contar el de llegada); ahi actua segun su rol;
- blanco: al llegar (o al tener el blanco a su alcance) ataca y sigue;
- aterrizaje: ultimo punto, en una base aerea propia (la municion merodeadora termina en el blanco).

Una mision puede ser para un grupo que ya existe (la conduce Operaciones, A3) o para un grupo que despegara de una
base en un turno programado (la planifica Planificacion, A5): asi se arma con anticipacion el plan aereo del dia.
Cada turno el grupo avanza solo por su ruta; una orden directa al grupo reemplaza la mision (redireccionamiento).
Con combustible critico abandona la ruta y regresa a la base mas cercana.

La estimacion (hora de llegada y combustible en cada punto) usa las mismas reglas que la resolucion del turno.
"""

import json
import math
from dataclasses import dataclass
from types import SimpleNamespace

from app.engine import aeronaves as aeronaves_mod
from app.engine import catalogo, geo, logistica, movimiento, vision
from app.engine import clima as clima_mod
from app.engine import guerra_electronica as ge_mod
from app.models.evento import Evento
from app.models.mision import Mision


@dataclass(frozen=True)
class Rol:
    id: str
    nombre: str
    descripcion: str
    requiere: tuple = ()  # tipos de punto obligatorios
    prohibe: tuple = ()  # tipos de punto que no admite
    capacidad: str = ""  # "aire" | "superficie" | "interferencia" | "" (cualquier aeronave)


ROLES: dict[str, Rol] = {r.id: r for r in [
    Rol("CAP", "Patrulla aerea de combate (CAP)",
        "Vuela a una orbita, la mantiene los turnos indicados interceptando a los aviones enemigos detectados a su "
        "alcance y regresa a la base.", ("orbita",), ("blanco",), "aire"),
    Rol("INTERDICCION", "Interdiccion (ataque a un blanco)",
        "Vuela hasta el blanco, lo ataca al tenerlo a su alcance y regresa. Si el blanco ya no esta, ataca al enemigo "
        "detectado mas cercano.", ("blanco",), (), "superficie"),
    Rol("CAS", "Apoyo aereo cercano (CAS)",
        "Orbita sobre la zona de combate y en cada turno ataca al enemigo de superficie detectado mas cercano a su "
        "alcance.", ("orbita",), ("blanco",), "superficie"),
    Rol("SEAD", "Supresion de defensas aereas (SEAD)",
        "Ataca radares y antiaerea: el blanco indicado o, si no lo hay, el emisor enemigo detectado mas cercano.",
        ("blanco",), (), "superficie"),
    Rol("RECO", "Reconocimiento",
        "Recorre la ruta (con orbitas, si se indican) para detectar al enemigo, sin atacar.", (), ("blanco",), ""),
    Rol("GE", "Guerra electronica (interferencia en orbita)",
        "Mantiene una orbita e interfiere cada turno sobre ella (sensores, antiaerea y drones enemigos).",
        ("orbita",), ("blanco",), "interferencia"),
    Rol("TRASLADO", "Traslado a otra base",
        "Vuela la ruta y aterriza en la base indicada.", (), ("orbita", "blanco"), ""),
    Rol("ESCOLTA", "Escolta de otra mision",
        "Vuela junto al grupo de la mision escoltada e intercepta a los aviones enemigos que lo amenacen; cuando esa "
        "mision termina, regresa a la base indicada.", ("aterrizaje",), ("orbita", "blanco"), "aire"),
]}
RADIO_ESCOLTA_KM = 8.0  # distancia a la que el escolta se coloca del grupo escoltado
TIPOS_PUNTO = ("paso", "orbita", "blanco", "aterrizaje")
MAX_PUNTOS = 12
MAX_TURNOS_ORBITA = 12
MAX_ANTICIPACION_TURNOS = 24
LLEGADA_KM = 1.0
ACTIVAS = ("programada", "en_curso")


def roles_publicos() -> dict:
    return {
        "roles": [{"id": r.id, "nombre": r.nombre, "descripcion": r.descripcion, "requiere": list(r.requiere),
                   "prohibe": list(r.prohibe), "capacidad": r.capacidad} for r in ROLES.values()],
        "tipos_punto": list(TIPOS_PUNTO), "max_puntos": MAX_PUNTOS, "max_turnos_orbita": MAX_TURNOS_ORBITA,
        "max_anticipacion_turnos": MAX_ANTICIPACION_TURNOS,
    }


# ---------------------------------------------------------------------------------------------------------------
# Planificacion: validacion y estimacion
# ---------------------------------------------------------------------------------------------------------------
def clase_de_modelo(modelo_id: str):
    m = catalogo.MODELOS.get(modelo_id or "")
    return None if m is None else catalogo.perfil(SimpleNamespace(clase=m.clase, tipo="aerea", modelo=m.id))


def velocidad_efectiva(velocidad_kmh: float, clase, clima, lat=None, lon=None) -> float:
    return velocidad_kmh * clima_mod.factor_movimiento(clima, "aerea", lat, lon) * (1.0 - clase.penalizacion_movilidad)


def validar(rol_id: str, puntos: list, clase) -> list[str]:
    """Errores de la mision (lista vacia si es valida)."""
    rol = ROLES.get(rol_id)
    if rol is None:
        return ["Rol de mision desconocido."]
    if not puntos:
        return ["La ruta no tiene puntos."]
    errores = []
    tipos = [p.get("tipo") for p in puntos]
    if len(puntos) > MAX_PUNTOS:
        errores.append(f"Maximo {MAX_PUNTOS} puntos por mision.")
    if any(t not in TIPOS_PUNTO for t in tipos):
        errores.append("Tipo de punto desconocido.")
    if clase.se_consume:
        if rol.id not in ("INTERDICCION", "SEAD"):
            errores.append("La municion merodeadora solo cumple misiones de interdiccion o SEAD.")
        if tipos[-1] != "blanco":
            errores.append("La municion merodeadora termina su ruta en el blanco (se destruye al impactar).")
    elif tipos[-1] != "aterrizaje":
        errores.append("La ruta debe terminar con el aterrizaje en una base propia.")
    if "aterrizaje" in tipos[:-1]:
        errores.append("El aterrizaje solo puede ser el ultimo punto.")
    for t in rol.requiere:
        if t not in tipos:
            errores.append(f"El rol {rol.nombre} necesita al menos un punto de tipo {t}.")
    for t in rol.prohibe:
        if t in tipos:
            errores.append(f"El rol {rol.nombre} no admite puntos de tipo {t}.")
    if any(p.get("tipo") == "orbita" and not 1 <= int(p.get("turnos") or 0) <= MAX_TURNOS_ORBITA for p in puntos):
        errores.append(f"Cada orbita dura entre 1 y {MAX_TURNOS_ORBITA} turnos.")
    if rol.capacidad == "aire" and clase.ataque_vs.get("aerea", 0.0) <= 0:
        errores.append(f"{clase.nombre} no puede interceptar aviones: no sirve para {rol.nombre}.")
    if rol.capacidad == "superficie" and max(clase.ataque_vs.get("terrestre", 0.0), clase.ataque_vs.get("naval", 0.0)) <= 0:
        errores.append(f"{clase.nombre} no puede atacar blancos de superficie: no sirve para {rol.nombre}.")
    if rol.capacidad == "interferencia" and clase.interferencia_km <= 0:
        errores.append(f"{clase.nombre} no puede interferir: no sirve para {rol.nombre}.")
    return errores


def estimar(lat: float, lon: float, velocidad_kmh: float, autonomia_km: float, combustible: float, puntos: list) -> dict:
    """Hora (horas desde el despegue) y combustible (%) estimados en cada punto de la ruta.

    Igual que en la resolucion: el grupo se detiene en cada orbita o blanco el resto del turno en que llega; la
    orbita dura N turnos completos y gasta el combustible de espera; el vuelo gasta segun la autonomia."""
    vel, aut = max(velocidad_kmh, 1e-6), max(autonomia_km, 1e-6)
    horas, comb = 0.0, float(combustible)
    filas, avisos = [], []
    prev = (lat, lon)
    for i, p in enumerate(puntos):
        d = geo.distancia_km(prev[0], prev[1], p["lat"], p["lon"])
        horas += d / vel
        comb -= d / aut * 100.0
        fila = {"tipo": p["tipo"], "km": round(d, 1), "llegada_h": round(horas, 2), "combustible_llegada": round(comb, 1)}
        if p["tipo"] == "orbita":
            t = int(p.get("turnos") or 1)
            horas = math.floor(horas + 1e-9) + 1 + t
            comb -= t * aeronaves_mod.COMBUSTIBLE_LOITER
            fila.update(salida_h=round(horas, 2), combustible_salida=round(comb, 1))
        elif p["tipo"] == "blanco":
            horas = math.floor(horas + 1e-9) + 1
            fila["salida_h"] = round(horas, 2)
        if comb < 0:
            if not any(a.startswith("No alcanza") for a in avisos):
                avisos.append(f"No alcanza el combustible: se quedaria sin combustible antes del punto {i + 1}.")
        elif comb <= aeronaves_mod.COMBUSTIBLE_CRITICO and i < len(puntos) - 1 and not avisos:
            avisos.append(f"Llegaria al punto {i + 1} con combustible critico ({comb:.0f} %): abandonara la ruta y "
                          "regresara antes.")
        filas.append(fila)
        prev = (p["lat"], p["lon"])
    return {"puntos": filas, "duracion_h": round(horas, 2), "combustible_final": round(comb, 1), "advertencias": avisos}


# ---------------------------------------------------------------------------------------------------------------
# Consultas y serializacion
# ---------------------------------------------------------------------------------------------------------------
def escolta_de(m: Mision) -> int | None:
    """Id de la mision que escolta (rol ESCOLTA), guardado en el plan."""
    try:
        v = json.loads(m.plan_json or "{}").get("escolta_de")
    except ValueError:
        return None
    return int(v) if v else None


def _seguir_escoltado(db, m: Mision, u, unidades: dict, lista, terreno, clima, obras, bit, turno: int) -> bool:
    """Escolta: se coloca junto al grupo escoltado y patrulla alli. Devuelve True si sigue escoltando; False si la
    mision escoltada termino (o no existe) y el escolta debe seguir su propia ruta (el aterrizaje)."""
    e = db.get(Mision, escolta_de(m) or -1)
    escoltado = unidades.get(e.unidad_id) if e is not None and e.unidad_id else None
    if e is None or e.escenario_id != m.escenario_id or e.estado not in ACTIVAS:
        return False
    if e.estado == "programada" or escoltado is None or escoltado.estado != "activa" or escoltado.en_tierra:
        # el escoltado aun no despego (o esta en tierra): el escolta patrulla donde esta y espera
        bit.poner(u, "combustible", u.combustible - aeronaves_mod.COMBUSTIBLE_LOITER, "mision")
        u.mision, u.mision_lat, u.mision_lon = "patrulla", u.lat, u.lon
        m.resultado = f"Espera en el aire al grupo de {e.nombre or e.rol}."
        return True
    d = geo.distancia_km(u.lat, u.lon, escoltado.lat, escoltado.lon)
    if d > RADIO_ESCOLTA_KM:
        mov = movimiento.simular(u, [[escoltado.lat, escoltado.lon]], terreno, clima, obras)
        u.lat, u.lon = mov.lat, mov.lon
        bit.poner(u, "combustible", u.combustible - mov.combustible_gastado, "mision")
        d = geo.distancia_km(u.lat, u.lon, escoltado.lat, escoltado.lon)
    else:
        bit.poner(u, "combustible", u.combustible - aeronaves_mod.COMBUSTIBLE_LOITER, "mision")
    u.mision, u.mision_lat, u.mision_lon = "patrulla", u.lat, u.lon  # intercepta lo que amenace al grupo
    m.resultado = (f"Escolta a {escoltado.nombre} ({d:.0f} km)." if d <= RADIO_ESCOLTA_KM
                   else f"Alcanza a {escoltado.nombre}: faltan {d:.0f} km.")
    return True


def puntos_de(m: Mision) -> list:
    return json.loads(m.puntos_json or "[]")


def visibles_para(db, escenario, rol: str) -> list[Mision]:
    """Cada bando ve solo sus misiones; instructor y observador, todas."""
    q = db.query(Mision).filter(Mision.escenario_id == escenario.id)
    if rol in ("azul", "rojo"):
        q = q.filter(Mision.bando == rol)
    return q.order_by(Mision.id.desc()).limit(80).all()


def aeronaves_programadas(db, escenario_id: int, bando: str, drones: bool) -> int:
    """Aeronaves de las misiones que aun deben despegar de una base (cuentan para el tope del bando)."""
    return sum(
        m.aeronaves or 0 for m in db.query(Mision).filter(
            Mision.escenario_id == escenario_id, Mision.bando == bando, Mision.estado == "programada",
            Mision.unidad_id.is_(None))
        if aeronaves_mod.es_dron_modelo(m.modelo) == drones
    )


def serializar(m: Mision) -> dict:
    rol = ROLES.get(m.rol)
    return {
        "id": m.id, "bando": m.bando, "rol": m.rol, "rol_nombre": rol.nombre if rol else m.rol, "nombre": m.nombre,
        "estado": m.estado, "unidad_id": m.unidad_id, "base_id": m.base_id, "modelo": m.modelo,
        "aeronaves": m.aeronaves, "turno_despegue": m.turno_despegue, "creada_turno": m.creada_turno,
        "puntos": puntos_de(m), "plan": json.loads(m.plan_json or "{}"), "indice": m.indice, "espera": m.espera,
        "resultado": m.resultado, "escolta_de": escolta_de(m),
    }


def _evento(db, m: Mision, turno: int, texto: str) -> None:
    db.add(Evento(escenario_id=m.escenario_id, turno=turno, tipo="mision", bando_destino=m.bando,
                  descripcion=f"Mision {m.id} ({m.rol}{' ' + m.nombre if m.nombre else ''}): {texto}"))


def _terminar(db, m: Mision, estado: str, texto: str, turno: int) -> None:
    m.estado, m.resultado = estado, texto[:300]
    _evento(db, m, turno, texto)


# ---------------------------------------------------------------------------------------------------------------
# Cambios fuera de la resolucion (API)
# ---------------------------------------------------------------------------------------------------------------
def cancelar_por_orden(db, unidad, tipo_orden: str) -> None:
    """Una orden directa a un grupo reemplaza su mision (redireccionamiento)."""
    for m in db.query(Mision).filter(Mision.escenario_id == unidad.escenario_id, Mision.unidad_id == unidad.id,
                                     Mision.estado.in_(ACTIVAS)):
        m.estado = "abortada" if m.estado == "en_curso" else "cancelada"
        m.resultado = f"Reemplazada por una orden directa ({tipo_orden})."


def abortar(m: Mision, unidades: list) -> None:
    """Cancela una mision programada; una en curso abandona la ruta y regresa a la base propia mas cercana."""
    if m.estado == "programada":
        m.estado, m.resultado = "cancelada", "Cancelada antes de iniciarse."
        return
    u = next((x for x in unidades if x.id == m.unidad_id), None)
    base = aeronaves_mod.base_mas_cercana(u, unidades) if u is not None and not u.en_tierra else None
    if base is None:
        m.estado, m.resultado = "abortada", "Abortada."
        return
    m.puntos_json = json.dumps([{"tipo": "aterrizaje", "lat": base.lat, "lon": base.lon, "base_id": base.id}])
    m.indice, m.espera = 0, -1
    m.resultado = f"Abortada: regresa a {base.nombre}."
    u.mision, u.mision_lat, u.mision_lon = "", None, None


# ---------------------------------------------------------------------------------------------------------------
# Resolucion del turno (la llama engine/orders.py)
# ---------------------------------------------------------------------------------------------------------------
def _tipo_efectivo(x) -> str:
    return "terrestre" if x.tipo == "base" or getattr(x, "en_tierra", False) else x.tipo


def _visible(x, bando: str, lista, terreno, clima, ge) -> bool:
    if ge is not None and ge.emite(x):
        return True
    return any(d.bando == bando and d.estado == "activa" and d.deteccion_km and vision.detecta(d, x, terreno, clima, ge)
               for d in lista)


def _blanco_automatico(u, rol_id: str, lista, terreno, clima, ge):
    """Enemigo de superficie detectado mas cercano al alcance del grupo (SEAD prefiere radares y antiaerea)."""
    clase = catalogo.perfil(u)
    candidatos = [
        x for x in lista
        if x.bando != u.bando and x.estado == "activa" and _tipo_efectivo(x) != "aerea"
        and clase.ataque_vs.get(_tipo_efectivo(x), 0.0) > 0
        and geo.distancia_km(u.lat, u.lon, x.lat, x.lon) <= u.alcance_km
        and _visible(x, u.bando, lista, terreno, clima, ge)
    ]
    if rol_id == "SEAD":
        emisores = [x for x in candidatos if ge_mod.emite_radar(x) or (ge is not None and ge.emite(x))]
        candidatos = emisores or candidatos
    return min(candidatos, key=lambda x: geo.distancia_km(u.lat, u.lon, x.lat, x.lon), default=None)


def activar(db, escenario, unidades: dict, lista: list, turno: int, lanzados_en_base: dict) -> None:
    """Inicia las misiones programadas para este turno: hace despegar los grupos nuevos desde su base y pone en
    ruta a los grupos existentes (los que estan en tierra, si ya terminaron de reabastecerse)."""
    pendientes = db.query(Mision).filter(
        Mision.escenario_id == escenario.id, Mision.estado == "programada", Mision.turno_despegue <= turno
    ).order_by(Mision.id).all()
    for m in pendientes:
        if m.unidad_id is None:
            base = unidades.get(m.base_id)
            dron = aeronaves_mod.es_dron_modelo(m.modelo)
            motivo = "La base ya no existe." if base is None else aeronaves_mod.error_de_despegue(
                base, m.modelo, m.aeronaves,
                aeronaves_mod.aeronaves_en_servicio((x for x in lista if x.bando == m.bando), dron))
            if motivo:
                _terminar(db, m, "cancelada", f"No pudo despegar: {motivo}", turno)
                continue
            grupo = aeronaves_mod.crear_grupo(base, m.modelo, m.aeronaves, m.nombre, lanzados_en_base[base.id])
            lanzados_en_base[base.id] += 1
            logistica.descontar_despegue(base, m.aeronaves)
            db.add(grupo)
            db.flush()
            unidades[grupo.id] = grupo
            lista.append(grupo)
            m.unidad_id = grupo.id
            _evento(db, m, turno, f"{grupo.nombre} despego de {base.nombre}.")
        else:
            u = unidades.get(m.unidad_id)
            if u is None or u.estado != "activa":
                _terminar(db, m, "fallida", "El grupo ya no esta activo.", turno)
                continue
            if u.en_tierra and u.espera_restante > 0:
                m.resultado = f"Espera en tierra: faltan {u.espera_restante} turno(s) para reabastecer y rearmar."
                continue
            if u.en_tierra:
                aeronaves_mod.despegar_unidad(u)
            u.mision, u.mision_lat, u.mision_lon = "", None, None
        m.estado, m.indice, m.espera = "en_curso", 0, -1
        m.resultado = "En ruta."


def interferencias(db, escenario, unidades: dict) -> list[tuple]:
    """(grupo, lat, lon) de las misiones de guerra electronica que estan orbitando: interfieren solas este turno."""
    salida = []
    for m in db.query(Mision).filter(Mision.escenario_id == escenario.id, Mision.estado == "en_curso",
                                     Mision.rol == "GE").order_by(Mision.id):
        u, pts = unidades.get(m.unidad_id), puntos_de(m)
        if u is None or u.estado != "activa" or m.espera <= 0 or m.indice >= len(pts) or pts[m.indice]["tipo"] != "orbita":
            continue
        p = pts[m.indice]
        centro = p.get("centro") or [p["lat"], p["lon"]]
        if geo.distancia_km(u.lat, u.lon, centro[0], centro[1]) > u.alcance_km:
            centro = [p["lat"], p["lon"]]
        salida.append((u, centro[0], centro[1]))
    return salida


def avanzar(db, escenario, unidades: dict, lista: list, con_orden: set, terreno, clima: str, obras, ge, bit,
            turno: int) -> tuple[list, set]:
    """Hace avanzar cada mision en curso un turno. Devuelve los ataques que pide ([(atacante_id, blanco_id)]) y los
    ids de los grupos que conduce (no reciben ademas la logica de patrulla libre)."""
    ataques, bajo_mision = [], set()
    for m in db.query(Mision).filter(Mision.escenario_id == escenario.id, Mision.estado == "en_curso").order_by(Mision.id):
        u = unidades.get(m.unidad_id)
        if u is None or u.estado != "activa":
            continue  # cerrar() la da por fallida al final del turno
        if u.id in con_orden:
            _terminar(db, m, "abortada", "Redirigida por una orden directa.", turno)
            continue
        if u.en_tierra:
            _terminar(db, m, "abortada", "El grupo aterrizo antes de completar la ruta.", turno)
            continue
        bajo_mision.add(u.id)
        pts = puntos_de(m)
        if m.indice >= len(pts):
            _terminar(db, m, "cumplida", "Ruta completada.", turno)
            continue
        if ge_mod.enlace_perdido(u, ge):
            bit.poner(u, "combustible", u.combustible - aeronaves_mod.COMBUSTIBLE_LOITER, "mision")
            m.resultado = ge_mod.MOTIVO_SIN_ENLACE
            continue
        # ---- escolta: acompaña al grupo escoltado mientras su mision siga; luego vuelve a la base ----
        if m.rol == "ESCOLTA" and m.indice < len(pts) - 1 or (m.rol == "ESCOLTA" and m.indice == 0 and len(pts) == 1 and m.espera != -2):
            if u.combustible > aeronaves_mod.COMBUSTIBLE_CRITICO and _seguir_escoltado(db, m, u, unidades, lista, terreno, clima, obras, bit, turno):
                continue
            m.espera = -2  # marca: la escolta termino, sigue su ruta al aterrizaje
            u.mision, u.mision_lat, u.mision_lon = "", None, None
            _evento(db, m, turno, "La mision escoltada termino: regresa a la base.")
        # combustible critico: abandona la ruta y regresa a la base propia mas cercana
        if (u.combustible <= aeronaves_mod.COMBUSTIBLE_CRITICO and pts[-1]["tipo"] == "aterrizaje"
                and len(pts) - m.indice > 1):
            base = aeronaves_mod.base_mas_cercana(u, lista)
            if base is not None:
                pts = [{"tipo": "aterrizaje", "lat": base.lat, "lon": base.lon, "base_id": base.id}]
                m.puntos_json, m.indice, m.espera = json.dumps(pts), 0, -1
                u.mision, u.mision_lat, u.mision_lon = "", None, None
                _evento(db, m, turno, f"Combustible critico ({u.combustible:.0f} %): abandona la ruta y regresa a {base.nombre}.")

        p = pts[m.indice]
        # ---- en orbita: actua segun el rol ----
        if p["tipo"] == "orbita" and m.espera > 0:
            bit.poner(u, "combustible", u.combustible - aeronaves_mod.COMBUSTIBLE_LOITER, "mision")
            if m.rol == "CAP":
                u.mision, u.mision_lat, u.mision_lon = "patrulla", p["lat"], p["lon"]
            elif m.rol == "CAS":
                blanco = _blanco_automatico(u, "CAS", lista, terreno, clima, ge)
                if blanco is not None:
                    ataques.append((u.id, blanco.id))
            m.espera -= 1
            if m.espera <= 0:  # sigue patrullando este ultimo turno; deja la zona al reanudar el vuelo
                m.indice, m.espera = m.indice + 1, -1
                m.resultado = "Termina la orbita y sigue la ruta."
            else:
                m.resultado = f"En orbita: {m.espera} turno(s) mas."
            continue

        # ---- vuelo hacia el proximo punto de detencion (los puntos de paso se atraviesan) ----
        if u.mision == "patrulla":  # dejo la orbita: ya no vigila la zona
            u.mision, u.mision_lat, u.mision_lon = "", None, None
        i0 = j = m.indice
        while j < len(pts) - 1 and pts[j]["tipo"] == "paso":
            j += 1
        destino = pts[j]
        objetivo = None
        if destino["tipo"] == "blanco" and destino.get("objetivo_unidad_id"):
            x = unidades.get(destino["objetivo_unidad_id"])
            if x is not None and x.estado == "activa" and x.bando != u.bando:
                objetivo = x
        wps = [[q["lat"], q["lon"]] for q in pts[i0:j + 1]]
        if objetivo is not None and _visible(objetivo, u.bando, lista, terreno, clima, ge):
            wps[-1] = [objetivo.lat, objetivo.lon]  # el blanco se movio y se lo sigue viendo: se lo persigue
        origen = (u.lat, u.lon)
        mov = movimiento.simular(u, wps, terreno, clima, obras)
        u.lat, u.lon = mov.lat, mov.lon
        bit.poner(u, "combustible", u.combustible - mov.combustible_gastado, "mision")
        acumulado, previo = 0.0, origen
        for k, wp in enumerate(wps[:-1]):
            acumulado += geo.distancia_km(previo[0], previo[1], wp[0], wp[1])
            previo = wp
            if acumulado <= mov.km_reales + 0.5:
                m.indice = i0 + k + 1
        faltan = geo.distancia_km(u.lat, u.lon, wps[-1][0], wps[-1][1])
        llego = faltan <= LLEGADA_KM

        if destino["tipo"] == "orbita":
            if llego:
                m.indice, m.espera = j, int(destino.get("turnos") or 1)
                if m.rol == "CAP":
                    u.mision, u.mision_lat, u.mision_lon = "patrulla", destino["lat"], destino["lon"]
                m.resultado = f"Llega a la orbita; la mantiene {m.espera} turno(s)."
            else:
                m.resultado = f"Vuela hacia la orbita: faltan {faltan:.0f} km."
        elif destino["tipo"] == "blanco":
            en_alcance = objetivo is not None and geo.distancia_km(u.lat, u.lon, objetivo.lat, objetivo.lon) <= u.alcance_km
            if en_alcance or llego:
                m.indice = j + 1
                blanco = objetivo if en_alcance else _blanco_automatico(u, m.rol, lista, terreno, clima, ge)
                if blanco is not None:
                    ataques.append((u.id, blanco.id))
                    m.resultado = f"Ataca a {blanco.nombre}."
                else:
                    m.resultado = "Llega al blanco pero no encuentra enemigos a su alcance."
                    _evento(db, m, turno, m.resultado)
            else:
                m.resultado = f"Vuela hacia el blanco: faltan {faltan:.0f} km."
        elif destino["tipo"] == "aterrizaje":
            base = unidades.get(destino.get("base_id"))
            if llego or (base is not None and geo.distancia_km(u.lat, u.lon, base.lat, base.lon) <= aeronaves_mod.RADIO_ATERRIZAJE_KM):
                motivo = aeronaves_mod.error_de_aterrizaje(u, base, lista)
                if motivo is None:
                    aeronaves_mod.aterrizar(u, base, len(aeronaves_mod.estacionadas(base, lista)))
                    m.indice = len(pts)
                    _terminar(db, m, "cumplida", f"Mision cumplida: aterrizo en {base.nombre}.", turno)
                else:
                    otra = aeronaves_mod.base_mas_cercana(u, lista)
                    if otra is not None and otra is not base:
                        pts[j] = {"tipo": "aterrizaje", "lat": otra.lat, "lon": otra.lon, "base_id": otra.id}
                        m.puntos_json = json.dumps(pts)
                        m.resultado = f"{motivo} Se desvia a {otra.nombre}."
                        _evento(db, m, turno, m.resultado)
                    else:
                        _terminar(db, m, "abortada", f"{motivo} No hay otra base disponible.", turno)
            else:
                m.resultado = f"Regresa a {base.nombre if base else 'la base'}: faltan {faltan:.0f} km."
    return ataques, bajo_mision


def cerrar(db, escenario, unidades: dict, turno: int) -> None:
    """Al final del turno: las misiones cuyo grupo fue destruido terminan (la municion merodeadora que impacto
    en su blanco cumplio la mision)."""
    for m in db.query(Mision).filter(Mision.escenario_id == escenario.id, Mision.estado == "en_curso"):
        u = unidades.get(m.unidad_id)
        if u is not None and u.estado == "activa":
            continue
        if u is not None and catalogo.obtener(u.clase, u.tipo).se_consume and m.indice >= len(puntos_de(m)):
            _terminar(db, m, "cumplida", "La municion merodeadora impacto en su blanco.", turno)
        else:
            _terminar(db, m, "fallida", "El grupo fue derribado o se perdio.", turno)
