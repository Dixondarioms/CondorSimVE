"""Identidad nacional de cada bando: para que un ejercicio se pueda ambientar con Venezuela o contra alguno de
sus vecinos, o entre dos paises cualesquiera de America (en un supuesto que no involucre a Venezuela).

Es una capa de nombre y color sobre el bando ("azul"/"rojo" siguen siendo el bando real del motor, con su
simbologia y su niebla de guerra de siempre): no representa el orden de batalla real de esos paises, que el
catalogo (`catalogo.py`) no modela por pais. El terreno de referencia (fronteras, estados, ciudades) de todo el
continente esta en `frontend/static/geo/` (ver `tools/preparar_terreno.py`), y los aerodromos en
`frontend/static/geo/bases_aereas.geojson` (`tools/generar_bases_aereas.py`, que usa PAISES_AMERICA de aqui)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Nacion:
    id: str
    nombre: str
    gentilicio: str
    capital: str
    colores: tuple  # 2-3 colores (hex) para una franja identificativa simple, sin ser el escudo/bandera oficial
    iso: str = ""  # ISO 3166-1 alfa-2, para enlazar con los datos geograficos (aerodromos, fronteras)


# Estados soberanos de America. Venezuela va primero (es el bando propio por defecto) y el resto en orden
# alfabetico, tal como se muestra en el selector del instructor.
_LISTA = [
    Nacion("venezuela", "Venezuela", "venezolano", "Caracas", ("#FFCC00", "#00247D", "#CF142B"), "VE"),
    Nacion("argentina", "Argentina", "argentino", "Buenos Aires", ("#74ACDF", "#FFFFFF", "#F6B40E"), "AR"),
    Nacion("bahamas", "Bahamas", "bahameño", "Nasáu", ("#00778B", "#FFC72C", "#000000"), "BS"),
    Nacion("barbados", "Barbados", "barbadense", "Bridgetown", ("#00267F", "#FFC726", "#000000"), "BB"),
    Nacion("belice", "Belice", "beliceño", "Belmopán", ("#003F87", "#FFFFFF", "#CE1126"), "BZ"),
    Nacion("bolivia", "Bolivia", "boliviano", "Sucre (sede de gobierno: La Paz)", ("#D52B1E", "#F9E300", "#007934"), "BO"),
    Nacion("brasil", "Brasil", "brasileño", "Brasilia", ("#009C3B", "#FFDF00", "#002776"), "BR"),
    Nacion("canada", "Canadá", "canadiense", "Ottawa", ("#FF0000", "#FFFFFF"), "CA"),
    Nacion("chile", "Chile", "chileno", "Santiago", ("#FFFFFF", "#0039A6", "#D52B1E"), "CL"),
    Nacion("colombia", "Colombia", "colombiano", "Bogotá", ("#FCD116", "#003893", "#CE1126"), "CO"),
    Nacion("costa_rica", "Costa Rica", "costarricense", "San José", ("#002B7F", "#FFFFFF", "#CE1126"), "CR"),
    Nacion("cuba", "Cuba", "cubano", "La Habana", ("#002A8F", "#FFFFFF", "#CB1515"), "CU"),
    Nacion("ecuador", "Ecuador", "ecuatoriano", "Quito", ("#FFDD00", "#034EA2", "#ED1C24"), "EC"),
    Nacion("el_salvador", "El Salvador", "salvadoreño", "San Salvador", ("#0F47AF", "#FFFFFF"), "SV"),
    Nacion("estados_unidos", "Estados Unidos", "estadounidense", "Washington D. C.", ("#B22234", "#FFFFFF", "#3C3B6E"), "US"),
    Nacion("guatemala", "Guatemala", "guatemalteco", "Ciudad de Guatemala", ("#4997D0", "#FFFFFF"), "GT"),
    Nacion("guyana", "Guyana", "guyanés", "Georgetown", ("#009E49", "#FCD116", "#CE1126"), "GY"),
    Nacion("haiti", "Haití", "haitiano", "Puerto Príncipe", ("#00209F", "#D21034"), "HT"),
    Nacion("honduras", "Honduras", "hondureño", "Tegucigalpa", ("#00BCE4", "#FFFFFF"), "HN"),
    Nacion("jamaica", "Jamaica", "jamaiquino", "Kingston", ("#009B3A", "#FED100", "#000000"), "JM"),
    Nacion("mexico", "México", "mexicano", "Ciudad de México", ("#006847", "#FFFFFF", "#CE1126"), "MX"),
    Nacion("nicaragua", "Nicaragua", "nicaragüense", "Managua", ("#0067C6", "#FFFFFF"), "NI"),
    Nacion("panama", "Panamá", "panameño", "Ciudad de Panamá", ("#FFFFFF", "#005293", "#D21034"), "PA"),
    Nacion("paraguay", "Paraguay", "paraguayo", "Asunción", ("#D52B1E", "#FFFFFF", "#0038A8"), "PY"),
    Nacion("peru", "Perú", "peruano", "Lima", ("#D91023", "#FFFFFF"), "PE"),
    Nacion("republica_dominicana", "República Dominicana", "dominicano", "Santo Domingo", ("#002D62", "#FFFFFF", "#CE1126"), "DO"),
    Nacion("surinam", "Surinam", "surinamés", "Paramaribo", ("#377E3F", "#FFFFFF", "#B40A2D"), "SR"),
    Nacion("trinidad_tobago", "Trinidad y Tobago", "trinitense", "Puerto España", ("#CE1126", "#000000", "#FFFFFF"), "TT"),
    Nacion("uruguay", "Uruguay", "uruguayo", "Montevideo", ("#FFFFFF", "#0038A8", "#FCD116"), "UY"),
]
# Estados FICTICIOS del mapa ficticio (region "teatro_ficticio", tools/generar_mapa_ficticio.py), para ejercicios
# que no involucran a ningun pais real. Codigos XV y XO: el rango X* de ISO 3166 es de uso privado.
_FICTICIAS = [
    Nacion("valdoria", "País Azul (ficticio)", "azul", "Capital Azul", ("#1F4E9C", "#FFFFFF", "#3FA34D"), "XV"),
    Nacion("ostrania", "País Rojo (ficticio)", "rojo", "Capital Roja", ("#B3202A", "#1A1A1A", "#F2C14E"), "XO"),
]
# Estados de otras regiones que aparecen en las operaciones historicas (engine/historicas.py). La coalicion de 1991
# usa el codigo XC (rango X* de uso privado de ISO 3166).
_HISTORICAS = [
    Nacion("reino_unido", "Reino Unido", "británico", "Londres", ("#012169", "#FFFFFF", "#C8102E"), "GB"),
    Nacion("israel", "Israel", "israelí", "Jerusalén", ("#FFFFFF", "#0038B8"), "IL"),
    Nacion("irak", "Irak", "iraquí", "Bagdad", ("#CE1126", "#FFFFFF", "#000000"), "IQ"),
    Nacion("libia", "Libia", "libio", "Trípoli", ("#239E46", "#FFFFFF"), "LY"),
    Nacion("coalicion", "Coalición (1991)", "de la coalición", "-", ("#002868", "#FFFFFF", "#BF0A30"), "XC"),
]


def _sin_tildes(texto: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


# Venezuela primero; despues los paises reales en orden alfabetico; al final los ficticios y la coalicion
_REALES = sorted(_LISTA[1:] + [n for n in _HISTORICAS if not n.iso.startswith("X")], key=lambda n: _sin_tildes(n.nombre))
NACIONES: dict[str, Nacion] = {n.id: n for n in [_LISTA[0], *_REALES, *_FICTICIAS,
                                                 *(n for n in _HISTORICAS if n.iso.startswith("X"))]}

# Nombre en español de cada pais o territorio de America (ISO 3166-1 alfa-2), incluidos los que no son estados
# soberanos (y por eso no estan en NACIONES): sirve para rotular datos geograficos como los aerodromos.
PAISES_AMERICA: dict[str, str] = {
    **{n.iso: n.nombre for n in _LISTA + _FICTICIAS},
    "AG": "Antigua y Barbuda", "DM": "Dominica", "GD": "Granada", "KN": "San Cristóbal y Nieves",
    "LC": "Santa Lucía", "VC": "San Vicente y las Granadinas",
    # territorios y dependencias
    "AI": "Anguila (Reino Unido)", "AW": "Aruba (Países Bajos)", "BL": "San Bartolomé (Francia)",
    "BM": "Bermudas (Reino Unido)", "BQ": "Caribe Neerlandés (Países Bajos)", "CW": "Curazao (Países Bajos)",
    "FK": "Islas Malvinas (Reino Unido)", "GF": "Guayana Francesa (Francia)", "GL": "Groenlandia (Dinamarca)",
    "GP": "Guadalupe (Francia)", "GS": "Georgia del Sur (Reino Unido)", "KY": "Islas Caimán (Reino Unido)",
    "MF": "San Martín (Francia)", "MQ": "Martinica (Francia)", "MS": "Montserrat (Reino Unido)",
    "PM": "San Pedro y Miquelón (Francia)", "PR": "Puerto Rico (Estados Unidos)", "SX": "Sint Maarten (Países Bajos)",
    "TC": "Islas Turcas y Caicos (Reino Unido)", "UM": "Islas menores de Estados Unidos",
    "VG": "Islas Vírgenes Británicas (Reino Unido)", "VI": "Islas Vírgenes de los Estados Unidos",
}


def obtener(id_nacion: str | None) -> Nacion | None:
    return NACIONES.get(id_nacion or "")


def nacion_dict(n: Nacion) -> dict:
    return {"id": n.id, "nombre": n.nombre, "gentilicio": n.gentilicio, "capital": n.capital, "colores": list(n.colores), "iso": n.iso}
