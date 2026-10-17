"""Sistemas de defensa aerea con sus armas: ZU-23-2, S-125 Pechora-2M y Buk-M2E.

Cada sistema es un modelo del catalogo (clase "antiaerea" o "artilleria_antiaerea") con lo que el resto de la
antiaerea no tiene: sus armas (misiles guiados por radar o infrarrojos, y canones), con alcance minimo y maximo,
techo, probabilidad de derribo por misil y misiles por blanco; los misiles listos en los lanzadores y la reserva en
los vehiculos de recarga; radar de vigilancia (ve y alimenta el cuadro) y radar de tiro (guia los misiles); tiempo de
reaccion, canales de tiro, tiempos de despliegue y repliegue, vehiculos y personal.

Enfrentamiento (cada turno de 1 h, `enfrentar`): la bateria tiene 3 600 s de tiempo de fuego (menos lo que tardo en
moverse y desplegarse). Para cada aeronave enemiga que su bando detecta, elige el arma (la que fijo el operador o la
automatica: la de mayor probabilidad que alcance esa altura y distancia) y calcula:
  - la geometria: segun hacia donde vuela la aeronave respecto de la bateria (de frente, de traves o alejandose) el
    misil la alcanza a toda su distancia o solo a una parte (`factor_aspecto`);
  - la exposicion: cuanto tiempo de la hora pasa la aeronave dentro de ese alcance (la cuerda de su trayectoria);
  - las salvas que caben: (exposicion - reaccion) / (reaccion + tiempo de vuelo del misil + evaluacion), limitadas
    por los misiles listos; si se acaban, la bateria recarga desde su reserva y queda inoperativa ese tiempo;
  - la probabilidad de derribo por salva: 1 - (1 - pk)^misiles, con pk afectada por la interferencia enemiga (el
    radar de tiro pierde alcance y precision), la maniobra evasiva de las aeronaves tripuladas, la firma radar
    (furtivos), la cota baja para los misiles guiados por radar y la noche para los canones de punteria optica.
Los derribos esperados restan aeronaves al grupo (su fuerza). Los valores son de referencia (fuentes abiertas) y
didacticos, ajustables; no son datos oficiales de los sistemas.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass

from app.engine import geo

TURNO_S = 3600.0
EVALUACION_S = 10.0  # tras cada salva, evaluar el resultado antes de la siguiente
REACCION_CUE_S = 20.0  # si el radar propio no tenia la traza (avisa otro sensor del bando), se suma a la reaccion
# modificadores de la probabilidad de derribo
FACTOR_INTERFERENCIA_PK = 0.6  # misiles guiados por radar dentro de una interferencia enemiga
FACTOR_INTERFERENCIA_ALCANCE = 0.6  # el radar de tiro interferido solo "quema" la interferencia mas cerca
FACTOR_EVASION = {"misil_radar": 0.8, "misil_ir": 0.8, "canon": 0.7}  # aeronave tripulada que maniobra
FACTOR_NOCHE_CANON = 0.6  # punteria optica de noche
FACTOR_COTA_BAJA_RADAR = 0.85  # a pocos metros sobre el suelo el radar de tiro sufre el eco del terreno
# las armas rinden distinto segun el blanco: helicopteros y drones son lentos y bajos (canones), los misiles de
# crucero son pequenos y rapidos, los aviones grandes (alerta temprana, cisternas) son faciles
FACTOR_BLANCO = {
    "helicoptero": 1.5, "helicoptero_artillado": 1.5, "dron_reconocimiento": 1.3, "dron_ataque": 1.3,
    "municion_merodeadora": 1.2, "misil_crucero": 0.6, "alerta_temprana": 1.3, "cisterna": 1.3, "avion_ge": 1.1,
}
TIPOS_ARMA = {"misil_radar": "Misil guiado por radar", "misil_ir": "Misil infrarrojo", "canon": "Cañón (puntería óptica)"}


@dataclass(frozen=True)
class Arma:
    id: str
    nombre: str
    tipo: str  # "misil_radar" | "misil_ir" | "canon"
    categoria: str  # "largo" | "corto": para que el operador elija
    alcance_min_km: float
    alcance_max_km: float
    altura_min_m: float
    altura_max_m: float
    pk: float  # probabilidad de derribo de un misil (o una rafaga) contra un caza que no maniobra
    por_blanco: int  # misiles (o rafagas) por salva
    velocidad_ms: float  # para el tiempo de vuelo
    cargados: int  # listos en los lanzadores
    reserva: int  # en los vehiculos de transporte y recarga
    recarga_min: float  # tiempo para volver a cargar los lanzadores desde la reserva (inoperativa)

    @property
    def guiado_radar(self) -> bool:
        return self.tipo == "misil_radar"


@dataclass(frozen=True)
class Sistema:
    modelo: str
    armas: tuple[Arma, ...]
    radar_vigilancia_km: float  # 0 = sin radar propio: depende del cuadro de su bando
    radar_tiro_km: float  # 0 = punteria optica o infrarroja
    reaccion_s: float  # de la deteccion al disparo
    canales: int  # blancos que puede batir a la vez
    despliegue_min: float  # de marcha a listo para tirar
    repliegue_min: float  # de listo a marcha
    movilidad: str
    vehiculos: tuple[tuple[int, str], ...]
    personal: int
    nota: str = ""

    def arma(self, arma_id: str | None) -> Arma | None:
        return next((a for a in self.armas if a.id == arma_id), None)

    @property
    def total_vehiculos(self) -> int:
        return sum(n for n, _ in self.vehiculos)


_ZU23 = Arma("zu23", "ZU-23-2 (cañón bitubo de 23 mm)", "canon", "corto", 0.2, 2.5, 0.0, 1500.0, 0.08, 3, 970.0,
             20, 120, 1.0)
SISTEMAS: dict[str, Sistema] = {s.modelo: s for s in [
    Sistema(
        "zu23_2", (_ZU23,), radar_vigilancia_km=0.0, radar_tiro_km=0.0, reaccion_s=6.0, canales=2,
        despliegue_min=1.0, repliegue_min=1.0, movilidad="Remolcada por camión (pesada: cruza ríos por puentes)",
        vehiculos=((2, "montajes ZU-23-2"), (2, "camiones tractores con la munición")), personal=12,
        nota="Defensa cercana de muy baja cota con puntería óptica: no emite, no la detecta la escucha enemiga, "
             "pero de noche tira peor. Depende del cuadro aéreo de su bando para saber qué viene."),
    Sistema(
        "pechora_2m", (
            Arma("5v27de", "5V27DE (largo alcance)", "misil_radar", "largo", 3.5, 32.0, 20.0, 20000.0, 0.6, 2, 900.0,
                 8, 8, 30.0),
            _ZU23,
        ), radar_vigilancia_km=160.0, radar_tiro_km=75.0, reaccion_s=25.0, canales=1,
        despliegue_min=25.0, repliegue_min=25.0, movilidad="Lanzadores y radares sobre camión (pesada)",
        vehiculos=((4, "lanzadores 5P73-2M de 2 misiles"), (1, "radar de tiro SNR-125-2M"),
                   (1, "radar de vigilancia P-18-2"), (1, "puesto de mando de la batería"),
                   (4, "vehículos de transporte y carga de misiles"), (2, "grupos electrógenos"),
                   (2, "montajes ZU-23-2 de defensa cercana"), (2, "camiones tractores")),
        personal=60,
        nota="Batería de mediano alcance modernizada. Un radar de tiro guía un blanco a la vez; recargar los "
             "lanzadores desde los vehículos de carga la deja unos 30 min sin poder tirar con misiles. Los "
             "ZU-23-2 de la batería cubren la cota muy baja."),
    Sistema(
        "buk_m2e", (
            Arma("9m317e", "9M317E (largo alcance)", "misil_radar", "largo", 3.0, 45.0, 15.0, 25000.0, 0.75, 2, 1200.0,
                 12, 8, 13.0),
            Arma("igla_s", "Igla-S (defensa cercana)", "misil_ir", "corto", 0.5, 6.0, 10.0, 3500.0, 0.4, 1, 600.0,
                 4, 8, 1.0),
        ), radar_vigilancia_km=160.0, radar_tiro_km=45.0, reaccion_s=12.0, canales=8,
        despliegue_min=5.0, repliegue_min=5.0, movilidad="Autopropulsada sobre orugas (pesada)",
        vehiculos=((2, "TELAR 9A317E (radar de tiro y 4 misiles)"), (1, "TEL 9A316E (4 misiles y 8 de recarga)"),
                   (1, "radar de vigilancia 9S18M1-3E"), (1, "puesto de mando 9S510E"),
                   (1, "vehículo de mantenimiento"), (1, "sección Igla-S de defensa cercana")),
        personal=30,
        nota="Batería de mediano alcance con radar de tiro en cada TELAR: hasta 8 blancos a la vez. Recargar los "
             "TELAR desde el TEL toma unos 13 min sin poder tirar con 9M317E. La sección Igla-S cubre la cota baja "
             "cercana sin emitir."),
]}


# ---------------------------------------------------------------------------------------------- estado de la unidad
def sistema(u) -> Sistema | None:
    return SISTEMAS.get(getattr(u, "modelo", "") or "")


def _guardado(u) -> dict:
    try:
        datos = json.loads(getattr(u, "cargas_json", None) or "{}")
    except ValueError:
        datos = {}
    return datos if isinstance(datos, dict) else {}


def cargas(u, s: Sistema | None = None) -> dict[str, int]:
    """Misiles (o rafagas) listos de cada arma; al principio, los lanzadores llenos."""
    s = s or sistema(u)
    if s is None:
        return {}
    listos = _guardado(u).get("listos", {})
    return {a.id: int(listos.get(a.id, a.cargados)) for a in s.armas}


def reservas(u, s: Sistema | None = None) -> dict[str, int]:
    """Misiles de recarga de cada arma (en los vehiculos de transporte y carga). Cada arma lleva la suya; la municion
    de la unidad (%) es el total que queda, y cuando el deposito o el convoy la reponen, lo repuesto se reparte entre
    las armas a las que les falta."""
    s = s or sistema(u)
    if s is None:
        return {}
    guardada = _guardado(u).get("reserva")
    pct = max(0.0, min(100.0, getattr(u, "municion", 100.0) or 0.0))
    if guardada is None:  # aun no tiro: la reserva sigue a la municion de la unidad
        return {a.id: int(math.floor(a.reserva * pct / 100.0 + 1e-9)) for a in s.armas}
    res = {a.id: int(guardada.get(a.id, a.reserva)) for a in s.armas}
    total = reserva_total(s)
    repuesto = int(round(total * pct / 100.0)) - sum(res.values())
    while repuesto > 0:  # reabastecida: una a una, al arma con mas faltante relativo
        faltan = [a for a in s.armas if res[a.id] < a.reserva]
        if not faltan:
            break
        a = max(faltan, key=lambda x: (x.reserva - res[x.id]) / x.reserva)
        res[a.id] += 1
        repuesto -= 1
    return res


def guardar_cargas(u, listos: dict[str, int], reserva: dict[str, int] | None = None) -> None:
    s = sistema(u)
    reserva = reserva if reserva is not None else reservas(u, s)
    u.cargas_json = json.dumps({"listos": listos, "reserva": reserva}, sort_keys=True)
    total = reserva_total(s) if s else 0
    if total:
        u.municion = 100.0 * sum(reserva.values()) / total


def reserva_total(s: Sistema) -> int:
    return sum(a.reserva for a in s.armas)


def reserva_disponible(u, s: Sistema, arma: Arma) -> int:
    return reservas(u, s).get(arma.id, 0)


def arma_elegida(u, s: Sistema | None = None) -> Arma | None:
    s = s or sistema(u)
    return s.arma(getattr(u, "arma_elegida", None)) if s else None


# ---------------------------------------------------------------------------------------------- geometria
def _xy(lat0: float, lon0: float, lat: float, lon: float) -> tuple[float, float]:
    """Plano local en km centrado en (lat0, lon0)."""
    return ((lon - lon0) * 111.32 * math.cos(math.radians(lat0)), (lat - lat0) * 110.57)


def factor_aspecto(bat, desde: tuple[float, float] | None, hasta: tuple[float, float]) -> tuple[float, str]:
    """Cuanto del alcance del misil sirve segun el rumbo de la aeronave respecto de la bateria: 1 si viene de frente,
    ~0,8 si pasa de traves, 0,55 si se aleja (el misil tiene que perseguirla). Sin movimiento (orbita): 1."""
    if desde is None:
        return 1.0, "en órbita"
    x0, y0 = _xy(bat.lat, bat.lon, *desde)
    x1, y1 = _xy(bat.lat, bat.lon, *hasta)
    vx, vy = x1 - x0, y1 - y0
    v = math.hypot(vx, vy)
    d = math.hypot(x1, y1)
    if v < 1.0 or d < 1e-6:
        return 1.0, "en órbita"
    coseno = (vx * -x1 + vy * -y1) / (v * d)  # >0: la aeronave se acerca a la bateria
    f = 0.775 + 0.225 * coseno
    etiqueta = "de frente" if coseno > 0.5 else "alejándose" if coseno < -0.5 else "de través"
    return f, etiqueta


def exposicion_s(bat, desde: tuple[float, float] | None, hasta: tuple[float, float], radio_km: float,
                 radio_min_km: float = 0.0) -> float:
    """Segundos de la hora que la aeronave paso dentro del alcance [min, max] (cuerda de su trayectoria del turno)."""

    def dentro_de(radio: float) -> float:
        if radio <= 0:
            return 0.0
        x1, y1 = _xy(bat.lat, bat.lon, *hasta)
        if desde is None:
            return TURNO_S if math.hypot(x1, y1) <= radio else 0.0
        x0, y0 = _xy(bat.lat, bat.lon, *desde)
        dx, dy = x1 - x0, y1 - y0
        largo = math.hypot(dx, dy)
        if largo < 1.0:  # quieta u orbitando: todo el turno donde esta
            return TURNO_S if math.hypot(x1, y1) <= radio else 0.0
        # interseccion del segmento P0 + t*(P1-P0), t en [0,1], con el circulo de radio `radio`
        a = dx * dx + dy * dy
        b = 2 * (x0 * dx + y0 * dy)
        c = x0 * x0 + y0 * y0 - radio * radio
        disc = b * b - 4 * a * c
        if disc <= 0:
            return 0.0
        r = math.sqrt(disc)
        t0, t1 = max(0.0, (-b - r) / (2 * a)), min(1.0, (-b + r) / (2 * a))
        return max(0.0, t1 - t0) * TURNO_S

    return max(0.0, dentro_de(radio_km) - dentro_de(radio_min_km))


def puede_batir(arma: Arma, distancia_km: float, altura_m: float) -> bool:
    return arma.alcance_min_km <= distancia_km <= arma.alcance_max_km and arma.altura_min_m <= altura_m <= arma.altura_max_m


# ---------------------------------------------------------------------------------------------- enfrentamiento
@dataclass
class Disparo:
    blanco_id: int
    arma: Arma
    salvas: int
    misiles: int
    pk: float  # por misil, ya con los modificadores
    p_salva: float  # probabilidad de derribar una aeronave por salva
    derribos: float  # aeronaves derribadas esperadas
    aspecto: str
    distancia_km: float
    exposicion_s: float
    efectos: list[str]
    evasion: bool = False

    def texto(self, nombre_blanco: str) -> str:
        return (f"{self.salvas} salva(s) de {self.arma.nombre} ({self.misiles} disparo(s)) contra {nombre_blanco} "
                f"a {self.distancia_km:.0f} km, {self.aspecto}; {self.exposicion_s / 60:.0f} min en alcance; "
                f"probabilidad por salva {self.p_salva * 100:.0f} %, derribos esperados {self.derribos:.1f}"
                + (f" ({'; '.join(self.efectos)})" if self.efectos else ""))


@dataclass
class Resultado:
    disparos: list[Disparo]
    recargas: list[str]
    sin_fuego: str = ""  # motivo si no pudo tirar
    motivos: dict = None  # blanco_id -> por que no se lo batio

    def __post_init__(self):
        if self.motivos is None:
            self.motivos = {}


def pk_efectivo(arma: Arma, blanco, *, interferida: bool, noche: bool, tripulada: bool, firma: float,
                altura_m: float) -> tuple[float, list[str], bool]:
    pk = arma.pk
    efectos: list[str] = []
    clase_blanco = getattr(blanco, "clase", "") or ""
    if clase_blanco in FACTOR_BLANCO:
        pk *= FACTOR_BLANCO[clase_blanco]
    if arma.guiado_radar:
        if interferida:
            pk *= FACTOR_INTERFERENCIA_PK
            efectos.append(f"radar de tiro interferido x{FACTOR_INTERFERENCIA_PK:.2f}")
        if firma < 1.0:
            pk *= 0.5 + 0.5 * firma
            efectos.append(f"firma radar reducida x{0.5 + 0.5 * firma:.2f}")
        if altura_m < 100.0:
            pk *= FACTOR_COTA_BAJA_RADAR
            efectos.append(f"cota muy baja (eco del terreno) x{FACTOR_COTA_BAJA_RADAR:.2f}")
    if arma.tipo == "canon" and noche:
        pk *= FACTOR_NOCHE_CANON
        efectos.append(f"puntería óptica de noche x{FACTOR_NOCHE_CANON:.2f}")
    evasion = tripulada
    if evasion:
        pk *= FACTOR_EVASION[arma.tipo]
        efectos.append(f"maniobra evasiva x{FACTOR_EVASION[arma.tipo]:.2f}")
    return max(0.0, min(0.95, pk)), efectos, evasion


def elegir_arma(s: Sistema, forzada: Arma | None, distancia_km: float, altura_m: float, radar_ok: bool,
                radio_radar_km: float, listos: dict[str, int], reserva: dict[str, int]) -> tuple[Arma | None, str]:
    """El arma con que se tira: la que fijo el operador o, en automatico, la de mayor probabilidad que alcance."""

    def apta(a: Arma) -> str:
        if not puede_batir(a, distancia_km, altura_m):
            if not a.altura_min_m <= altura_m <= a.altura_max_m:
                return f"{a.nombre}: fuera de su franja de altura ({a.altura_min_m:.0f}-{a.altura_max_m:.0f} m)"
            return f"{a.nombre}: fuera de alcance ({a.alcance_min_km:g}-{a.alcance_max_km:g} km)"
        if a.guiado_radar and not radar_ok:
            return f"{a.nombre}: radar de tiro apagado"
        if a.guiado_radar and distancia_km > radio_radar_km:
            return f"{a.nombre}: fuera del alcance del radar de tiro ({radio_radar_km:.0f} km)"
        if listos.get(a.id, 0) + reserva.get(a.id, 0) < a.por_blanco:
            return f"{a.nombre}: sin misiles"
        return ""

    if forzada is not None:
        motivo = apta(forzada)
        return (None, motivo) if motivo else (forzada, "")
    candidatas = [a for a in s.armas if not apta(a)]
    if not candidatas:
        return None, "; ".join(apta(a) for a in s.armas)
    return max(candidatas, key=lambda a: (a.pk, a.alcance_max_km)), ""


def enfrentar(bat, blancos: list[dict], *, se_movio: bool, radar_ok: bool, interferida: bool, noche: bool,
              arma_forzada: str | None = None) -> Resultado:
    """Tiro de una bateria durante el turno contra los blancos (dicts con unidad, desde, hasta, altura_m, firma,
    tripulada, aeronaves, traza_propia), ordenados del mas amenazante al menos. Actualiza sus cargas y su municion."""
    s = sistema(bat)
    if s is None:
        return Resultado([], [], "Sin sistema de armas")
    tiempo = TURNO_S
    if se_movio:
        tiempo -= TURNO_S / 2 + (s.repliegue_min + s.despliegue_min) * 60.0
        if tiempo <= 0:
            return Resultado([], [], f"Desplegando tras moverse ({s.despliegue_min:.0f} min)")
    listos = cargas(bat, s)
    reserva = reservas(bat, s)
    forzada = s.arma(arma_forzada) if arma_forzada else arma_elegida(bat, s)
    radio_radar = s.radar_tiro_km * (FACTOR_INTERFERENCIA_ALCANCE if interferida else 1.0)
    canales_tiempo = [tiempo] * max(1, s.canales)  # cada canal de tiro tiene su propia hora
    disparos: list[Disparo] = []
    recargas: list[str] = []
    motivos: dict[int, str] = {}

    for b in blancos:
        d = b["unidad"]
        distancia = geo.distancia_km(bat.lat, bat.lon, d.lat, d.lon)
        arma, motivo = elegir_arma(s, forzada, distancia, b["altura_m"], radar_ok, radio_radar, listos, reserva)
        if arma is None:
            motivos[d.id] = motivo
            continue
        f_asp, aspecto = factor_aspecto(bat, b.get("desde"), b["hasta"])
        alcance = arma.alcance_max_km * f_asp
        if arma.guiado_radar:
            alcance = min(alcance, radio_radar)
        expo = exposicion_s(bat, b.get("desde"), b["hasta"], alcance, arma.alcance_min_km)
        reaccion = s.reaccion_s + (0.0 if b.get("traza_propia", True) else REACCION_CUE_S)
        vuelo = distancia * 1000.0 / arma.velocidad_ms
        ciclo = reaccion + vuelo + EVALUACION_S
        canal = max(range(len(canales_tiempo)), key=lambda i: canales_tiempo[i])
        disponible = min(expo, canales_tiempo[canal]) + EVALUACION_S  # la ultima evaluacion puede ser despues
        if ciclo > disponible:
            motivos[d.id] = (f"{arma.nombre}: la aeronave paso solo {expo / 60:.0f} min a su alcance ({aspecto}) y la "
                             f"bateria necesita {ciclo:.0f} s para reaccionar y que el misil llegue")
            continue
        pk, efectos, evasion = pk_efectivo(arma, d, interferida=interferida, noche=noche, tripulada=b["tripulada"],
                                           firma=b["firma"], altura_m=b["altura_m"])
        p_salva = 1.0 - (1.0 - pk) ** arma.por_blanco
        quedan = max(0.0, float(b["aeronaves"]))
        salvas = 0
        usado = 0.0
        derribos = 0.0
        while usado + ciclo <= disponible and quedan - derribos > 0.05:
            if listos[arma.id] < arma.por_blanco:  # recargar los lanzadores desde la reserva: inoperativa
                if reserva[arma.id] < arma.por_blanco or usado + arma.recarga_min * 60.0 + ciclo > disponible:
                    break
                n = min(arma.cargados - listos[arma.id], reserva[arma.id])
                listos[arma.id] += n
                reserva[arma.id] -= n
                usado += arma.recarga_min * 60.0
                recargas.append(f"{bat.nombre} recargó {n} {arma.nombre} desde su reserva: {arma.recarga_min:.0f} min "
                                f"sin poder tirar con ese misil")
            listos[arma.id] -= arma.por_blanco
            salvas += 1
            usado += ciclo
            derribos += min(p_salva, quedan - derribos)  # cada salva va por una aeronave del grupo
        if not salvas:
            motivos[d.id] = f"{arma.nombre}: sin misiles listos ni tiempo para recargar"
            continue
        canales_tiempo[canal] -= usado
        disparos.append(Disparo(d.id, arma, salvas, salvas * arma.por_blanco, pk, p_salva, min(quedan, derribos),
                                aspecto, distancia, expo, efectos, evasion))

    # en el tiempo libre del turno, los lanzadores que quedaron a medias se recargan
    libre = max(canales_tiempo)
    for a in s.armas:
        falta = a.cargados - listos[a.id]
        if falta > 0 and reserva[a.id] > 0 and libre >= a.recarga_min * 60.0:
            n = min(falta, reserva[a.id])
            listos[a.id] += n
            reserva[a.id] -= n
    guardar_cargas(bat, listos, reserva)
    return Resultado(disparos, recargas, motivos=motivos)


# ---------------------------------------------------------------------------------------------- para la interfaz
def arma_dict(a: Arma) -> dict:
    return {"id": a.id, "nombre": a.nombre, "tipo": a.tipo, "tipo_nombre": TIPOS_ARMA[a.tipo], "categoria": a.categoria,
            "alcance_min_km": a.alcance_min_km, "alcance_max_km": a.alcance_max_km, "altura_min_m": a.altura_min_m,
            "altura_max_m": a.altura_max_m, "pk": a.pk, "por_blanco": a.por_blanco, "cargados": a.cargados,
            "reserva": a.reserva, "recarga_min": a.recarga_min}


def sistema_dict(s: Sistema) -> dict:
    return {"modelo": s.modelo, "armas": [arma_dict(a) for a in s.armas], "radar_vigilancia_km": s.radar_vigilancia_km,
            "radar_tiro_km": s.radar_tiro_km, "reaccion_s": s.reaccion_s, "canales": s.canales,
            "despliegue_min": s.despliegue_min, "repliegue_min": s.repliegue_min, "movilidad": s.movilidad,
            "vehiculos": [{"cantidad": n, "descripcion": t} for n, t in s.vehiculos],
            "total_vehiculos": s.total_vehiculos, "personal": s.personal, "nota": s.nota}


def estado_dict(u) -> dict | None:
    """Lo que el operador ve de su bateria: misiles listos y en reserva de cada arma y el arma elegida."""
    s = sistema(u)
    if s is None:
        return None
    listos, reserva = cargas(u, s), reservas(u, s)
    return {"armas": [{"id": a.id, "listos": listos[a.id], "reserva": reserva[a.id]} for a in s.armas],
            "arma_elegida": getattr(u, "arma_elegida", None)}
