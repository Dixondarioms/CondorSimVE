"""Resolucion de ordenes de un turno, en fases:

0. Despegues: los grupos aereos pedidos a una base aerea o a un portaaviones nacen junto a el (ver
   engine/aeronaves.py), y las salvas de misiles de crucero nacen sobre su lanzador (ver engine/misiles.py).
1. Movimiento (terreno, rios/obras, clima, peso y combustible; ver engine/movimiento.py), vuelo de las
   aeronaves (despegue desde la base, patrulla persistente, aterrizaje), vuelo guiado de los misiles hacia su
   blanco, aeronaves embarcadas que siguen a su portaaviones y construccion de puentes y vados.
2. Apoyos: se registra que unidades apoyan a cuales. Las patrullas interceptan aviones enemigos al alcance.
3. Combates simultaneos: todos se calculan con las fuerzas de inicio de fase y las perdidas se
   aplican juntas, de modo que el resultado no depende del orden en que se emitieron las ordenes.
   Cuentan la sorpresa, la cadencia de fuego, el despliegue y la recarga de cada plataforma. Excepcion: los
   disparos contra municiones en vuelo (misiles, merodeadoras) se resuelven antes (interceptacion antes del
   impacto): llegan al blanco con la fuerza que les queda, o no llegan.
4. Logistica: consumo de municion, reabastecimiento (aviones solo en tierra, en su base) y por convoyes,
   aterrizaje de emergencia y regreso automatico por combustible critico, perdida de aeronaves sin
   combustible, contadores de despliegue/recarga/espera en tierra y caducidad de las obras.

Cada cambio de combustible, municion o carga queda en `registro_logistico` con su causa.
"""

import json
from collections import defaultdict

from sqlalchemy.orm import Session

from app.engine import aeronaves as aeronaves_mod
from app.engine import bases as bases_mod
from app.engine import azar as azar_mod
from app.engine import catalogo, combat, geo, logistica, movimiento, vision
from app.engine import clima as clima_mod
from app.engine import guerra_electronica as ge_mod
from app.engine import misiles as misiles_mod
from app.engine import misiones as misiones_mod
from app.engine import transporte as transporte_mod
from app.engine.movimiento import TURNO_DURACION_HORAS  # noqa: F401  (reexportado)
from app.models.aar import Combate, RegistroLogistico
from app.models.escenario import Escenario
from app.models.evento import Evento
from app.models.interferencia import Interferencia
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
# `detalle` de las ordenes que crea el propio motor al resolver (sin autor): ataques pedidos por misiones, impactos
# de misiles, intercepciones, defensa antiaerea y regreso por combustible critico
DETALLES_AUTOMATICOS = frozenset({"mision", "impacto", "intercepcion", "defensa aerea", "combustible critico"})


def es_automatica(orden: Orden) -> bool:
    """Orden creada por el motor (ningun alumno la emitio)."""
    return orden.autor_id is None and orden.detalle in DETALLES_AUTOMATICOS


def tipo_efectivo(unidad: Unidad) -> str:
    """Tipo que se usa en el combate: las bases y los aviones estacionados cuentan como objetivos terrestres."""
    return "terrestre" if unidad.tipo == "base" or getattr(unidad, "en_tierra", False) else unidad.tipo


def _tiene_cobertura_aerea(bando: str, lat: float, lon: float, unidades) -> bool:
    return any(
        u.bando == bando
        and u.tipo == "aerea"
        and u.estado == "activa"
        and not u.en_tierra
        and not catalogo.es_misil(u)
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


def _sorpresa(atacante: Unidad, defensor: Unidad, unidades, terreno: Terreno, clima: str, ge=None) -> float:
    """Multiplicador de ataque si el bando defensor no detecta al atacante (emboscada)."""
    for x in unidades:
        if x.bando == defensor.bando and x.estado == "activa" and x.deteccion_km:
            if vision.detecta(x, atacante, terreno, clima, ge):
                return 1.0
    return SORPRESA_EMBOSCADA if catalogo.obtener(defensor.clase, defensor.tipo).vulnerable_emboscada else SORPRESA_GENERAL


def _aviso_interferencia(db: Session, escenario: Escenario, turno: int, bando: str, lat: float, lon: float,
                         radio: float) -> None:
    db.add(Evento(
        escenario_id=escenario.id, turno=turno, tipo="guerra_electronica",
        bando_destino="rojo" if bando == "azul" else "azul",
        descripcion=(f"Interferencia electronica enemiga sobre ({lat:.2f}, {lon:.2f}), radio {radio:.0f} km: "
                     "sensores, antiaerea y enlaces de drones degradados en la zona. El emisor fue localizado."),
    ))


class _Bitacora:
    """Escribe en `registro_logistico` cada variacion de combustible, municion o carga."""

    def __init__(self, db: Session, escenario: Escenario):
        self.db, self.escenario = db, escenario

    def poner(self, u: Unidad, variable: str, valor: float, causa: str, orden_id: int | None = None) -> None:
        antes = getattr(u, variable)
        # direccion: con la logistica apagada no se consume combustible ni municion (los aumentos si se aplican)
        if not getattr(self.escenario, "logistica", True) and variable in ("combustible", "municion") and valor < antes:
            return
        valor = max(0.0, min(100.0, valor))
        if abs(valor - antes) < 0.05:
            return
        setattr(u, variable, valor)
        self.db.add(RegistroLogistico(
            escenario_id=self.escenario.id, turno=self.escenario.turno_actual, unidad_id=u.id,
            unidad_nombre=u.nombre, bando=u.bando, variable=variable, antes=round(antes, 2),
            despues=round(valor, 2), causa=causa, orden_id=orden_id,
        ))


REPOSICION_PORTAAVIONES = 100.0  # puntos por variable que un portaaviones recarga por turno junto a un puerto propio


def _reabastecer(unidades: list[Unidad], bit: _Bitacora) -> None:
    """Las bases reabastecen (+50 %) desde sus existencias; los convoyes reabastecen en marcha (+40 %), se recargan
    en los depositos y descargan en las bases aereas y puertos; los depositos reponen existencias cada turno. Un
    portaaviones reabastece a sus aeronaves embarcadas desde sus propias existencias y las repone junto a un puerto
    propio."""
    bases = [
        u for u in unidades
        if (u.tipo == "base" or catalogo.es_portaaviones(u)) and u.estado == "activa" and u.fuerza >= BASE_FUERZA_MINIMA
    ]
    antes = {b.id: {v: logistica.stock(b, v) for v in logistica.VARIABLES} for b in bases}
    for u in unidades:
        if u.tipo == "base" or u.estado != "activa":
            continue
        if u.tipo == "aerea" and not u.en_tierra:
            continue  # un avion en vuelo no se reabastece: debe aterrizar
        for b in bases:
            if b is u or b.bando != u.bando or u.tipo not in catalogo.obtener(b.clase, b.tipo).suministra:
                continue
            if b.tipo != "base" and u.base_id != b.id:
                continue  # un portaaviones solo abastece a las aeronaves estacionadas a bordo
            if geo.distancia_km(b.lat, b.lon, u.lat, u.lon) <= b.alcance_km:
                for variable in logistica.VARIABLES:
                    dar = min(REABASTECIMIENTO_POR_TURNO, 100.0 - getattr(u, variable), logistica.stock(b, variable))
                    if dar > 0.05:
                        bit.poner(u, variable, getattr(u, variable) + dar, "reabastecimiento")
                        logistica.cambiar_stock(b, variable, -dar)
                clase_u = catalogo.obtener(u.clase, u.tipo)
                if clase_u.carga_max:
                    carga = logistica.carga_disponible(b, min(RECARGA_CONVOY_EN_DEPOSITO, clase_u.carga_max - u.carga))
                    if carga > 0.05:
                        bit.poner(u, "carga", u.carga + carga, "reabastecimiento")
                        logistica.retirar_carga(b, carga)
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

    # los convoyes descargan sus suministros en las bases que no los recargan (bases aereas y puertos)
    for conv in unidades:
        clase = catalogo.obtener(conv.clase, conv.tipo)
        if conv.estado != "activa" or not clase.nodo_movil_km or conv.carga <= 0.05:
            continue
        for b in bases:
            if b.tipo != "base" or b.bando != conv.bando or conv.tipo in catalogo.obtener(b.clase, "base").suministra:
                continue
            if geo.distancia_km(conv.lat, conv.lon, b.lat, b.lon) <= clase.nodo_movil_km:
                entrega = logistica.carga_que_admite(b, min(logistica.ENTREGA_CONVOY_POR_TURNO, conv.carga))
                if entrega > 0.05:
                    bit.poner(conv, "carga", conv.carga - entrega, "entrega a base")
                    logistica.depositar_carga(b, entrega)
                break

    # los portaaviones reponen sus existencias desde un puerto propio a su alcance
    puertos = [b for b in bases if b.tipo == "base" and "naval" in catalogo.obtener(b.clase, "base").suministra]
    for pa in bases:
        if pa.tipo == "base":
            continue
        for p in puertos:
            if p.bando != pa.bando or geo.distancia_km(p.lat, p.lon, pa.lat, pa.lon) > p.alcance_km:
                continue
            for variable in logistica.VARIABLES:
                dar = min(REPOSICION_PORTAAVIONES, logistica.maximo(pa) - logistica.stock(pa, variable),
                          logistica.stock(p, variable))
                if dar > 0.05:
                    logistica.cambiar_stock(pa, variable, dar)
                    logistica.cambiar_stock(p, variable, -dar)
            break

    for b in bases:
        logistica.reponer(b)
        for variable in logistica.VARIABLES:
            if antes[b.id][variable] > 0 and logistica.stock(b, variable) <= 0:
                bit.db.add(Evento(
                    escenario_id=bit.escenario.id, turno=bit.escenario.turno_actual, tipo="logistica",
                    bando_destino=b.bando,
                    descripcion=f"{b.nombre} se quedo sin {variable} en deposito: no puede reabastecer ni lanzar "
                                "aeronaves hasta recibir suministros.",
                ))


def procesar_ordenes(
    db: Session, escenario: Escenario, terreno: Terreno | None = None
) -> list[Orden]:
    terreno = terreno or get_terreno()
    clima = clima_mod.contexto(db, escenario) if getattr(escenario, "efectos_clima", True) else clima_mod.ClimaLocal("despejado")
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
                base, modelo_id, n, aeronaves_mod.aeronaves_en_servicio(
                    (u for u in lista_unidades if u.bando == base.bando), aeronaves_mod.es_dron_modelo(modelo_id))
            )
        )
        if motivo:
            rechazar(orden, motivo)
            continue
        grupo = aeronaves_mod.crear_grupo(base, modelo_id, n, datos.get("indicativo", ""), lanzados_en_base[base.id])
        lanzados_en_base[base.id] += 1
        logistica.descontar_despegue(base, n)
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
    # misiones aereas programadas para este turno: despegan de su base o se ponen en ruta
    misiones_mod.activar(db, escenario, unidades, lista_unidades, turno, lanzados_en_base)

    # salvas de misiles de crucero: nacen sobre el lanzador y vuelan desde este mismo turno
    salvas_de: dict[int, int] = defaultdict(int)
    for orden in [o for o in ordenes if o.tipo == "lanzar"]:
        lanzador = unidades.get(orden.unidad_id)
        blanco = unidades.get(orden.objetivo_unidad_id) if orden.objetivo_unidad_id else None
        n = misiles_mod.decodificar(orden.detalle).get("misiles")
        motivo = ("El lanzador no esta activo." if lanzador is None or lanzador.estado != "activa"
                  else misiles_mod.error_de_lanzamiento(lanzador, blanco, n))
        if motivo:
            rechazar(orden, motivo)
            continue
        salva = misiles_mod.crear_salva(lanzador, blanco, n, salvas_de[lanzador.id])
        salvas_de[lanzador.id] += 1
        bit.poner(lanzador, "municion", lanzador.municion - misiles_mod.MUNICION_POR_MISIL * n, "lanzamiento", orden.id)
        db.add(salva)
        db.flush()
        unidades[salva.id] = salva
        lista_unidades.append(salva)
        orden.estado = "resuelta"
        orden.resultado = f"{lanzador.nombre} lanzo {n} misil(es) de crucero contra {blanco.nombre} ({salva.nombre})."
        db.add(Evento(
            escenario_id=escenario.id, turno=turno, tipo="lanzamiento", bando_destino=lanzador.bando,
            descripcion=f"{lanzador.nombre} lanzo {n} misil(es) de crucero contra {blanco.nombre}.",
        ))

    # ---- Fase 0a: embarques. La unidad sube al transporte propio que tiene al lado y viaja con el ----
    for orden in [o for o in ordenes if o.tipo == "embarcar"]:
        u = unidades.get(orden.unidad_id)
        t = unidades.get(orden.objetivo_unidad_id) if orden.objetivo_unidad_id else None
        motivo = "La unidad no esta activa." if u is None or u.estado != "activa" else transporte_mod.error_de_embarque(u, t, lista_unidades)
        if motivo:
            rechazar(orden, motivo)
            continue
        transporte_mod.embarcar(u, t)
        orden.estado = "resuelta"
        orden.resultado = f"{u.nombre} embarco en {t.nombre}: viaja a bordo y no se la ve por separado."

    # ---- Fase 0b: guerra electronica. Cada interferencia rige este turno y la planificacion del siguiente ----
    zonas: list[Interferencia] = []
    for orden in [o for o in ordenes if o.tipo == "interferir"]:
        u = unidades.get(orden.unidad_id)
        punto = (json.loads(orden.waypoints_json or "[]") or [None])[0]
        motivo = "La unidad no esta activa." if u is None or u.estado != "activa" else ge_mod.error_de_interferencia(u, punto)
        if motivo:
            rechazar(orden, motivo)
            continue
        radio = catalogo.obtener(u.clase, u.tipo).interferencia_km
        zona = Interferencia(escenario_id=escenario.id, unidad_id=u.id, bando=u.bando, lat=punto[0], lon=punto[1],
                             radio_km=radio, turno=turno)
        db.add(zona)
        zonas.append(zona)
        if aeronaves_mod.en_vuelo(u):  # el avion de GE orbita para interferir: deja la patrulla y gasta combustible
            u.mision, u.mision_lat, u.mision_lon = "", None, None
            bit.poner(u, "combustible", u.combustible - aeronaves_mod.COMBUSTIBLE_LOITER, "interferencia", orden.id)
        orden.estado = "resuelta"
        orden.resultado = (
            f"Interfiere en un radio de {radio:.0f} km sobre ({punto[0]:.3f}, {punto[1]:.3f}) durante este turno y la "
            "planificacion del siguiente. Al emitir, el enemigo localiza al interferidor."
        )
        _aviso_interferencia(db, escenario, turno, u.bando, punto[0], punto[1], radio)
    # las misiones de guerra electronica que estan orbitando interfieren solas (su combustible lo descuenta la mision)
    for u, lat, lon in misiones_mod.interferencias(db, escenario, unidades):
        radio = catalogo.obtener(u.clase, u.tipo).interferencia_km
        zona = Interferencia(escenario_id=escenario.id, unidad_id=u.id, bando=u.bando, lat=lat, lon=lon,
                             radio_km=radio, turno=turno)
        db.add(zona)
        zonas.append(zona)
        _aviso_interferencia(db, escenario, turno, u.bando, lat, lon, radio)
    ge = ge_mod.Contexto(zonas)

    # ---- Fase 1: movimiento, vuelo, patrulla y aterrizaje ----
    con_orden_de_vuelo: set[int] = set()
    aterrizajes_del_turno: dict[int, int] = defaultdict(int)
    desembarcos: dict[int, list] = {}
    for orden in [o for o in ordenes if o.tipo in ("mover", "patrullar", "aterrizar", "desembarcar")]:
        u = unidades.get(orden.unidad_id)
        waypoints = json.loads(orden.waypoints_json or "[]")
        if orden.tipo == "desembarcar":
            punto = waypoints[-1] if waypoints else None
            motivo = ("La unidad no esta activa." if u is None or u.estado != "activa"
                      else transporte_mod.error_de_desembarco(u, punto, terreno, lista_unidades))
            if motivo:
                rechazar(orden, motivo)
                continue
            desembarcos[u.id] = (orden, punto)
            waypoints = waypoints[:-1] if u.tipo == "naval" and len(waypoints) > 1 else waypoints
            if u.tipo == "naval" and len(waypoints) == 1 and terreno.clase(waypoints[0][0], waypoints[0][1]) != "agua":
                waypoints = []  # ya esta junto a la costa: no se mueve, solo desembarca
            if not waypoints:
                orden.estado = "resuelta"
                orden.resultado = "Desembarca desde su posicion."
                continue
            # el resto del turno se trata como un movimiento (rama generica); el desembarco va despues
        base_destino = unidades.get(orden.objetivo_unidad_id) if orden.tipo == "aterrizar" and orden.objetivo_unidad_id else None
        if u is None or u.estado != "activa":
            rechazar(orden, "La unidad no esta activa.")
        elif transporte_mod.embarcada(u):
            rechazar(orden, "La unidad viaja a bordo de un transporte: primero debe desembarcar.")
        elif catalogo.es_misil(u):
            rechazar(orden, misiles_mod.MOTIVO_SIN_ORDENES)
        elif ge_mod.enlace_perdido(u, ge):
            rechazar(orden, ge_mod.MOTIVO_SIN_ENLACE)
        elif u.tipo == "base" or u.velocidad_kmh <= 0:
            rechazar(orden, "La unidad no puede moverse.")
        elif u.en_tierra and u.espera_restante > 0:
            rechazar(orden, f"En tierra: faltan {u.espera_restante} turno(s) para reabastecer y rearmar.")
        elif orden.tipo in ("mover", "patrullar") and not waypoints:
            rechazar(orden, "Orden de movimiento sin waypoints.")
        elif orden.tipo == "patrullar" and u.tipo != "aerea":
            rechazar(orden, "Solo las aeronaves pueden patrullar.")
        elif orden.tipo == "aterrizar" and (motivo := aeronaves_mod.error_de_aterrizaje(u, base_destino, lista_unidades)):
            rechazar(orden, motivo)
        else:
            if orden.tipo == "aterrizar":
                waypoints = [[base_destino.lat, base_destino.lon]]
            if u.en_tierra:
                aeronaves_mod.despegar_unidad(u)  # una orden de vuelo a una aeronave lista en tierra es el despegue
            if orden.tipo != "patrullar":
                u.mision, u.mision_lat, u.mision_lon = "", None, None
            mov = movimiento.simular(u, waypoints, terreno, clima, obras)
            if mov.km_reales > 0:
                movidas.add(u.id)
            con_orden_de_vuelo.add(u.id)
            u.lat, u.lon = mov.lat, mov.lon
            bit.poner(u, "combustible", u.combustible - mov.combustible_gastado, "movimiento", orden.id)
            orden.estado = "resuelta"
            if orden.tipo == "patrullar":
                u.mision, u.mision_lat, u.mision_lon = "patrulla", waypoints[-1][0], waypoints[-1][1]
                orden.resultado = (
                    f"Patrulla sobre ({u.mision_lat:.3f}, {u.mision_lon:.3f}); recorrio {mov.km_reales:.1f} km, "
                    f"combustible {u.combustible:.0f}%. Se mantiene en la zona e intercepta aviones enemigos."
                )
            elif orden.tipo == "aterrizar":
                faltan = geo.distancia_km(u.lat, u.lon, base_destino.lat, base_destino.lon)
                if faltan <= aeronaves_mod.RADIO_ATERRIZAJE_KM:
                    aeronaves_mod.aterrizar(u, base_destino, aterrizajes_del_turno[base_destino.id])
                    aterrizajes_del_turno[base_destino.id] += 1
                    orden.resultado = (
                        f"Aterrizo en {base_destino.nombre}; combustible {u.combustible:.0f}%. "
                        f"Quedara lista para despegar en {u.espera_restante} turnos."
                    )
                else:
                    orden.resultado = (
                        f"Vuela hacia {base_destino.nombre}: faltan {faltan:.0f} km, combustible {u.combustible:.0f}%. "
                        f"{mov.nota}"
                    ).strip()
            else:
                orden.resultado = (
                    f"Unidad en ({u.lat:.4f}, {u.lon:.4f}); recorrio {mov.km_reales:.1f} km, "
                    f"combustible {u.combustible:.0f}%. {mov.nota}"
                ).strip()

    # misiones aereas en curso: cada grupo sin orden directa avanza solo por su ruta
    ataques_mision, bajo_mision = misiones_mod.avanzar(
        db, escenario, unidades, lista_unidades, con_orden_de_vuelo, terreno, clima, obras, ge, bit, turno)
    con_orden_de_vuelo |= bajo_mision

    # patrullas en curso (sin orden de vuelo este turno): siguen hacia su zona o la mantienen gastando combustible
    for u in lista_unidades:
        if u.mision != "patrulla" or not aeronaves_mod.en_vuelo(u) or u.id in con_orden_de_vuelo:
            continue
        restante = geo.distancia_km(u.lat, u.lon, u.mision_lat, u.mision_lon)
        if restante > 1.0:
            mov = movimiento.simular(u, [[u.mision_lat, u.mision_lon]], terreno, clima, obras)
            u.lat, u.lon = mov.lat, mov.lon
            bit.poner(u, "combustible", u.combustible - mov.combustible_gastado, "movimiento")
        else:
            bit.poner(u, "combustible", u.combustible - aeronaves_mod.COMBUSTIBLE_LOITER, "patrulla")

    # misiles de crucero: vuelan solos hacia la posicion actual de su blanco (despues de que todo se movio)
    impactos: list[tuple[int, int]] = []
    for u in list(lista_unidades):
        if not catalogo.es_misil(u) or not aeronaves_mod.en_vuelo(u):
            continue
        blanco, gasto, perdida = misiles_mod.guiar(u, unidades, terreno, clima, obras)
        bit.poner(u, "combustible", u.combustible - gasto, "vuelo del misil")
        if blanco is not None:
            impactos.append((u.id, blanco.id))
        elif perdida:
            u.estado, u.fuerza = "destruida", 0.0
            db.add(Evento(
                escenario_id=escenario.id, turno=turno, tipo="combate", bando_destino=u.bando,
                descripcion=(f"{u.nombre} no encontro su blanco en el ultimo punto conocido "
                             f"({u.lat:.3f}, {u.lon:.3f}) y se perdio."),
            ))
    # las aeronaves estacionadas en un portaaviones navegan con el; las tropas embarcadas, con su transporte
    aeronaves_mod.seguir_portaaviones(lista_unidades)
    transporte_mod.seguir_transporte(lista_unidades)
    for uid, (orden, punto) in desembarcos.items():
        t = unidades[uid]
        bajadas = transporte_mod.desembarcar(t, punto, lista_unidades, terreno)
        if bajadas:
            nombres = ", ".join(x.nombre for x in bajadas)
            orden.resultado = (orden.resultado or "").rstrip() + f" Desembarco en ({punto[0]:.3f}, {punto[1]:.3f}): {nombres}."
            db.add(Evento(escenario_id=escenario.id, turno=turno, tipo="logistica", bando_destino=t.bando,
                          descripcion=f"{t.nombre} desembarco a {nombres} en ({punto[0]:.3f}, {punto[1]:.3f})."))
            movidas.update(x.id for x in bajadas)
        else:
            faltan = geo.distancia_km(t.lat, t.lon, punto[0], punto[1])
            orden.resultado = (orden.resultado or "").rstrip() + f" Aun a {faltan:.0f} km del punto de desembarco."

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

    # ---- Fase 2b: interceptacion. Cada patrulla sin orden de ataque combate al avion enemigo detectado mas cercano
    # dentro de su alcance; se registra como una orden de ataque "intercepcion" (aparece en la cola y el informe).
    atacan = {o.unidad_id for o in ordenes if o.tipo == "atacar" and o.estado == "pendiente"}
    # los ataques que piden las misiones (blanco, CAS, SEAD) se registran como ordenes de ataque "mision", y los
    # misiles que alcanzan su blanco, como ordenes de ataque "impacto"
    for atacante_id, blanco_id, detalle in ([(a, b, "mision") for a, b in ataques_mision]
                                            + [(a, b, "impacto") for a, b in impactos]):
        if atacante_id in atacan:
            continue
        ataque = Orden(
            escenario_id=escenario.id, unidad_id=atacante_id, tipo="atacar", objetivo_unidad_id=blanco_id,
            detalle=detalle, turno_emitida=turno, estado="pendiente",
        )
        db.add(ataque)
        db.flush()
        ordenes.append(ataque)
        atacan.add(atacante_id)
    fuego_auto = getattr(escenario, "fuego_automatico", True)
    for u in lista_unidades:
        if not fuego_auto or u.mision != "patrulla" or not aeronaves_mod.en_vuelo(u) or u.id in atacan:
            continue
        if u.municion <= 0 or u.recarga_restante > 0 or catalogo.perfil(u).ataque_vs.get("aerea", 0.0) <= 0:
            continue
        aliados = [x for x in lista_unidades if x.bando == u.bando and x.estado == "activa" and x.deteccion_km]
        amenazas = [
            x for x in lista_unidades
            if x.bando != u.bando and aeronaves_mod.en_vuelo(x)
            and geo.distancia_km(u.lat, u.lon, x.lat, x.lon) <= u.alcance_km
            and any(vision.detecta(d, x, terreno, clima, ge) for d in aliados)
        ]
        if not amenazas:
            continue
        blanco = min(amenazas, key=lambda x: geo.distancia_km(u.lat, u.lon, x.lat, x.lon))
        intercepcion = Orden(
            escenario_id=escenario.id, unidad_id=u.id, tipo="atacar", objetivo_unidad_id=blanco.id,
            detalle="intercepcion", turno_emitida=turno, estado="pendiente",
        )
        db.add(intercepcion)
        db.flush()
        ordenes.append(intercepcion)
        atacan.add(u.id)

    # ---- Fase 2c: defensa antiaerea automatica. Cada pieza con fuego libre y sin orden de ataque dispara contra la
    # aeronave enemiga en vuelo mas cercana a su alcance que su bando detecte; la guiada por radar necesita el radar
    # encendido. Se registra como una orden de ataque "defensa aerea".
    for u in lista_unidades:
        clase_aa = catalogo.obtener(u.clase, u.tipo)
        if not fuego_auto or not clase_aa.defensa_aerea or u.estado != "activa" or u.fuego_libre is False or u.id in atacan:
            continue
        if u.municion <= 0 or u.recarga_restante > 0:
            continue
        if clase_aa.emisor and not ge_mod.emite_radar(u):
            continue  # con el radar apagado no dispara sola (a ojo solo por orden)
        if clase_aa.despliegue_turnos and (u.id in movidas or u.despliegue_restante > 0):
            continue
        aliados = [x for x in lista_unidades if x.bando == u.bando and x.estado == "activa" and x.deteccion_km]
        amenazas = [
            x for x in lista_unidades
            if x.bando != u.bando and aeronaves_mod.en_vuelo(x)
            and geo.distancia_km(u.lat, u.lon, x.lat, x.lon) <= u.alcance_km
            and any(vision.detecta(d, x, terreno, clima, ge) for d in aliados)
        ]
        if not amenazas:
            continue
        blanco = min(amenazas, key=lambda x: geo.distancia_km(u.lat, u.lon, x.lat, x.lon))
        disparo = Orden(
            escenario_id=escenario.id, unidad_id=u.id, tipo="atacar", objetivo_unidad_id=blanco.id,
            detalle="defensa aerea", turno_emitida=turno, estado="pendiente",
        )
        db.add(disparo)
        db.flush()
        ordenes.append(disparo)
        atacan.add(u.id)

    # ---- Fase 3: combates simultaneos ----
    fuerza_inicial = {uid: u.fuerza for uid, u in unidades.items()}
    perdidas: dict[int, float] = defaultdict(float)
    gasto_municion: dict[int, float] = defaultdict(float)
    orden_de_ataque: dict[int, int] = {}
    derribados: set[int] = set()
    partes_atacadas: dict[int, str | None] = {}
    pistas_operativas_antes = {u.id: bases_mod.pista_operativa(u) for u in lista_unidades if catalogo.opera_aeronaves(u)}

    def municion_en_vuelo(x) -> bool:
        """Misil o municion merodeadora en vuelo: se la puede interceptar antes de que impacte."""
        return x is not None and aeronaves_mod.en_vuelo(x) and catalogo.obtener(x.clase, x.tipo).se_consume

    def resolver_ataque(orden: Orden) -> None:
        a = unidades.get(orden.unidad_id)
        d = unidades.get(orden.objetivo_unidad_id) if orden.objetivo_unidad_id else None
        if a is not None and a.id in derribados:
            rechazar(orden, "Derribado antes del impacto.")
            return
        if a is None or a.estado != "activa" or a.tipo == "base":
            rechazar(orden, "La unidad atacante no esta activa.")
            return
        if transporte_mod.embarcada(a):
            rechazar(orden, "La unidad viaja a bordo de un transporte y no puede combatir.")
            return
        if d is None or d.bando == a.bando or d.estado != "activa":
            rechazar(orden, "Objetivo invalido o ya fuera de combate.")
            return
        if ge_mod.enlace_perdido(a, ge):
            rechazar(orden, ge_mod.MOTIVO_SIN_ENLACE)
            return
        t_a, t_d = tipo_efectivo(a), tipo_efectivo(d)
        clase_a, clase_d = catalogo.perfil(a), catalogo.perfil(d)
        # la antiaerea guiada por radar pierde efecto contra aeronaves si esta interferida, y mas aun si tira a ojo
        # con el radar apagado (solo por orden: sola no dispara)
        aaa_optica = clase_a.emisor and t_d == "aerea" and a.emitiendo is False
        aaa_interferida = clase_a.emisor and t_d == "aerea" and not aaa_optica and ge.interferido(a)
        if clase_a.ataque_vs.get(t_d, 0.0) <= 0:
            rechazar(orden, f"{clase_a.nombre} no puede atacar objetivos de tipo {t_d}.")
            return
        if a.municion <= 0:
            rechazar(orden, "Sin municion.")
            return
        if a.recarga_restante > 0:
            rechazar(orden, f"Recargando ({a.recarga_restante} turno(s) restante(s)).")
            return
        if clase_a.despliegue_turnos and (a.id in movidas or a.despliegue_restante > 0):
            faltan = max(a.despliegue_restante, clase_a.despliegue_turnos if a.id in movidas else 0)
            rechazar(orden, f"Desplegando el sistema tras moverse ({faltan} turno(s) quieta).")
            return
        distancia = geo.distancia_km(a.lat, a.lon, d.lat, d.lon)
        if distancia > a.alcance_km:
            rechazar(orden, f"Objetivo fuera de alcance ({distancia:.1f} km > {a.alcance_km:.1f} km).")
            return

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
            factor_ataque=clase_a.ataque_vs.get(t_d, 1.0) * catalogo.factor_grupo(a)
            * (ge_mod.FACTOR_ANTIAEREA if aaa_interferida else 1.0) * (ge_mod.FACTOR_TIRO_OPTICO if aaa_optica else 1.0),
            factor_defensa=clase_d.defensa * catalogo.factor_grupo(d),
            factor_clima=clima_mod.factor_ataque_aereo(clima, d.lat, d.lon) if a.tipo == "aerea" else 1.0,
            factor_municion=min(1.0, a.municion / consumo),
            azar=azar_mod.factor_azar(escenario.semilla, turno, a.id, d.id) if escenario.azar else 1.0,
            sorpresa=_sorpresa(a, d, lista_unidades, terreno, clima, ge),
            cadencia=clase_a.cadencia_fuego,
        )
        if aaa_interferida:
            res.efectos.append(f"antiaerea interferida por guerra electronica x{ge_mod.FACTOR_ANTIAEREA:.2f}")
        perdidas[a.id] += fuerza_inicial[a.id] - res.fuerza_atacante_resultante
        perdidas[d.id] += fuerza_inicial[d.id] - res.fuerza_defensor_resultante
        if catalogo.opera_aeronaves(d):  # base aerea o portaaviones: el daño se reparte en sus partes
            parte = orden.detalle if orden.detalle in bases_mod.PARTES else None
            partes_atacadas[d.id] = parte
            cambios = bases_mod.aplicar_dano(d, fuerza_inicial[d.id] - res.fuerza_defensor_resultante, parte)
            if cambios:
                res.efectos.append("daño a " + ", ".join(f"{p} {v:.0f} %" for p, v in cambios.items()))
        gasto_municion[a.id] += consumo
        orden_de_ataque[a.id] = orden.id
        dispararon.add(a.id)
        orden.estado = "resuelta"
        orden.resultado = f"Ataque a {d.nombre}. {res.resumen}" + (
            f" Antiaerea interferida por guerra electronica enemiga (x{ge_mod.FACTOR_ANTIAEREA:.2f})." if aaa_interferida else ""
        ) + (f" Tiro optico con el radar apagado (x{ge_mod.FACTOR_TIRO_OPTICO:.2f})." if aaa_optica else "")
        db.add(Combate(
            escenario_id=escenario.id, turno=turno, orden_id=orden.id,
            atacante_id=a.id, defensor_id=d.id, atacante_nombre=a.nombre, defensor_nombre=d.nombre,
            atacante_bando=a.bando, defensor_bando=d.bando, ratio=res.ratio,
            fuerza_ini_atacante=fuerza_inicial[a.id], fuerza_ini_defensor=fuerza_inicial[d.id],
            perdida_atacante=fuerza_inicial[a.id] - res.fuerza_atacante_resultante,
            perdida_defensor=fuerza_inicial[d.id] - res.fuerza_defensor_resultante,
            terreno=terreno.clase(d.lat, d.lon), efectos="; ".join(res.efectos), lat=d.lat, lon=d.lon,
        ))

    ataques = [o for o in ordenes if o.tipo == "atacar"]
    # interceptacion antes del impacto: los disparos contra misiles y merodeadoras en vuelo se resuelven primero y
    # sus perdidas se descuentan de la fuerza con la que esa municion llega (o no llega) a su blanco
    contra_municion = [
        o for o in ataques
        if municion_en_vuelo(unidades.get(o.objetivo_unidad_id) if o.objetivo_unidad_id else None)
    ]
    for orden in contra_municion:
        resolver_ataque(orden)
    for uid in {o.objetivo_unidad_id for o in contra_municion}:
        if perdidas.get(uid, 0.0) > 0:
            fuerza_inicial[uid] = max(0.0, fuerza_inicial[uid] - perdidas[uid])
            if fuerza_inicial[uid] <= 0:
                derribados.add(uid)
                m = unidades[uid]
                db.add(Evento(
                    escenario_id=escenario.id, turno=turno, tipo="combate", bando_destino=m.bando,
                    descripcion=f"{m.nombre} fue derribado por la defensa enemiga antes de llegar a su blanco.",
                ))
    for orden in ataques:
        if orden not in contra_municion:
            resolver_ataque(orden)

    for uid, perdida in perdidas.items():
        u = unidades[uid]
        u.fuerza = max(0.0, u.fuerza - perdida)
        if u.fuerza <= 0:
            u.estado = "destruida"
        elif uid in partes_atacadas and not bases_mod.pista_operativa(u) and pistas_operativas_antes.get(uid, True):
            db.add(Evento(escenario_id=escenario.id, turno=turno, tipo="combate", bando_destino=u.bando,
                          descripcion=f"La pista de {u.nombre} quedo inoperativa ({bases_mod.dano(u, 'pista'):.0f} % de daño): "
                                      "sin despegues ni aterrizajes hasta repararla."))
    # la municion merodeadora se estrella contra su blanco: se pierde al atacar
    for uid in sorted(dispararon):
        u = unidades[uid]
        if catalogo.obtener(u.clase, u.tipo).se_consume and u.estado == "activa":
            u.estado, u.fuerza = "destruida", 0.0
            db.add(Evento(
                escenario_id=escenario.id, turno=turno, tipo="combate", bando_destino=u.bando,
                descripcion=f"{u.nombre} impacto contra su blanco y se destruyo (municion merodeadora).",
            ))
    for uid, gasto in gasto_municion.items():
        bit.poner(unidades[uid], "municion", unidades[uid].municion - gasto, "combate", orden_de_ataque.get(uid))
    # las tropas a bordo de un transporte sufren parte de su daño (y se pierden con el)
    for uid, perdida in list(perdidas.items()):
        t = unidades[uid]
        if transporte_mod.es_transporte(t) and perdida > 0:
            for x in transporte_mod.repartir_dano(t, perdida, lista_unidades):
                if x.estado == "destruida":
                    db.add(Evento(escenario_id=escenario.id, turno=turno, tipo="combate", bando_destino=x.bando,
                                  descripcion=f"{x.nombre} se perdio a bordo de {t.nombre}."))
    # los aviones estacionados sufren parte del dano que recibe su base o su portaaviones (ataques al aerodromo);
    # si el portaaviones se hunde, se pierden con el
    for uid, perdida in list(perdidas.items()):
        base = unidades[uid]
        if not catalogo.opera_aeronaves(base) or perdida <= 0:
            continue
        estacionados = aeronaves_mod.estacionadas(base, lista_unidades)
        con_refugio = bases_mod.protegidos(base, estacionados)
        for x in estacionados:
            if base.estado == "destruida" and catalogo.es_portaaviones(base):
                x.fuerza = 0.0
            else:
                # una plataforma dañada expone mas a los aviones; un refugio reforzado los protege
                factor = bases_mod.factor_plataforma(base) * (bases_mod.PROTECCION_REFUGIO if x.id in con_refugio else 1.0)
                x.fuerza = max(0.0, x.fuerza - perdida * aeronaves_mod.PERDIDA_EN_TIERRA * factor)
            if x.fuerza <= 0:
                x.estado = "destruida"
                donde = "se hundio con" if catalogo.es_portaaviones(base) and base.estado == "destruida" else "fue destruido en tierra durante el ataque a"
                db.add(Evento(
                    escenario_id=escenario.id, turno=turno, tipo="combate", bando_destino=x.bando,
                    descripcion=f"{x.nombre} {donde} {base.nombre}.",
                ))

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
    # aterrizaje de emergencia: sin combustible pero junto a una base propia con plazas, la aeronave aterriza
    for u in lista_unidades:
        if aeronaves_mod.en_vuelo(u) and u.combustible <= 0 and not catalogo.es_misil(u):
            base = aeronaves_mod.base_mas_cercana(u, lista_unidades)
            if base is not None and geo.distancia_km(u.lat, u.lon, base.lat, base.lon) <= base.alcance_km:
                aeronaves_mod.aterrizar(u, base, len(aeronaves_mod.estacionadas(base, lista_unidades)))
                db.add(Evento(
                    escenario_id=escenario.id, turno=turno, tipo="logistica", bando_destino=u.bando,
                    descripcion=f"{u.nombre} aterrizo de emergencia en {base.nombre} sin combustible.",
                ))
    _reabastecer(lista_unidades, bit)
    for u in lista_unidades:
        if u.tipo == "aerea" and u.estado == "activa" and not u.en_tierra and u.combustible <= 0:
            u.estado = "destruida"
            u.fuerza = 0.0
            texto = (f"{u.nombre} agoto su alcance sin llegar al blanco y cayo al terreno." if catalogo.es_misil(u)
                     else f"{u.nombre} se quedo sin combustible lejos de una base aerea y se perdio.")
            db.add(Evento(escenario_id=escenario.id, turno=turno, tipo="logistica", bando_destino=u.bando, descripcion=texto))

    for u in lista_unidades:
        if (u.mision == "patrulla" and aeronaves_mod.en_vuelo(u) and u.combustible <= aeronaves_mod.COMBUSTIBLE_CRITICO
                and u.id not in bajo_mision):  # las misiones resuelven su propio regreso
            base = aeronaves_mod.base_mas_cercana(u, lista_unidades)
            u.mision, u.mision_lat, u.mision_lon = "", None, None
            if base is not None:
                db.add(Orden(
                    escenario_id=escenario.id, unidad_id=u.id, tipo="aterrizar", objetivo_unidad_id=base.id,
                    detalle="combustible critico", turno_emitida=turno + 1, estado="pendiente",
                ))
                texto = f"{u.nombre} deja la patrulla con combustible critico ({u.combustible:.0f}%) y regresa a {base.nombre}."
            else:
                texto = f"{u.nombre} deja la patrulla con combustible critico ({u.combustible:.0f}%) y no hay base disponible."
            db.add(Evento(escenario_id=escenario.id, turno=turno, tipo="logistica", bando_destino=u.bando, descripcion=texto))

    for u in lista_unidades:
        clase = catalogo.obtener(u.clase, u.tipo)
        if u.en_tierra:
            u.espera_restante = max(0, u.espera_restante - 1)
        if u.id in dispararon:
            u.recarga_restante = clase.recarga_turnos
        else:
            u.recarga_restante = max(0, u.recarga_restante - 1)
        if u.id in movidas:
            u.despliegue_restante = clase.despliegue_turnos
        else:
            u.despliegue_restante = max(0, u.despliegue_restante - 1)

    misiones_mod.cerrar(db, escenario, unidades, turno)

    # reparacion de las partes de las bases (sola la pista; todo con ingenieros propios al lado)
    for u in lista_unidades:
        if catalogo.opera_aeronaves(u) and u.estado == "activa":
            antes_pista = bases_mod.dano(u, "pista")
            bases_mod.reparar(u, lista_unidades)
            if antes_pista >= bases_mod.PISTA_INOPERATIVA > bases_mod.dano(u, "pista"):
                db.add(Evento(escenario_id=escenario.id, turno=turno, tipo="logistica", bando_destino=u.bando,
                              descripcion=f"La pista de {u.nombre} vuelve a estar operativa ({bases_mod.dano(u, 'pista'):.0f} % de daño)."))

    # las zonas meteorologicas se desplazan con su deriva y las vencidas se disipan
    for z in clima_mod.avanzar(db, escenario, turno):
        db.add(Evento(escenario_id=escenario.id, turno=turno, tipo="clima", bando_destino="todos",
                      descripcion=f"Se disipo la zona de {z.tipo}{' ' + z.nombre if z.nombre else ''}."))

    for o in obras:
        if o.expira_turno <= turno:
            db.delete(o) if o in db else None

    return ordenes
