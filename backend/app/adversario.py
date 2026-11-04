"""Adversario automatico: el simulador conduce un bando (azul o rojo) con las mismas reglas que un alumno.

En tiempo real "piensa" cada IA_CADA_S segundos simulados mientras corre el reloj (engine/tiempo_real.py) y al
encenderlo el instructor (PATCH /config con ia_azul / ia_rojo): revisa cada unidad de su bando y le da una orden solo
si cambia lo que ya esta haciendo (una unidad en camino al mismo destino o atacando al mismo blanco sigue como va).
Las ordenes pasan por la misma validacion que las de los alumnos (routers/ordenes._crear_orden): alcance, municion,
combustible, puestos, niebla de guerra...

Solo usa lo que su bando sabe: sus propias unidades, las enemigas que detecta ahora (posicion, tipo y clase; nunca
su fuerza, su modelo ni su logistica), los ultimos contactos, sus propios objetivos y la ubicacion de las bases
enemigas (instalaciones fijas que figuran en el mapa de referencia).

Conducta (didactica y legible, no optima):
  - Aeronaves: vuelven a la base con poco combustible o sin municion; atacan al mejor blanco a su alcance; si no,
    se acercan a distancia de tiro de un blanco que puedan batir sin quedarse sin combustible para volver; sin
    blancos, patrullan sobre lo que deben proteger o su base. Los drones de reconocimiento y la alerta temprana
    orbitan hacia el enemigo; el cisterna, junto a sus aeronaves; la guerra electronica interfiere al enemigo.
  - Tierra: se reabastecen si les falta combustible o municion; atacan lo que esta a su alcance si la relacion es
    favorable; si no, van a sus objetivos (ocupar una zona, destruir o neutralizar una unidad conocida, proteger una propia) o se
    acercan al enemigo detectado. Los convoyes van hacia las unidades mas necesitadas.
  - Mar: salvas de misiles contra blancos a su alcance, ataque directo o acercamiento por el agua.
  - Lanzadores balisticos: tiran contra lo que su bando ve a su alcance, primero las instalaciones fijas (el misil cae
    donde estaba el blanco al lanzar: contra algo que se mueve suele errar); la recarga los limita.
  - Bases y portaaviones: lanzan un grupo de caza si el enemigo tiene aviacion a la vista y la propia no alcanza.
"""

import logging
import math
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import schemas, state
from app.engine import aeronaves as aeronaves_mod
from app.engine import balisticos as balisticos_mod
from app.engine import catalogo, defensa_aerea, geo
from app.engine import guerra_electronica as ge_mod
from app.engine import misiles as misiles_mod
from app.engine import rutas as rutas_mod
from app.engine import transporte as transporte_mod
from app.engine.orders import tipo_efectivo
from app.models.contacto import Contacto
from app.models.escenario import Escenario
from app.models.objetivo import Objetivo
from app.models.orden import Orden
from app.models.unidad import Unidad
from app.terreno import get_terreno

log = logging.getLogger("uvicorn.error")

REGRESO_COMBUSTIBLE = aeronaves_mod.COMBUSTIBLE_CRITICO + 15  # % con el que una aeronave emprende el regreso
SALIDA_COMBUSTIBLE = 60  # % minimo para despegar hacia una mision
SALIDA_MUNICION = 30
REABASTECER = 20  # % de combustible o municion por debajo del cual una unidad de tierra va a reabastecerse
RELACION_MINIMA = 0.6  # ataque propio / defensa del blanco (de su clase) para atacar en tierra
APROXIMACION = 0.8  # se acerca hasta este factor de su alcance
GRUPO_CAZA = 2  # aeronaves por grupo que lanza una base
IA_CADA_S = 300.0  # segundos simulados entre dos decisiones del adversario (5 min: a 60x, cada 5 s reales)
MISMO_DESTINO_KM = 3.0  # un destino nuevo a menos de esto (o del 10 % de lo que falta) es la misma orden
VARADA_RECUERDA_S = 3 * 3600.0  # tiempo simulado que recuerda que una unidad no pudo llegar a un destino...
VARADA_RADIO_KM = 10.0  # ...ni a sus alrededores
# Niveles del adversario (Escenario.ia_nivel): cuanto riesgo toma.
NIVELES = {
    # relacion: ataque/defensa minima para atacar en tierra; regreso: puntos de combustible sobre el de regreso;
    # aproximacion: fraccion de su alcance a la que se acerca; persecucion_km: hasta donde va por un blanco en tierra;
    # evita_antiaerea: tambien las aeronaves armadas evitan acercarse a la antiaerea conocida (salvo para batirla);
    # cazas_por_enemigo: cazas propios en vuelo por cada aeronave enemiga a la vista antes de dejar de lanzar mas
    "prudente": {"relacion": 0.9, "regreso": 10, "aproximacion": 0.9, "persecucion_km": 30, "evita_antiaerea": True,
                 "cazas_por_enemigo": 1.0},
    "normal": {"relacion": 0.6, "regreso": 0, "aproximacion": 0.8, "persecucion_km": 60, "evita_antiaerea": False,
               "cazas_por_enemigo": 1.0},
    "agresiva": {"relacion": 0.35, "regreso": -10, "aproximacion": 0.7, "persecucion_km": 150, "evita_antiaerea": False,
                 "cazas_por_enemigo": 2.0},
}
PRIORIDAD = {"antiaerea": 1.6, "radar": 1.5, "guerra_electronica": 1.4, "lanzador_misiles": 1.4, "base_aerea": 1.3,
             "portaaviones": 1.3, "destructor": 1.2, "fragata": 1.2, "artilleria": 1.2, "caza": 1.2,
             "avion_ge": 1.3, "alerta_temprana": 1.4, "cisterna": 1.3,
             # infraestructura: pesa en la conduccion del enemigo (engine/infraestructura.py)
             "centro_comunicaciones": 1.3, "termoelectrica": 1.2, "refineria": 1.2, "puente": 1.1, "hidroelectrica": 1.0}


def _rumbo(lat1, lon1, lat2, lon2) -> float:
    r = math.radians
    y = math.sin(r(lon2 - lon1)) * math.cos(r(lat2))
    x = math.cos(r(lat1)) * math.sin(r(lat2)) - math.sin(r(lat1)) * math.cos(r(lat2)) * math.cos(r(lon2 - lon1))
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def _punto_a_distancia(u, lat, lon, distancia_km) -> tuple[float, float]:
    """Punto sobre la recta de `u` hacia (lat, lon) que queda a `distancia_km` del destino."""
    d = geo.distancia_km(u.lat, u.lon, lat, lon)
    if d <= distancia_km:
        return (u.lat, u.lon)
    return geo.destino(u.lat, u.lon, _rumbo(u.lat, u.lon, lat, lon), d - distancia_km)


def _centro(puntos) -> tuple[float, float] | None:
    puntos = list(puntos)
    if not puntos:
        return None
    return (sum(p[0] for p in puntos) / len(puntos), sum(p[1] for p in puntos) / len(puntos))


class _Turno:
    """Lo que el bando sabe al abrirse el turno, y la emision de sus ordenes."""

    def __init__(self, db: Session, esc: Escenario, bando: str, terreno):
        from app.routers import ordenes as ordenes_router  # la misma validacion que las ordenes de los alumnos
        self.db, self.esc, self.bando, self.terreno = db, esc, bando, terreno
        self._crear = ordenes_router._crear_orden
        self.usuario = SimpleNamespace(id=None, rol=bando, puesto="comandante", username="IA")
        todas = db.query(Unidad).filter(Unidad.escenario_id == esc.id).all()
        self.propias = [u for u in todas if u.bando == bando and u.estado == "activa"
                        and not catalogo.es_misil(u) and not transporte_mod.embarcada(u)]
        self.visibles = state.unidades_visibles_para(db, esc, bando, terreno)
        # del enemigo solo se usa lo que se ve en el mapa: id, posicion, tipo, clase y si esta en tierra
        # los neutrales (trafico civil, paises ajenos) no son enemigos: la IA no les tira
        self.enemigos = [u for u in self.visibles if u.bando not in (bando, "neutral") and u.estado == "activa"
                         and not catalogo.es_misil(u)]
        ids_vistos = {u.id for u in self.enemigos}
        # instalaciones fijas del enemigo (bases aereas, puertos, depositos): figuran en el mapa, se conoce su ubicacion
        self.bases_enemigas = [u for u in todas if u.bando not in (bando, "neutral") and u.tipo == "base" and u.estado == "activa"]
        self.contactos = [c for c in db.query(Contacto).filter(Contacto.escenario_id == esc.id, Contacto.bando == bando)
                          if c.unidad_id not in ids_vistos]
        self.objetivos = db.query(Objetivo).filter(Objetivo.escenario_id == esc.id, Objetivo.bando == bando,
                                                   Objetivo.estado == "pendiente").all()
        self.decisiones: list[str] = []
        # ordenes que sus unidades estan cumpliendo (tiempo real) y destinos a los que no pudieron llegar hace poco (un
        # rio sin puente): no se las vuelve a mandar alli
        self.activas, self.varadas = {}, {}
        desde = (esc.sim_segundos or 0.0) - VARADA_RECUERDA_S
        for o in db.query(Orden).filter(Orden.escenario_id == esc.id,
                                        Orden.estado.in_(("pendiente", "en_ejecucion", "resuelta"))).order_by(Orden.id):
            if o.estado in ("pendiente", "en_ejecucion"):
                self.activas[o.unidad_id] = o
            elif o.tipo == "mover" and "Se detuvo" in (o.resultado or "") and (o.emitida_seg or 0.0) >= desde and o.waypoints:
                self.varadas.setdefault(o.unidad_id, []).append(o.waypoints[-1])
        self.nivel = NIVELES.get(getattr(esc, "ia_nivel", "normal") or "normal", NIVELES["normal"])
        self.reservas: dict[int, int] = {}  # plazas de cada base ya comprometidas por los aterrizajes de este turno

    # ---------------------------------------------------------------- emision
    def ordenar(self, u: Unidad, **campos) -> bool:
        """Intenta dar la orden; True si la validacion la acepto o si la unidad ya esta cumpliendo esa misma orden."""
        if self.ya_la_cumple(u, campos):
            return True
        try:
            self._crear(schemas.OrdenCreate(unidad_id=u.id, **campos), self.esc, self.db, self.usuario)
        except HTTPException:
            return False
        self.db.flush()
        self.decisiones.append(f"{u.nombre}: {campos['tipo']}")
        return True

    def ya_la_cumple(self, u, campos) -> bool:
        """La unidad ya cumple esa orden: mismo blanco o la misma base, o un destino practicamente igual (tiempo real:
        no se reinicia lo que va bien)."""
        actual = self.activas.get(u.id)
        if actual is None or actual.tipo != campos.get("tipo"):
            return False
        if actual.tipo in ("atacar", "aterrizar", "apoyar", "embarcar"):
            return actual.objetivo_unidad_id == campos.get("objetivo_unidad_id")
        nuevos, viejos = list(campos.get("waypoints") or []), actual.waypoints
        if not nuevos or not viejos:
            return False
        (lat, lon), (lat0, lon0) = nuevos[-1], viejos[-1]
        falta = geo.distancia_km(u.lat, u.lon, lat0, lon0)
        return geo.distancia_km(lat, lon, lat0, lon0) <= max(MISMO_DESTINO_KM, 0.1 * falta)

    def mover(self, u, lat, lon) -> bool:
        if geo.distancia_km(u.lat, u.lon, lat, lon) < 0.5:
            return False
        if self.ya_la_cumple(u, {"tipo": "mover", "waypoints": [(lat, lon)]}):
            return True  # antes de trazar la ruta: ya va hacia alli
        if any(geo.distancia_km(lat, lon, a, b) <= VARADA_RADIO_KM for a, b in self.varadas.get(u.id, [])):
            return False  # hace poco no pudo llegar alli
        if u.tipo == "terrestre" and self.terreno is not None:
            # por el camino mas rapido (carreteras y puentes), como el boton "Ruta por carretera" de los alumnos
            from app.routers.ordenes import _obras_y_cortes  # importacion tardia: evita ciclos entre routers
            ruta = rutas_mod.ruta(u, [lat, lon], self.terreno, _obras_y_cortes(self.db, self.esc))
            if ruta["nota"].startswith(("No hay camino", "El destino es intransitable")):
                return False  # no hay como llegar (rio sin puente): no se la manda a quedar varada
            return self.ordenar(u, tipo="mover", waypoints=[tuple(w) for w in ruta["waypoints"]])
        return self.ordenar(u, tipo="mover", waypoints=[(lat, lon)])

    # ---------------------------------------------------------------- criterios
    @staticmethod
    def puede_batir(u, e) -> float:
        return catalogo.perfil(u).ataque_vs.get(tipo_efectivo(e), 0.0)

    def mejor_blanco(self, u, alcance: float | None = None):
        """El blanco visible que mas conviene: capacidad de ataque contra el, prioridad de su clase y cercania."""
        mejor, puntaje = None, 0.0
        for e in self.enemigos:
            atk = self.puede_batir(u, e)
            if atk <= 0:
                continue
            d = geo.distancia_km(u.lat, u.lon, e.lat, e.lon)
            if alcance is not None and d > alcance:
                continue
            p = atk * PRIORIDAD.get(e.clase or "", 1.0) / (1 + d / 50)
            if p > puntaje:
                mejor, puntaje = e, p
        return mejor

    def relacion(self, u, e) -> float:
        """Ataque propio contra la defensa base de la clase del blanco (la fuerza enemiga no se conoce)."""
        defensa = catalogo.obtener(e.clase, e.tipo).defensa or 1.0
        return self.puede_batir(u, e) * (u.fuerza / 100.0) * catalogo.factor_grupo(u) / defensa

    def autonomia_restante(self, u) -> float:
        return u.autonomia_km * u.combustible / 100.0 if u.autonomia_km else float("inf")

    def bases_para(self, u):
        return [b for b in self.propias if catalogo.opera_aeronaves(b) and aeronaves_mod.puede_operar_en(u, b)]

    def protegidas(self):
        por_id = {u.id: u for u in self.propias}
        return [por_id[o.unidad_id] for o in self.objetivos if o.tipo == "proteger" and o.unidad_id in por_id]

    def posicion_conocida(self, unidad_id):
        for e in self.enemigos:
            if e.id == unidad_id:
                return (e.lat, e.lon)
        for c in self.contactos:
            if c.unidad_id == unidad_id:
                return (c.lat, c.lon)
        for b in self.bases_enemigas:
            if b.id == unidad_id:
                return (b.lat, b.lon)
        return None

    def amenazas(self):
        """Defensas antiaereas y cazas enemigos visibles con el alcance de su clase (lo que se puede saber de ellos);
        de un sistema de defensa aerea identificado (Buk, Pechora...) se conoce su alcance real."""
        lista = []
        for e in self.enemigos:
            c = catalogo.obtener(e.clase, e.tipo)
            if c.defensa_aerea or (e.tipo == "aerea" and not e.en_tierra and c.ataque_vs.get("aerea", 0) >= 1.0):
                s = defensa_aerea.sistema(e)
                lista.append((e.lat, e.lon, max(a.alcance_max_km for a in s.armas) if s else c.alcance_km))
        return lista

    def en_peligro(self, lat, lon, margen=1.3) -> bool:
        return any(geo.distancia_km(lat, lon, a, b) <= r * margen for a, b, r in self.amenazas())

    def frente(self):
        """Centro del enemigo conocido (visto o ultimo contacto)."""
        return (_centro([(e.lat, e.lon) for e in self.enemigos] + [(c.lat, c.lon) for c in self.contactos])
                or _centro([(b.lat, b.lon) for b in self.bases_enemigas]))

    # ---------------------------------------------------------------- aeronaves
    def aeronave(self, u):
        clase = catalogo.obtener(u.clase, u.tipo)
        if u.en_tierra:
            if u.espera_restante > 0 or u.combustible < SALIDA_COMBUSTIBLE or (u.municion < SALIDA_MUNICION and clase.ataque_vs and any(clase.ataque_vs.values())):
                return
        else:
            sin_armas = not any(catalogo.perfil(u).ataque_vs.values())
            if u.combustible <= REGRESO_COMBUSTIBLE + self.nivel["regreso"] or (u.municion <= 5 and not sin_armas):
                if self.aterrizar(u):
                    return
        sin_armas = not any(catalogo.perfil(u).ataque_vs.values())
        if sin_armas and not u.en_tierra and self.en_peligro(u.lat, u.lon):
            return self.replegar(u)  # aviones sin armas: fuera del alcance de la defensa enemiga
        if clase.id == "cisterna":
            return self.cisterna(u)
        if clase.id in ("alerta_temprana", "dron_reconocimiento"):
            return self.vigilancia(u)
        if clase.interferencia_km and self.interferir(u):
            return
        blanco = self.mejor_blanco(u, u.alcance_km)
        if blanco and u.municion > 0 and self.ordenar(u, tipo="atacar", objetivo_unidad_id=blanco.id):
            return
        blanco = self.mejor_blanco(u)
        if blanco and u.municion > 0:
            base = min(self.bases_para(u), key=lambda b: geo.distancia_km(blanco.lat, blanco.lon, b.lat, b.lon), default=None)
            ida = max(0.0, geo.distancia_km(u.lat, u.lon, blanco.lat, blanco.lon) - u.alcance_km * self.nivel["aproximacion"])
            vuelta = geo.distancia_km(blanco.lat, blanco.lon, base.lat, base.lon) if base else 0.0
            if ida + vuelta * 1.15 < self.autonomia_restante(u):
                lat, lon = _punto_a_distancia(u, blanco.lat, blanco.lon, u.alcance_km * self.nivel["aproximacion"])
                expuesto = (self.nivel["evita_antiaerea"] and not catalogo.obtener(blanco.clase, blanco.tipo).defensa_aerea
                            and self.en_peligro(lat, lon, 1.0))
                if not expuesto and self.mover(u, lat, lon):
                    return
        if u.municion > 0 and not sin_armas and self.hacia_objetivo_aereo(u):
            return
        if not u.en_tierra:
            self.patrullar(u)

    def hacia_objetivo_aereo(self, u) -> bool:
        """Sin blancos a la vista: se acerca a la posicion conocida de un objetivo a destruir que pueda batir, hasta
        tenerlo a distancia de deteccion y de tiro, si le alcanza el combustible para volver."""
        destinos = []
        for o in self.objetivos:
            if o.tipo not in ("destruir", "neutralizar") or not o.unidad_id:
                continue
            p = self.posicion_conocida(o.unidad_id)
            es_base = any(b.id == o.unidad_id for b in self.bases_enemigas)
            if p and (es_base or o.unidad_id in {c.unidad_id for c in self.contactos}) \
                    and catalogo.perfil(u).ataque_vs.get("terrestre", 0) > 0:
                destinos.append(p)
        if not destinos:
            return False
        lat, lon = min(destinos, key=lambda d: geo.distancia_km(u.lat, u.lon, d[0], d[1]))
        margen = min(u.alcance_km, u.deteccion_km or u.alcance_km) * self.nivel["aproximacion"]
        base = min(self.bases_para(u), key=lambda b: geo.distancia_km(lat, lon, b.lat, b.lon), default=None)
        ida = max(0.0, geo.distancia_km(u.lat, u.lon, lat, lon) - margen)
        vuelta = geo.distancia_km(lat, lon, base.lat, base.lon) if base else 0.0
        if ida + vuelta * 1.15 >= self.autonomia_restante(u):
            return False
        return self.mover(u, *_punto_a_distancia(u, lat, lon, margen))

    def aterrizar(self, u) -> bool:
        """En la base mas cercana que tenga plazas, contando las que ya piden otros grupos este turno."""
        n = max(1, u.aeronaves or 1)
        for b in sorted(self.bases_para(u), key=lambda b: geo.distancia_km(u.lat, u.lon, b.lat, b.lon)):
            if aeronaves_mod.plazas_libres(b, self.propias) - self.reservas.get(b.id, 0) < n:
                continue
            if self.ordenar(u, tipo="aterrizar", objetivo_unidad_id=b.id):
                self.reservas[b.id] = self.reservas.get(b.id, 0) + n
                return True
        return False

    def replegar(self, u):
        base = min(self.bases_para(u), key=lambda b: geo.distancia_km(u.lat, u.lon, b.lat, b.lon), default=None)
        if base and not self.en_peligro(base.lat, base.lon):
            if self.ordenar(u, tipo="patrullar", waypoints=[(base.lat, base.lon)]):
                return
        # alejarse de la amenaza mas cercana el doble de su alcance
        a, b, r = min(self.amenazas(), key=lambda t: geo.distancia_km(u.lat, u.lon, t[0], t[1]))
        punto = geo.destino(a, b, _rumbo(a, b, u.lat, u.lon), r * 2)
        self.ordenar(u, tipo="mover", waypoints=[punto])

    def patrullar(self, u):
        protegidas = self.protegidas()
        punto = _centro([(p.lat, p.lon) for p in protegidas]) if protegidas else None
        frente = self.frente()
        if punto is None and frente is not None:
            # patrulla de combate a medio camino hacia el enemigo, fuera de su defensa antiaerea conocida
            base = min(self.bases_para(u), key=lambda b: geo.distancia_km(u.lat, u.lon, b.lat, b.lon), default=None)
            origen = (base.lat, base.lon) if base else (u.lat, u.lon)
            d = geo.distancia_km(origen[0], origen[1], frente[0], frente[1])
            rumbo = _rumbo(origen[0], origen[1], frente[0], frente[1])
            for fraccion in (0.5, 0.3, 0.15):
                candidato = geo.destino(origen[0], origen[1], rumbo, d * fraccion)
                if not self.en_peligro(*candidato):
                    punto = candidato
                    break
        if punto is None:
            base = min(self.bases_para(u), key=lambda b: geo.distancia_km(u.lat, u.lon, b.lat, b.lon), default=None)
            punto = (base.lat, base.lon) if base else (u.lat, u.lon)
        self.ordenar(u, tipo="patrullar", waypoints=[punto])

    def vigilancia(self, u):
        """Reconocimiento y alerta temprana: orbitan entre lo propio y el enemigo conocido (o adelante de su base)."""
        frente = self.frente()
        propio = _centro([(p.lat, p.lon) for p in self.propias if p.tipo != "aerea"]) or (u.lat, u.lon)
        if frente is None:
            return self.ordenar(u, tipo="patrullar", waypoints=[propio])
        # a medio camino, sin entrar en la defensa enemiga: un tercio de la distancia desde lo propio
        d = geo.distancia_km(propio[0], propio[1], frente[0], frente[1])
        rumbo = _rumbo(propio[0], propio[1], frente[0], frente[1])
        for fraccion in (1 / 3, 1 / 5, 1 / 10, 0.0):  # lo mas adelante posible sin entrar en la defensa enemiga
            punto = geo.destino(propio[0], propio[1], rumbo, d * fraccion)
            if not self.en_peligro(*punto):
                break
        self.ordenar(u, tipo="patrullar", waypoints=[punto])

    def cisterna(self, u):
        if u.en_tierra:
            return
        en_vuelo = [a for a in self.propias if a.tipo == "aerea" and not a.en_tierra and a is not u
                    and catalogo.obtener(a.clase, a.tipo).id != "cisterna"]
        punto = _centro([(a.lat, a.lon) for a in en_vuelo]) or (u.lat, u.lon)
        if self.en_peligro(*punto):
            return self.replegar(u)
        self.ordenar(u, tipo="patrullar", waypoints=[punto])

    def interferir(self, u) -> bool:
        """Interfiere donde se concentra el enemigo visible (sus radares y antiaerea primero)."""
        clave = [e for e in self.enemigos if (e.clase or "") in ("radar", "antiaerea", "guerra_electronica", "destructor")]
        for grupo in (clave, self.enemigos):
            centro = _centro([(e.lat, e.lon) for e in grupo])
            if centro and ge_mod.error_de_interferencia(u, centro) is None:
                return self.ordenar(u, tipo="interferir", waypoints=[centro])
        return False

    # ---------------------------------------------------------------- bases y portaaviones
    def base(self, b):
        """Lanza un grupo de caza si el enemigo tiene aviacion a la vista y la propia en vuelo no la iguala."""
        aviones_enemigos = [e for e in self.enemigos if e.tipo == "aerea" and not e.en_tierra]
        cazas_propios = [a for a in self.propias if a.tipo == "aerea" and not a.en_tierra
                         and catalogo.perfil(a).ataque_vs.get("aerea", 0) >= 1.0]
        if not aviones_enemigos or len(cazas_propios) > len(aviones_enemigos) * self.nivel["cazas_por_enemigo"]:
            return
        for modelo in self.modelos_caza(b):
            if self.ordenar(b, tipo="despegar", modelo=modelo, aeronaves=GRUPO_CAZA):
                return

    def modelos_caza(self, b):
        """Los modelos de caza que ya usa el bando (primero) y los del catalogo que pueden salir de esa base."""
        usados = [a.modelo for a in self.propias if a.modelo and a.modelo in catalogo.MODELOS
                  and catalogo.MODELOS[a.modelo].clase == "caza"]
        resto = [m.id for m in catalogo.MODELOS.values() if m.clase == "caza"]
        vistos, orden = set(), []
        for m in usados + resto:
            if m not in vistos and (catalogo.opera_aeronaves(b) and (b.tipo == "base" or catalogo.es_embarcable("caza", m))):
                vistos.add(m)
                orden.append(m)
        return orden

    # ---------------------------------------------------------------- tierra
    def terrestre(self, u):
        clase = catalogo.obtener(u.clase, u.tipo)
        if clase.lanza_misiles and self.salva(u):
            return
        if balisticos_mod.lanza(u):
            self.balistico(u)  # en posicion: solo lanza
            return
        if clase.interferencia_km and self.interferir(u):
            return
        if clase.carga_max:
            return self.convoy(u)
        if clase.id in ("radar", "guerra_electronica", "antiaerea", "antiaerea_portatil", "lanzador_misiles", "ingenieros"):
            return  # sensores, defensa antiaerea (dispara sola) y apoyos: en posicion
        if not any(catalogo.perfil(u).ataque_vs.values()):
            return
        if (u.combustible < REABASTECER or u.municion < REABASTECER) and self.reabastecer(u):
            return
        blanco = self.mejor_blanco(u, u.alcance_km)
        if blanco and u.municion > 0 and self.relacion(u, blanco) >= self.nivel["relacion"]:
            if self.ordenar(u, tipo="atacar", objetivo_unidad_id=blanco.id):
                return
        if self.ir_a_objetivo(u):
            return
        blanco = self.mejor_blanco(u)
        if blanco and self.relacion(u, blanco) >= self.nivel["relacion"] and geo.distancia_km(u.lat, u.lon, blanco.lat, blanco.lon) < self.nivel["persecucion_km"]:
            lat, lon = _punto_a_distancia(u, blanco.lat, blanco.lon, u.alcance_km * self.nivel["aproximacion"])
            self.mover(u, lat, lon)

    def ir_a_objetivo(self, u) -> bool:
        destinos = []
        for o in self.objetivos:
            if o.tipo == "ocupar" and o.lat is not None:
                if geo.distancia_km(u.lat, u.lon, o.lat, o.lon) > o.radio_km * 0.5:
                    destinos.append((o.lat, o.lon, 0.0))
            elif o.tipo in ("destruir", "neutralizar") and o.unidad_id:
                p = self.posicion_conocida(o.unidad_id)
                if p:
                    destinos.append((p[0], p[1], u.alcance_km * self.nivel["aproximacion"]))
            elif o.tipo == "proteger":
                p = next((x for x in self.propias if x.id == o.unidad_id), None)
                if p and p is not u and geo.distancia_km(u.lat, u.lon, p.lat, p.lon) > 10:
                    destinos.append((p.lat, p.lon, 3.0))
        if not destinos:
            return False
        lat, lon, margen = min(destinos, key=lambda d: geo.distancia_km(u.lat, u.lon, d[0], d[1]))
        lat, lon = _punto_a_distancia(u, lat, lon, margen) if margen else (lat, lon)
        return self.mover(u, lat, lon)

    def reabastecer(self, u) -> bool:
        fuentes = [b for b in self.propias if b is not u and (
            (b.tipo == "base" and u.tipo in catalogo.obtener(b.clase, b.tipo).suministra)
            or (catalogo.obtener(b.clase, b.tipo).nodo_movil_km and u.tipo in catalogo.obtener(b.clase, b.tipo).suministra))]
        f = min(fuentes, key=lambda b: geo.distancia_km(u.lat, u.lon, b.lat, b.lon), default=None)
        if f is None:
            return False
        radio = catalogo.obtener(f.clase, f.tipo).nodo_movil_km or f.alcance_km or 1.0
        if geo.distancia_km(u.lat, u.lon, f.lat, f.lon) <= radio:
            return False  # ya esta al alcance: se reabastece quieto
        lat, lon = _punto_a_distancia(u, f.lat, f.lon, radio * 0.5)
        return self.mover(u, lat, lon)

    def convoy(self, u):
        clase = catalogo.obtener(u.clase, u.tipo)
        necesitadas = [x for x in self.propias if x is not u and x.tipo in clase.suministra
                       and min(x.combustible, x.municion) < 60]
        if not necesitadas or u.carga < 15:
            return self.reabastecer_convoy(u)
        x = min(necesitadas, key=lambda x: (min(x.combustible, x.municion), geo.distancia_km(u.lat, u.lon, x.lat, x.lon)))
        lat, lon = _punto_a_distancia(u, x.lat, x.lon, clase.nodo_movil_km * 0.5)
        self.mover(u, lat, lon)

    def reabastecer_convoy(self, u):
        depositos = [b for b in self.propias if b.tipo == "base" and u.tipo in catalogo.obtener(b.clase, b.tipo).suministra]
        d = min(depositos, key=lambda b: geo.distancia_km(u.lat, u.lon, b.lat, b.lon), default=None)
        if d and geo.distancia_km(u.lat, u.lon, d.lat, d.lon) > d.alcance_km:
            lat, lon = _punto_a_distancia(u, d.lat, d.lon, d.alcance_km * 0.5)
            self.mover(u, lat, lon)

    def salva(self, u) -> bool:
        blancos = sorted((e for e in self.enemigos if misiles_mod.blanco_valido(e)),
                         key=lambda e: -PRIORIDAD.get(e.clase or "", 1.0) / (1 + geo.distancia_km(u.lat, u.lon, e.lat, e.lon) / 100))
        for e in blancos:
            n = 2 if u.municion >= 50 else 1
            if misiles_mod.error_de_lanzamiento(u, e, n) is None and self.ordenar(u, tipo="lanzar", objetivo_unidad_id=e.id, misiles=n):
                return True
        return False

    def balistico(self, u) -> bool:
        """Salva balistica contra el mejor blanco visible a su alcance: las instalaciones fijas primero, porque el misil
        cae donde estaba el blanco al lanzar (no ataca aeronaves en vuelo ni buques, que se mueven)."""
        def puntaje(e):
            fijo = e.tipo == "base" or getattr(e, "en_tierra", False)
            d = geo.distancia_km(u.lat, u.lon, e.lat, e.lon)
            return -(PRIORIDAD.get(e.clase or "", 1.0) * (2.0 if fijo else 1.0) / (1 + d / 200))
        blancos = sorted((e for e in self.enemigos if e.tipo in ("base", "terrestre") or getattr(e, "en_tierra", False)),
                         key=puntaje)
        n = 2 if u.municion >= 2 * balisticos_mod.MUNICION_POR_MISIL else 1
        for e in blancos:
            if balisticos_mod.error_de_lanzamiento(u, e, n) is None and self.ordenar(u, tipo="lanzar", objetivo_unidad_id=e.id, misiles=n):
                return True
        return False

    # ---------------------------------------------------------------- mar
    def naval(self, u):
        clase = catalogo.obtener(u.clase, u.tipo)
        if clase.lanza_misiles and self.salva(u):
            return
        blanco = self.mejor_blanco(u, u.alcance_km)
        if blanco and u.municion > 0 and self.ordenar(u, tipo="atacar", objetivo_unidad_id=blanco.id):
            return
        if catalogo.opera_aeronaves(u):
            return self.base(u)
        blanco = self.mejor_blanco(u)
        if blanco and blanco.tipo == "naval" and self.relacion(u, blanco) >= self.nivel["relacion"]:
            lat, lon = _punto_a_distancia(u, blanco.lat, blanco.lon, u.alcance_km * self.nivel["aproximacion"])
            if self.terreno is None or self.terreno.clase(lat, lon) == "agua":
                self.mover(u, lat, lon)

    # ---------------------------------------------------------------- turno
    def jugar(self) -> list[str]:
        # una aeronave que vuelve a aterrizar (combustible critico o decision previa) no se distrae
        con_orden = {uid for uid, o in self.activas.items() if o.tipo == "aterrizar"}
        # primero las bases (despegues), luego aeronaves, mar y tierra
        orden = sorted(self.propias, key=lambda u: {"base": 0, "aerea": 1, "naval": 2}.get(u.tipo, 3))
        for u in orden:
            if u.id in con_orden:
                continue
            try:
                if u.tipo == "base":
                    if catalogo.opera_aeronaves(u):
                        self.base(u)
                elif u.tipo == "aerea":
                    self.aeronave(u)
                elif u.tipo == "naval":
                    self.naval(u)
                else:
                    self.terrestre(u)
            except Exception:  # noqa: BLE001 - una unidad problematica no detiene al resto del bando
                log.exception("Adversario automatico: no se pudo decidir la orden de %s", u.nombre)
        return self.decisiones


def jugar_turno(db: Session, esc: Escenario, terreno=None, bandos=None) -> dict[str, list[str]]:
    """Una decision de los bandos que conduce el simulador: las ordenes nuevas que hacen falta. No confirma la
    transaccion. En tiempo real se llama cada IA_CADA_S simulados (y al encender la IA), tambien con el reloj
    detenido, salvo con el escenario finalizado."""
    if esc.estado == "finalizado":
        return {}
    terreno = terreno or get_terreno()
    resultado = {}
    # la visibilidad no cambia mientras se dan las ordenes: se calcula una vez por bando
    original = state.unidades_visibles_para
    memoria: dict = {}

    def visibles(db_, esc_, rol, terreno_=None):
        if (esc_.id, rol) not in memoria:
            memoria[(esc_.id, rol)] = original(db_, esc_, rol, terreno_ or terreno)
        return memoria[(esc_.id, rol)]

    state.unidades_visibles_para = visibles
    try:
        for bando in bandos or ("azul", "rojo"):
            if not getattr(esc, f"ia_{bando}", False):
                continue
            resultado[bando] = _Turno(db, esc, bando, terreno).jugar()
    finally:
        state.unidades_visibles_para = original
    db.flush()
    return resultado
