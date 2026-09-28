"""Resolucion de ordenes de un turno, en fases:

0. Despegues: los grupos aereos pedidos a una base aerea nacen junto a ella (ver engine/aeronaves.py).
1. Movimiento (terreno, rios/obras, clima, peso y combustible; ver engine/movimiento.py) y
   construccion de puentes y vados por los ingenieros.
2. Apoyos: se registra que unidades apoyan a cuales.
3. Combates simultaneos: todos se calculan con las fuerzas de inicio de fase y las perdidas se
   aplican juntas, de modo que el resultado no depende del orden en que se emitieron las ordenes.
   Cuentan la sorpresa, la cadencia de fuego, el despliegue y la recarga de cada plataforma.
4. Logistica: consumo de municion, reabastecimiento junto a bases y por convoyes, perdida de
   aeronaves sin combustible, contadores de despliegue/recarga y caducidad de las obras.

Cada cambio de combustible, municion o carga queda en `registro_logistico` con su causa.
"""

import json
from collections import defaultdict

from sqlalchemy.orm import Session

from app.engine import aeronaves as aeronaves_mod
from app.engine import azar as azar_mod
from app.engine import catalogo, combat, geo, movimiento, vision
from app.engine import clima as clima_mod
from app.engine.movimiento import TURNO_DURACION_HORAS  # noqa: F401  (reexportado)
from app.models.aar import Combate, RegistroLogistico
from app.models.escenario import Escenario
from app.models.evento import Evento
from app.models.obra import Obra
from app.models.orden import Orden
from app.models.unidad import Unidad
from app.terreno import Terreno, get_terreno

COBERTURA_AEREA_KM = 40.0
BONO_APOYO_MAX_POR_UNIDAD = 0.30  # +30% con la unidad de apoyo a plena fuerza
BONO_APOYO_TOPE = 0.60
MUNICION_POR_ATAQUE = {"terrestre": 25.0, "aerea": 34.0, "naval": 20.0}
MUNICION_POR_APOYO = 10.0
REABASTECIMIENTO_POR_TURNO = 50.0  # puntos de combustible y de municion que da una base
REABASTECIMIENTO_CONVOY = 40.0  # ... y un convoy
CARGA_POR_UNIDAD_CONVOY = 15.0  # suministros que gasta un convoy por cada unidad que reabastece
RECARGA_CONVOY_EN_DEPOSITO = 50.0
BASE_FUERZA_MINIMA = aeronaves_mod.FUERZA_MINIMA_BASE  # una base muy danada deja de reabastecer y de lanzar grupos
SORPRESA_GENERAL = 1.2  # el atacante no fue detectado por el defensor
SORPRESA_EMBOSCADA = 1.5  # ... y el defensor es de los que sufren emboscadas (convoyes)
COSTO_OBRA = {"vado": 30.0, "puente": 60.0}  # % de material (municion) del ingeniero
DURACION_OBRA = {"vado": 4, "puente": 12}  # turnos que sigue en pie


def tipo_efectivo(unidad: Unidad) -> str:
    """Tipo que se usa en el combate: las bases cuentan como objetivos terrestres."""
    return "terrestre" if unidad.tipo == "base" else unidad.tipo


def _tiene_cobertura_aerea(bando: str, lat: float, lon: float, unidades) -> bool:
    return any(
        u.bando == bando
        and u.tipo == "aerea"
        and u.estado == "activa"
        and geo.distancia_km(u.lat, u.lon, lat, lon) <= COBERTURA_AEREA_KM
        for u in unidades
    )


def _bono_apoyo(objetivo: Unidad, apoyos: dict, unidades: dict) -> float:
    bono = 0.0
    for apoyador_id in apoyos.get(objetivo.id, []):
        a = unidades[apoyador_id]
        if a.estado != "activa":
            continue
        if geo.distancia_km(a.lat, a.lon, objetivo.lat, objetivo.lon) <= a.alcance_km:
            escasez = min(1.0, a.municion / MUNICION_POR_APOYO)
            bono += BONO_APOYO_MAX_POR_UNIDAD * a.fuerza / 100.0 * escasez
    return 1.0 + min(bono, BONO_APOYO_TOPE)


def _sorpresa(atacante: Unidad, defensor: Unidad, unidades, terreno: Terreno, clima: str) -> float:
    """Multiplicador de ataque si el bando defensor no detecta al atacante (emboscada)."""
    for x in unidades:
        if x.bando == defensor.bando and x.estado == "activa" and x.deteccion_km:
            if vision.detecta(x, atacante, terreno, clima):
                return 1.0
    return SORPRESA_EMBOSCADA if catalogo.obtener(defensor.clase, defensor.tipo).vulnerable_emboscada else SORPRESA_GENERAL


class _Bitacora:
    """Escribe en `registro_logistico` cada variacion de combustible, municion o carga."""

    def __init__(self, db: Session, escenario: Escenario):
        self.db, self.escenario = db, escenario

    def poner(self, u: Unidad, variable: str, valor: float, causa: str, orden_id: int | None = None) -> None:
        antes = getattr(u, variable)
        valor = max(0.0, min(100.0, valor))
        if abs(valor - antes) < 0.05:
            return
        setattr(u, variable, valor)
        self.db.add(RegistroLogistico(
            escenario_id=self.escenario.id, turno=self.escenario.turno_actual, unidad_id=u.id,
            unidad_nombre=u.nombre, bando=u.bando, variable=variable, antes=round(antes, 2),
            despues=round(valor, 2), causa=causa, orden_id=orden_id,
        ))


def _reabastecer(unidades: list[Unidad], bit: _Bitacora) -> None:
    """Bases (+50 %) y despues convoyes con carga (+40 %); los convoyes se rellenan en los depositos."""
    bases = [
        u for u in unidades
        if u.tipo == "base" and u.estado == "activa" and u.fuerza >= BASE_FUERZA_MINIMA
    ]
    for u in unidades:
        if u.tipo == "base" or u.estado != "activa":
            continue
        for b in bases:
            if b.bando != u.bando or u.tipo not in catalogo.obtener(b.clase, "base").suministra:
                continue
            if geo.distancia_km(b.lat, b.lon, u.lat, u.lon) <= b.alcance_km:
                bit.poner(u, "combustible", u.combustible + REABASTECIMIENTO_POR_TURNO, "reabastecimiento")
                bit.poner(u, "municion", u.municion + REABASTECIMIENTO_POR_TURNO, "reabastecimiento")
                if catalogo.obtener(u.clase, u.tipo).carga_max:
                    bit.poner(u, "carga", u.carga + RECARGA_CONVOY_EN_DEPOSITO, "reabastecimiento")
                break

    for conv in unidades:
        clase = catalogo.obtener(conv.clase, conv.tipo)
        if conv.estado != "activa" or not clase.nodo_movil_km:
            continue
        for r in unidades:
            if conv.carga < CARGA_POR_UNIDAD_CONVOY:
                break
            if r is conv or r.estado != "activa" or r.bando != conv.bando or r.tipo not in clase.suministra:
                continue
            if r.combustible >= 100 and r.municion >= 100:
                continue
            if geo.distancia_km(conv.lat, conv.lon, r.lat, r.lon) <= clase.nodo_movil_km:
                bit.poner(r, "combustible", r.combustible + REABASTECIMIENTO_CONVOY, "convoy")
                bit.poner(r, "municion", r.municion + REABASTECIMIENTO_CONVOY, "convoy")
                bit.poner(conv, "carga", conv.carga - CARGA_POR_UNIDAD_CONVOY, "convoy")


def procesar_ordenes(
    db: Session, escenario: Escenario, terreno: Terreno | None = None
) -> list[Orden]:
    terreno = terreno or get_terreno()
    clima = escenario.clima
    turno = escenario.turno_actual
    bit = _Bitacora(db, escenario)

    ordenes = (
        db.query(Orden)
        .filter(Orden.escenario_id == escenario.id, Orden.estado == "pendiente")
        .order_by(Orden.id)
        .all()
    )
    unidades = {u.id: u for u in db.query(Unidad).filter(Unidad.escenario_id == escenario.id)}
    lista_unidades = list(unidades.values())
    obras = db.query(Obra).filter(Obra.escenario_id == escenario.id, Obra.expira_turno >= turno).all()
    movidas: set[int] = set()
    dispararon: set[int] = set()

    def rechazar(orden: Orden, motivo: str) -> None:
        orden.estado = "rechazada"
        orden.resultado = motivo

    # ---- Fase 0: despegue de grupos aereos ----
    lanzados_en_base: dict[int, int] = defaultdict(int)
    for orden in [o for o in ordenes if o.tipo == "despegar"]:
        base = unidades.get(orden.unidad_id)
        datos = aeronaves_mod.decodificar(orden.detalle)
        modelo_id, n = datos.get("modelo"), datos.get("aeronaves")
        motivo = (
            "La base no existe." if base is None
            else aeronaves_mod.error_de_despegue(
                base, modelo_id, n, aeronaves_mod.aeronaves_en_servicio(u for u in lista_unidades if u.bando == base.bando)
            )
        )
        if motivo:
            rechazar(orden, motivo)
            continue
        grupo = aeronaves_mod.crear_grupo(base, modelo_id, n, datos.get("indicativo", ""), lanzados_en_base[base.id])
        lanzados_en_base[base.id] += 1
        db.add(grupo)
        db.flush()  # asigna el id: el grupo participa en la logistica de este turno
        unidades[grupo.id] = grupo
        lista_unidades.append(grupo)
        modelo = catalogo.MODELOS[modelo_id]
        orden.estado = "resuelta"
        orden.resultado = f"{grupo.nombre} ({modelo.corto} x{n}) despego de {base.nombre}; podra recibir ordenes el proximo turno."
        db.add(Evento(
            escenario_id=escenario.id, turno=turno, tipo="despegue", bando_destino=base.bando,
            descripcion=f"Despego {grupo.nombre} ({modelo.corto} x{n}) desde {base.nombre}.",
        ))

    # ---- Fase 1: movimiento ----
    for orden in [o for o in ordenes if o.tipo == "mover"]:
        u = unidades.get(orden.unidad_id)
        waypoints = json.loads(orden.waypoints_json or "[]")
        if u is None or u.estado != "activa":
            rechazar(orden, "La unidad no esta activa.")
        elif not waypoints:
            rechazar(orden, "Orden de movimiento sin waypoints.")
        elif u.tipo == "base" or u.velocidad_kmh <= 0:
            rechazar(orden, "La unidad no puede moverse.")
        else:
            mov = movimiento.simular(u, waypoints, terreno, clima, obras)
            if mov.km_reales > 0:
                movidas.add(u.id)
            u.lat, u.lon = mov.lat, mov.lon
            bit.poner(u, "combustible", u.combustible - mov.combustible_gastado, "movimiento", orden.id)
            orden.estado = "resuelta"
            orden.resultado = (
                f"Unidad en ({u.lat:.4f}, {u.lon:.4f}); recorrio {mov.km_reales:.1f} km, "
                f"combustible {u.combustible:.0f}%. {mov.nota}"
            ).strip()

    # ---- Fase 1b: construccion de puentes y vados ----
    for orden in [o for o in ordenes if o.tipo == "construir"]:
        u = unidades.get(orden.unidad_id)
        sitio = (json.loads(orden.waypoints_json or "[]") or [None])[0]
        tipo_obra = orden.detalle
        if u is None or u.estado != "activa" or not catalogo.obtener(u.clase, u.tipo).construye:
            rechazar(orden, "Solo los ingenieros activos pueden construir.")
        elif tipo_obra not in COSTO_OBRA or sitio is None:
            rechazar(orden, "Indique si es un puente o un vado y el punto de construccion.")
        elif geo.distancia_km(u.lat, u.lon, sitio[0], sitio[1]) > u.alcance_km:
            rechazar(orden, f"El punto esta fuera del alcance de trabajo ({u.alcance_km:.0f} km).")
        elif not terreno.hay_rio_cerca(sitio[0], sitio[1], 1.0):
            rechazar(orden, "El punto no esta sobre un rio.")
        elif any(geo.distancia_km(o.lat, o.lon, sitio[0], sitio[1]) < o.radio_km for o in obras):
            rechazar(orden, "Ya hay una obra en ese punto.")
        elif u.municion < COSTO_OBRA[tipo_obra]:
            rechazar(orden, f"Material insuficiente ({u.municion:.0f}% < {COSTO_OBRA[tipo_obra]:.0f}%).")
        else:
            bit.poner(u, "municion", u.municion - COSTO_OBRA[tipo_obra], "construccion", orden.id)
            obra = Obra(
                escenario_id=escenario.id, unidad_id=u.id, bando=u.bando, tipo=tipo_obra, lat=sitio[0],
                lon=sitio[1], radio_km=movimiento.OBRA_RADIO_KM, creada_turno=turno,
                expira_turno=turno + DURACION_OBRA[tipo_obra],
            )
            db.add(obra)
            obras.append(obra)
            orden.estado = "resuelta"
            orden.resultado = (
                f"{tipo_obra.capitalize()} tendido en ({sitio[0]:.4f}, {sitio[1]:.4f}); "
                f"transitable hasta el turno {obra.expira_turno}."
            )

    # ---- Fase 2: apoyos ----
    apoyos: dict[int, list[int]] = defaultdict(list)
    ordenes_apoyo = []
    for orden in [o for o in ordenes if o.tipo == "apoyar"]:
        a = unidades.get(orden.unidad_id)
        obj = unidades.get(orden.objetivo_unidad_id) if orden.objetivo_unidad_id else None
        if a is None or a.estado != "activa" or a.tipo == "base":
            rechazar(orden, "La unidad de apoyo no esta activa.")
        elif a.municion <= 0:
            rechazar(orden, "Sin municion para apoyar.")
        elif obj is None or obj.bando != a.bando or obj.id == a.id or obj.estado != "activa":
            rechazar(orden, "Objetivo de apoyo invalido (debe ser otra unidad propia activa).")
        elif geo.distancia_km(a.lat, a.lon, obj.lat, obj.lon) > a.alcance_km:
            rechazar(orden, f"{obj.nombre} fuera del alcance de apoyo.")
        else:
            apoyos[obj.id].append(a.id)
            ordenes_apoyo.append((orden, a, obj))

    # ---- Fase 3: combates simultaneos ----
    fuerza_inicial = {uid: u.fuerza for uid, u in unidades.items()}
    perdidas: dict[int, float] = defaultdict(float)
    gasto_municion: dict[int, float] = defaultdict(float)
    orden_de_ataque: dict[int, int] = {}

    for orden in [o for o in ordenes if o.tipo == "atacar"]:
        a = unidades.get(orden.unidad_id)
        d = unidades.get(orden.objetivo_unidad_id) if orden.objetivo_unidad_id else None
        if a is None or a.estado != "activa" or a.tipo == "base":
            rechazar(orden, "La unidad atacante no esta activa.")
            continue
        if d is None or d.bando == a.bando or d.estado != "activa":
            rechazar(orden, "Objetivo invalido o ya fuera de combate.")
            continue
        t_a, t_d = tipo_efectivo(a), tipo_efectivo(d)
        clase_a, clase_d = catalogo.perfil(a), catalogo.perfil(d)
        if clase_a.ataque_vs.get(t_d, 0.0) <= 0:
            rechazar(orden, f"{clase_a.nombre} no puede atacar objetivos de tipo {t_d}.")
            continue
        if a.municion <= 0:
            rechazar(orden, "Sin municion.")
            continue
        if a.recarga_restante > 0:
            rechazar(orden, f"Recargando ({a.recarga_restante} turno(s) restante(s)).")
            continue
        if clase_a.despliegue_turnos and (a.id in movidas or a.despliegue_restante > 0):
            faltan = max(a.despliegue_restante, clase_a.despliegue_turnos if a.id in movidas else 0)
            rechazar(orden, f"Desplegando el sistema tras moverse ({faltan} turno(s) quieta).")
            continue
        distancia = geo.distancia_km(a.lat, a.lon, d.lat, d.lon)
        if distancia > a.alcance_km:
            rechazar(orden, f"Objetivo fuera de alcance ({distancia:.1f} km > {a.alcance_km:.1f} km).")
            continue

        consumo = (clase_a.municion_por_ataque or MUNICION_POR_ATAQUE.get(a.tipo, 25.0)) * clase_a.cadencia_fuego
        res = combat.resolver_combate(
            fuerza_atacante=fuerza_inicial[a.id],
            tipo_atacante=t_a,
            fuerza_defensor=fuerza_inicial[d.id],
            tipo_defensor=t_d,
            terreno_defensor=terreno.clase(d.lat, d.lon),
            cobertura_aerea_defensor=_tiene_cobertura_aerea(d.bando, d.lat, d.lon, lista_unidades),
            cobertura_aerea_atacante=_tiene_cobertura_aerea(a.bando, a.lat, a.lon, lista_unidades),
            bono_atacante=_bono_apoyo(a, apoyos, unidades),
            bono_defensor=_bono_apoyo(d, apoyos, unidades),
            factor_ataque=clase_a.ataque_vs.get(t_d, 1.0) * catalogo.factor_grupo(a),
            factor_defensa=clase_d.defensa * catalogo.factor_grupo(d),
            factor_clima=clima_mod.factor_ataque_aereo(clima) if a.tipo == "aerea" else 1.0,
            factor_municion=min(1.0, a.municion / consumo),
            azar=azar_mod.factor_azar(escenario.semilla, turno, a.id, d.id) if escenario.azar else 1.0,
            sorpresa=_sorpresa(a, d, lista_unidades, terreno, clima),
            cadencia=clase_a.cadencia_fuego,
        )
        perdidas[a.id] += fuerza_inicial[a.id] - res.fuerza_atacante_resultante
        perdidas[d.id] += fuerza_inicial[d.id] - res.fuerza_defensor_resultante
        gasto_municion[a.id] += consumo
        orden_de_ataque[a.id] = orden.id
        dispararon.add(a.id)
        orden.estado = "resuelta"
        orden.resultado = f"Ataque a {d.nombre}. {res.resumen}"
        db.add(Combate(
            escenario_id=escenario.id, turno=turno, orden_id=orden.id,
            atacante_id=a.id, defensor_id=d.id, atacante_nombre=a.nombre, defensor_nombre=d.nombre,
            atacante_bando=a.bando, defensor_bando=d.bando, ratio=res.ratio,
            fuerza_ini_atacante=fuerza_inicial[a.id], fuerza_ini_defensor=fuerza_inicial[d.id],
            perdida_atacante=fuerza_inicial[a.id] - res.fuerza_atacante_resultante,
            perdida_defensor=fuerza_inicial[d.id] - res.fuerza_defensor_resultante,
            terreno=terreno.clase(d.lat, d.lon), efectos="; ".join(res.efectos), lat=d.lat, lon=d.lon,
        ))

    for uid, perdida in perdidas.items():
        u = unidades[uid]
        u.fuerza = max(0.0, u.fuerza - perdida)
        if u.fuerza <= 0:
            u.estado = "destruida"
    for uid, gasto in gasto_municion.items():
        bit.poner(unidades[uid], "municion", unidades[uid].municion - gasto, "combate", orden_de_ataque.get(uid))

    for orden, a, obj in ordenes_apoyo:
        bono = _bono_apoyo(obj, apoyos, unidades)
        bit.poner(a, "municion", a.municion - MUNICION_POR_APOYO, "apoyo", orden.id)
        orden.estado = "resuelta"
        orden.resultado = (
            f"Apoyo a {obj.nombre}: bonificacion x{bono:.2f} a su defensa y ataques de este turno."
        )

    for orden in ordenes:
        if orden.estado == "pendiente":
            rechazar(orden, f"Tipo de orden desconocido: {orden.tipo}")

    # ---- Fase 4: logistica, contadores de plataforma y caducidad de obras ----
    _reabastecer(lista_unidades, bit)
    for u in lista_unidades:
        if u.tipo == "aerea" and u.estado == "activa" and u.combustible <= 0:
            u.estado = "destruida"
            u.fuerza = 0.0
            db.add(Evento(
                escenario_id=escenario.id, turno=turno, tipo="logistica", bando_destino=u.bando,
                descripcion=f"{u.nombre} se quedo sin combustible lejos de una base aerea y se perdio.",
            ))

    for u in lista_unidades:
        clase = catalogo.obtener(u.clase, u.tipo)
        if u.id in dispararon:
            u.recarga_restante = clase.recarga_turnos
        else:
            u.recarga_restante = max(0, u.recarga_restante - 1)
        if u.id in movidas:
            u.despliegue_restante = clase.despliegue_turnos
        else:
            u.despliegue_restante = max(0, u.despliegue_restante - 1)

    for o in obras:
        if o.expira_turno <= turno:
            db.delete(o) if o in db else None

    return ordenes
