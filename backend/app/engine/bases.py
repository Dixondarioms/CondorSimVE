"""Daño por partes de las bases aereas y refugios reforzados.

Ademas de su fuerza general, una base aerea (o un portaaviones) tiene tres partes con su propio daño (0-100 %):
la pista, la plataforma y el deposito de combustible. Un ataque puede dirigirse a una parte ("parte" en el detalle
de la orden de ataque) o ser general:

- pista >= 60 % de daño: la base no lanza ni recibe aviones (pista inoperativa), aunque su fuerza sea alta;
- plataforma: los aviones estacionados sufren mas daño en cada ataque (hasta el doble);
- combustible: las existencias maximas se reducen en proporcion y el excedente se pierde.

Los refugios reforzados (`refugios`, cantidad de grupos que caben protegidos) reducen a un cuarto el daño que
reciben los grupos estacionados que alcanzan refugio (los primeros por id). La pista se repara sola un poco cada
turno y mucho mas con ingenieros propios junto a la base; la plataforma y el deposito, solo con ingenieros.
"""

from app.engine import catalogo, geo

PARTES = ("pista", "plataforma", "combustible")
PISTA_INOPERATIVA = 60.0  # % de daño de la pista a partir del cual no hay despegues ni aterrizajes
DANO_A_PARTE_DIRIGIDO = 1.5  # el daño a la base se aplica a la parte atacada multiplicado por esto
DANO_A_PARTES_GENERAL = 0.5  # ... y en un ataque general, a cada parte por esto
REPARACION_PISTA_SOLA = 8.0  # % por turno que la base recupera de su pista con sus propios medios
REPARACION_CON_INGENIEROS = 25.0  # % por turno adicional en cada parte con ingenieros propios a <= 5 km
RADIO_INGENIEROS_KM = 5.0
PROTECCION_REFUGIO = 0.25  # fraccion del daño que sufre un grupo dentro de un refugio reforzado
REFUGIOS_POR_DEFECTO = 4  # refugios con que nace una base aerea (el instructor los ajusta)


def dano(base, parte: str) -> float:
    return float(getattr(base, f"dano_{parte}", 0.0) or 0.0)


def pista_operativa(base) -> bool:
    return dano(base, "pista") < PISTA_INOPERATIVA


def motivo_pista(base) -> str:
    return f"La pista de {base.nombre} esta inoperativa ({dano(base, 'pista'):.0f} % de daño): no hay despegues ni aterrizajes."


def aplicar_dano(base, perdida: float, parte: str | None = None) -> dict:
    """Reparte en las partes la perdida de fuerza que sufrio la base. Devuelve {parte: daño nuevo}."""
    if perdida <= 0 or not catalogo.opera_aeronaves(base):
        return {}
    cambios = {}
    for p in PARTES:
        extra = perdida * (DANO_A_PARTE_DIRIGIDO if parte == p else 0.0 if parte in PARTES else DANO_A_PARTES_GENERAL)
        if extra > 0:
            nuevo = min(100.0, dano(base, p) + extra)
            setattr(base, f"dano_{p}", nuevo)
            cambios[p] = nuevo
    return cambios


def factor_combustible(base) -> float:
    """Fraccion de las existencias maximas que el deposito conserva."""
    return 1.0 - dano(base, "combustible") / 100.0


def factor_plataforma(base) -> float:
    """Multiplicador del daño que sufren los aviones estacionados (1 intacta, 2 destruida)."""
    return 1.0 + dano(base, "plataforma") / 100.0


def protegidos(base, estacionados) -> set:
    """Ids de los grupos estacionados que alcanzan un refugio reforzado (los primeros por id)."""
    n = int(getattr(base, "refugios", 0) or 0)
    return {x.id for x in sorted(estacionados, key=lambda x: x.id)[:n]}


def reparar(base, unidades) -> dict:
    """Reparacion al final del turno: la pista sola un poco; todo mas con ingenieros propios cerca."""
    if not catalogo.opera_aeronaves(base) or base.estado != "activa":
        return {}
    ingenieros = any(
        u.bando == base.bando and u.estado == "activa" and catalogo.obtener(u.clase, u.tipo).construye
        and geo.distancia_km(u.lat, u.lon, base.lat, base.lon) <= RADIO_INGENIEROS_KM
        for u in unidades
    )
    cambios = {}
    for p in PARTES:
        d = dano(base, p)
        if d <= 0:
            continue
        cuanto = (REPARACION_PISTA_SOLA if p == "pista" else 0.0) + (REPARACION_CON_INGENIEROS if ingenieros else 0.0)
        if cuanto > 0:
            setattr(base, f"dano_{p}", max(0.0, d - cuanto))
            cambios[p] = getattr(base, f"dano_{p}")
    return cambios


def texto_partes(base) -> str:
    return ", ".join(f"{p} {dano(base, p):.0f} %" for p in PARTES)
