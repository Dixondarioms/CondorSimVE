"""Identidad nacional de cada bando: para que un ejercicio se pueda ambientar con Venezuela o contra alguno de
sus vecinos (o entre dos vecinos, en un supuesto que no involucre a Venezuela).

Es una capa de nombre y color sobre el bando ("azul"/"rojo" siguen siendo el bando real del motor, con su
simbologia y su niebla de guerra de siempre): no representa el orden de batalla real de esos paises, que el
catalogo (`catalogo.py`) no modela por pais. El terreno de referencia (fronteras, departamentos/estados,
ciudades) de estos mismos paises esta en `frontend/static/geo/` (ver `tools/preparar_terreno.py`)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Nacion:
    id: str
    nombre: str
    gentilicio: str
    capital: str
    colores: tuple  # 2-3 colores (hex) para una franja identificativa simple, sin ser el escudo/bandera oficial


NACIONES: dict[str, Nacion] = {n.id: n for n in [
    Nacion("venezuela", "Venezuela", "venezolano", "Caracas", ("#FFCC00", "#00247D", "#CF142B")),
    Nacion("colombia", "Colombia", "colombiano", "Bogotá", ("#FCD116", "#003893", "#CE1126")),
    Nacion("brasil", "Brasil", "brasileño", "Brasilia", ("#009C3B", "#FFDF00", "#002776")),
    Nacion("guyana", "Guyana", "guyanés", "Georgetown", ("#009E49", "#FCD116", "#CE1126")),
    Nacion("trinidad_tobago", "Trinidad y Tobago", "trinitense", "Puerto España", ("#CE1126", "#000000", "#FFFFFF")),
    Nacion("estados_unidos", "Estados Unidos", "estadounidense", "Washington D. C.", ("#B22234", "#FFFFFF", "#3C3B6E")),
]}


def obtener(id_nacion: str | None) -> Nacion | None:
    return NACIONES.get(id_nacion or "")


def nacion_dict(n: Nacion) -> dict:
    return {"id": n.id, "nombre": n.nombre, "gentilicio": n.gentilicio, "capital": n.capital, "colores": list(n.colores)}
