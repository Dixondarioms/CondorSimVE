"""Existencias de combustible y municion de las bases (logistica de base).

Cada base (aerea, deposito, puerto) guarda existencias en puntos: 100 puntos llenan una unidad. De ahi salen:
- el reabastecimiento de las unidades a su alcance (hasta +50 % por turno, si hay existencias);
- el despegue de grupos aereos (25 puntos de combustible y 25 de municion por aeronave): sin existencias
  suficientes la base no puede lanzarlos ("sin logistica");
- la recarga de los convoyes en los depositos.
Los depositos reponen existencias cada turno (la linea de abastecimiento de retaguardia) y los convoyes llevan
suministros a las bases aereas y puertos: la logistica pasa a ser una decision del bando (puesto A4).
"""

from app.engine import catalogo

STOCK_INICIAL = 1000.0
COSTO_DESPEGUE_POR_AERONAVE = 25.0
CARGA_A_STOCK = 4.0  # 1 punto de carga de un convoy = 4 puntos de existencias (mitad combustible, mitad municion)
ENTREGA_CONVOY_POR_TURNO = 25.0  # carga que un convoy descarga en una base por turno
VARIABLES = ("combustible", "municion")


def stock(b, variable: str) -> float:
    v = getattr(b, f"stock_{variable}", None)
    return STOCK_INICIAL if v is None else float(v)


def maximo(b) -> float:
    return catalogo.obtener(b.clase, b.tipo).stock_max or 2 * STOCK_INICIAL


def cambiar_stock(b, variable: str, delta: float) -> None:
    setattr(b, f"stock_{variable}", max(0.0, min(maximo(b), stock(b, variable) + delta)))


def carga_disponible(b, carga: float) -> float:
    """Cuanta carga de convoy puede entregar la base segun sus existencias."""
    return max(0.0, min(carga, min(stock(b, v) for v in VARIABLES) * 2 / CARGA_A_STOCK))


def retirar_carga(b, carga: float) -> None:
    for v in VARIABLES:
        cambiar_stock(b, v, -carga * CARGA_A_STOCK / 2)


def carga_que_admite(b, carga: float) -> float:
    """Cuanta carga de convoy puede recibir la base antes de llenarse."""
    return max(0.0, min(carga, min(maximo(b) - stock(b, v) for v in VARIABLES) * 2 / CARGA_A_STOCK))


def depositar_carga(b, carga: float) -> None:
    for v in VARIABLES:
        cambiar_stock(b, v, carga * CARGA_A_STOCK / 2)


def reponer(b) -> None:
    r = catalogo.obtener(b.clase, b.tipo).reposicion_turno
    if r:
        for v in VARIABLES:
            cambiar_stock(b, v, r)


def costo_despegue(aeronaves: int) -> float:
    return COSTO_DESPEGUE_POR_AERONAVE * max(1, aeronaves or 1)


def falta_para_despegue(b, aeronaves: int) -> str | None:
    """Motivo "sin logistica" si la base no tiene existencias para lanzar el grupo (None si puede)."""
    costo = costo_despegue(aeronaves)
    faltan = [v for v in VARIABLES if stock(b, v) < costo]
    if not faltan:
        return None
    return (f"Sin logistica: {b.nombre} no tiene {' ni '.join(faltan)} suficiente para {aeronaves} aeronave(s) "
            f"(necesita {costo:.0f} de cada uno; tiene {stock(b, 'combustible'):.0f} de combustible y "
            f"{stock(b, 'municion'):.0f} de municion).")


def descontar_despegue(b, aeronaves: int) -> None:
    for v in VARIABLES:
        cambiar_stock(b, v, -costo_despegue(aeronaves))
