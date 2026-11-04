"""Relieve y linea de vista: las montañas y la curvatura de la Tierra ocultan a los sensores; perfil de vuelo.

Con la grilla de alturas (tools/preparar_elevacion.py) un sensor solo detecta lo que esta en su linea de vista:
- Cada unidad tiene una altura: la del terreno donde esta mas la de su antena o su cota de vuelo (ALTURA_*).
- Entre el sensor y el objetivo se recorre el perfil del terreno; si algun punto sobresale de la linea recta que
  los une, el objetivo queda oculto (sombra de radar). Se usa el radio terrestre efectivo de 4/3 (refraccion
  normal del radar), de modo que el horizonte tambien oculta: un buque o un avion rasante desaparecen tras la
  curvatura aunque el mar sea plano.
- Las aeronaves vuelan en un PERFIL: alto, medio o rasante (cota sobre el terreno). Alto se ve desde muy lejos,
  esta fuera del techo de los misiles portatiles y gasta menos; rasante se esconde tras el relieve, pero gasta
  mas y queda expuesto a la antiaerea portatil. Los misiles de crucero vuelan siempre rasantes.

Sin grilla de alturas (pruebas, datos de mapa sin instalar) todo tiene linea de vista: el motor se comporta como
antes. La logica es pura: el terreno solo se consulta con terreno.altura(lat, lon).
"""

import math
from types import SimpleNamespace

from app.engine import catalogo, geo

R_EFECTIVO_KM = 8495.0  # 4/3 del radio terrestre: refraccion normal de las ondas de radar
PASO_KM = 0.6  # separacion de las muestras del perfil del terreno (la grilla de Venezuela tiene celdas de ~600 m)
MAX_MUESTRAS = 400
MARGEN_EXTREMOS_KM = 0.8  # el terreno pegado al sensor o al objetivo no los oculta (es donde estan parados)
TOLERANCIA_M = 5.0  # ruido de la grilla: lo que sobresale menos que esto no tapa

PERFILES = ("alto", "medio", "rasante")
ALTURA_PERFIL_M = {"alto": 6000.0, "medio": 1500.0, "rasante": 60.0}  # sobre el terreno
NOMBRE_PERFIL = {"alto": "Alto (6 000 m)", "medio": "Medio (1 500 m)", "rasante": "Rasante (60 m)"}
FACTOR_CONSUMO = {"alto": 0.85, "medio": 1.0, "rasante": 1.3}
ALTURA_MISIL_M = 30.0  # los misiles de crucero vuelan pegados al terreno o al mar
TECHO_PORTATIL_M = 3500.0  # una antiaerea portatil (tipo IGLA-S) no alcanza a una aeronave en perfil alto
FACTOR_PORTATIL_RASANTE = 1.25  # ... y a baja cota la aeronave queda mas expuesta a ella
CLASES_SIN_PERFIL_ALTO = ("helicoptero", "helicoptero_artillado", "municion_merodeadora")
CLASES_PERFIL_ALTO = ("alerta_temprana", "cisterna")  # vuelan alto por defecto (radar sobre el relieve, orbita)

# Altura de la antena o del sensor sobre el terreno (o sobre el mar), y la del blanco que ofrece la unidad.
ANTENA_M = {
    "radar": 25.0, "antiaerea": 12.0, "reconocimiento": 10.0, "guerra_electronica": 10.0, "lanzador_misiles": 6.0,
    "destructor": 30.0, "fragata": 25.0, "portaaviones": 40.0, "patrullero": 12.0, "buque_desembarco": 20.0,
    "submarino": 2.0,
}
ANTENA_POR_TIPO = {"terrestre": 3.0, "naval": 15.0, "base": 15.0, "aerea": 3.0}


def _clase_id(u) -> str:
    return getattr(u, "clase", None) or ""


def es_misil(u) -> bool:
    return catalogo.obtener(_clase_id(u), u.tipo).id == "misil_crucero" if u.tipo == "aerea" else False


def en_vuelo(u) -> bool:
    return u.tipo == "aerea" and not getattr(u, "en_tierra", False)


def perfiles_permitidos(u) -> tuple[str, ...]:
    """Perfiles que puede elegir una aeronave (ninguno: no vuela, o es un misil, que va siempre rasante)."""
    if u.tipo != "aerea" or es_misil(u):
        return ()
    if _clase_id(u) in CLASES_SIN_PERFIL_ALTO:
        return ("medio", "rasante")
    return PERFILES


def perfil_por_defecto(u) -> str | None:
    if u.tipo != "aerea":
        return None
    if es_misil(u) or _clase_id(u) in ("helicoptero", "helicoptero_artillado"):
        return "rasante"
    if _clase_id(u) in CLASES_PERFIL_ALTO:
        return "alto"
    return "medio"


def perfil_de(u) -> str | None:
    """Perfil de vuelo efectivo (el elegido, si es valido para la unidad; si no, el de su clase)."""
    if u.tipo != "aerea":
        return None
    if es_misil(u):
        return "rasante"
    elegido = getattr(u, "perfil_vuelo", None)
    return elegido if elegido in perfiles_permitidos(u) else perfil_por_defecto(u)


def altura_sobre_terreno(u) -> float:
    """Metros sobre el suelo (o el mar): cota de vuelo para lo que esta en el aire; antena o silueta para el resto."""
    if en_vuelo(u):
        return ALTURA_MISIL_M if es_misil(u) else ALTURA_PERFIL_M[perfil_de(u)]
    return ANTENA_M.get(_clase_id(u), ANTENA_POR_TIPO.get(u.tipo, 3.0))


def altura_suelo(terreno, lat: float, lon: float) -> float:
    h = terreno.altura(lat, lon) if terreno is not None else None
    return max(0.0, h) if h is not None else 0.0  # el mar (batimetria negativa) cuenta como nivel 0


def altura_msl(u, terreno) -> float:
    """Metros sobre el nivel del mar del sensor o del blanco."""
    base = 0.0 if u.tipo == "naval" else altura_suelo(terreno, u.lat, u.lon)
    return base + altura_sobre_terreno(u)


def factor_consumo(u) -> float:
    """Multiplicador del combustible que gasta una aeronave segun su perfil (1 para el resto)."""
    p = perfil_de(u) if en_vuelo(u) and not es_misil(u) else None
    return FACTOR_CONSUMO.get(p, 1.0)


def fuera_de_techo(atacante, objetivo) -> bool:
    """Una antiaerea portatil no alcanza a una aeronave en perfil alto."""
    return _clase_id(atacante) == "antiaerea_portatil" and en_vuelo(objetivo) and perfil_de(objetivo) == "alto"


def factor_portatil(atacante, objetivo) -> float:
    return FACTOR_PORTATIL_RASANTE if _clase_id(atacante) == "antiaerea_portatil" and en_vuelo(objetivo) and perfil_de(objetivo) == "rasante" else 1.0


# ---------------------------------------------------------------- linea de vista
def visible(terreno, lat1: float, lon1: float, h1: float, lat2: float, lon2: float, h2: float) -> bool:
    """True si la recta entre (lat1, lon1) a h1 m y (lat2, lon2) a h2 m (sobre el nivel del mar) no la corta el
    terreno ni la curvatura de la Tierra (radio efectivo de 4/3)."""
    d = geo.distancia_km(lat1, lon1, lat2, lon2)
    if d <= 2 * MARGEN_EXTREMOS_KM:
        return True
    n = min(MAX_MUESTRAS, max(8, int(d / PASO_KM)))
    for i in range(1, n):
        f = i / n
        s = d * f
        if s < MARGEN_EXTREMOS_KM or d - s < MARGEN_EXTREMOS_KM:
            continue
        linea = h1 + (h2 - h1) * f
        abombamiento = s * (d - s) / (2.0 * R_EFECTIVO_KM) * 1000.0  # la Tierra se levanta entre ambos (m)
        suelo = altura_suelo(terreno, lat1 + (lat2 - lat1) * f, lon1 + (lon2 - lon1) * f)
        if suelo + abombamiento > linea + TOLERANCIA_M:
            return False
    return True


def linea_de_vista(terreno, sensor, objetivo) -> bool:
    """Si `sensor` ve a `objetivo` por relieve y horizonte (sin contar alcance, clima ni firma: eso lo decide
    vision.py). Sin alturas cargadas, siempre True. Se cachea por posiciones y alturas (cambian una vez por turno)."""
    if terreno is None or not getattr(terreno, "tiene_elevacion", False):
        return True
    h1, h2 = altura_msl(sensor, terreno), altura_msl(objetivo, terreno)
    clave = (round(sensor.lat, 4), round(sensor.lon, 4), round(h1), round(objetivo.lat, 4), round(objetivo.lon, 4), round(h2))
    cache = terreno.__dict__.setdefault("_cache_linea_de_vista", {})
    if clave not in cache:
        if len(cache) > 50000:
            cache.clear()
        cache[clave] = visible(terreno, sensor.lat, sensor.lon, h1, objetivo.lat, objetivo.lon, h2)
    return cache[clave]


# ---------------------------------------------------------------- cobertura de un sensor
def cobertura(terreno, sensor, alcance_km: float, altura_blanco_m: float, rumbos: int = 72,
              altura_sensor_m: float | None = None) -> list[list[float]]:
    """Poligono [[lat, lon], ...] de lo que `sensor` ve hasta `alcance_km` de un blanco que vuela a
    `altura_blanco_m` sobre el terreno: por cada rumbo, la distancia hasta la primera sombra del relieve o del
    horizonte. Una sola pasada por rumbo: se guarda el mayor angulo de elevacion del terreno visto hasta alli y el
    blanco se ve mientras su angulo lo supere. `altura_sensor_m`: el sensor a esa altura sobre el suelo (si no, la
    de su clase)."""
    h0 = (altura_suelo(terreno, sensor.lat, sensor.lon) + altura_sensor_m if altura_sensor_m is not None
          else altura_msl(sensor, terreno))
    pasos = max(1, min(MAX_MUESTRAS, int(alcance_km / PASO_KM)))
    km_por_paso = alcance_km / pasos
    anillo = []
    for k in range(rumbos):
        rumbo = 360.0 * k / rumbos
        max_angulo = -math.inf
        alcance = alcance_km
        for i in range(1, pasos + 1):
            s = i * km_por_paso
            lat, lon = geo.destino(sensor.lat, sensor.lon, rumbo, s)
            caida = s * s / (2.0 * R_EFECTIVO_KM) * 1000.0
            suelo = altura_suelo(terreno, lat, lon)
            angulo_blanco = (suelo + altura_blanco_m - caida - h0) / (s * 1000.0)
            if s > MARGEN_EXTREMOS_KM and angulo_blanco < max_angulo - TOLERANCIA_M / (s * 1000.0):
                alcance = s - km_por_paso
                break
            if s > MARGEN_EXTREMOS_KM:
                max_angulo = max(max_angulo, (suelo - caida - h0) / (s * 1000.0))
        lat, lon = geo.destino(sensor.lat, sensor.lon, rumbo, max(0.0, alcance))
        anillo.append([round(lat, 5), round(lon, 5)])
    return anillo


def blanco_de_prueba(lat: float, lon: float, perfil: str) -> SimpleNamespace:
    """Aeronave ficticia en ese perfil, para medir el alcance de un sensor contra ella."""
    return SimpleNamespace(tipo="aerea", clase="caza", lat=lat, lon=lon, en_tierra=False, perfil_vuelo=perfil)
