"""Plantilla "Juegos de Guerra 01-2026: Operación Guri" (mapa de Venezuela) a partir de los documentos del ejercicio.

Fuentes: Situación General, Situación Azul ("Operación Guri"), Situación Rojo ("Escudo Protector Guri") y los planes
de campaña de cada bando (Timotocuica y Caribe), todos de junio de 2026. Las fuerzas iniciales salen de las
situaciones de cada bando; los planes de campaña van en el Problema Militar Operativo (pestaña TIEM) de su bando.

Supuestos del ejercicio (los documentos no los fijan):
- El "Paralelo 7" es 7° N: el País Rojo queda al norte (con el Guri, Angostura y el Bajo Caroní) y la República
  Federal Azul al sur. La Zona Desmilitarizada del Orinoco (ZDO) se dibuja como línea de fase en 7° N.
- Las bases con nombre clave se ubican en aeródromos reales a cada lado de la línea (ver BASES).
- Un grupo del simulador tiene como máximo 8 aeronaves, así que las flotas grandes van en varios grupos.
- C-130J, C-208, C-206, Y-8 de transporte, Do 228 y C-550 no tienen clase en el simulador (transporte de ala fija).
- Los sistemas sin modelo en el catálogo (MIM-23 Hawk, NASAMS, M-SHORAD) usan la clase genérica.

Las bases tienen muchas más aeronaves que las 12 plazas por base y los 24 por bando del simulador: la plantilla
necesita backend/data/ajustes_catalogo.json con más plazas y topes (lo escribe --ajustes).

    backend\\venv\\Scripts\\python tools\\crear_ejercicio_guri.py --ajustes          # plantilla + ajustes
    backend\\venv\\Scripts\\python tools\\crear_ejercicio_guri.py --ajustes --crear  # y crea el escenario con la ZDO
"""

import argparse
import json
import math
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "backend"))

from app import terreno as terreno_mod  # noqa: E402
from app.engine import catalogo  # noqa: E402

SALIDA = RAIZ / "backend" / "data" / "plantillas_sistema" / "guri_2026.json"
AJUSTES = RAIZ / "backend" / "data" / "ajustes_catalogo.json"
INFRA = json.loads((RAIZ / "frontend" / "static" / "geo" / "venezuela" / "infraestructura.json").read_text(encoding="utf-8"))
INFRA = {i["id"]: i for i in INFRA["instalaciones"]}
T = terreno_mod.cargar()
EN_TIERRA = ("llano", "bosque", "urbano", "montana", "pantano")
LINEA_ZDO = 7.0  # Paralelo 7 (norte): Rojo al norte, Azul al sur
STOCK_BASE = catalogo.CLASES["base_aerea"].stock_max

# Bases con su nombre clave, el aeródromo donde se las ubica y el combustible JP-1 (disponible / capacidad, litros)
BASES = {
    # ---- República Federal Azul (sur del paralelo 7) ----
    "Echo": ("azul", "Puerto Ayacucho", 5.6200, -67.6061, 2_659_000, 2_700_000),
    "Golf": ("azul", "Canaima", 6.2320, -62.8548, 640_000, 700_000),
    "Hotel": ("azul", "Santa Elena de Uairén", 4.5547, -61.1452, 140_000, 900_000),
    "Kilo": ("azul", "Puerto Páez", 6.2264, -67.4486, 180_000, 300_000),
    "Oscar": ("azul", "La Paragua", 6.8330, -63.3300, 110_000, 500_000),
    "November": ("azul", "Kavanayén", 5.6320, -61.7700, 140_000, 900_000),
    # ---- País Rojo (norte del paralelo 7) ----
    "Aves": ("rojo", "Barcelona", 10.1072, -64.6892, 1_600_000, 1_700_000),
    "Patos": ("rojo", "Maturín", 9.7490, -63.1533, 140_000, 300_000),
    "Roques": ("rojo", "Puerto Ordaz", 8.2847, -62.7639, 190_000, 200_000),
    "Tortuga": ("rojo", "Angostura, Ciudad Bolívar", 8.1222, -63.5369, 590_000, 700_000),
    "Orchila": ("rojo", "San Tomé", 8.9451, -64.1511, 380_000, 400_000),
}
GURI = (INFRA["inf011"]["lat"], INFRA["inf011"]["lon"])


def mover(lat, lon, rumbo_deg, km):
    return (lat + km * math.cos(math.radians(rumbo_deg)) / 111.0,
            lon + km * math.sin(math.radians(rumbo_deg)) / (111.0 * math.cos(math.radians(lat))))


def en_tierra(lat, lon, rumbo_deg=0.0, km=0.0, lado=None):
    """El punto a `km` con ese rumbo, corrido a la tierra firme más cercana y del lado correcto de la ZDO."""
    lat0, lon0 = mover(lat, lon, rumbo_deg, km)

    def valido(la, lo):
        if T.clase(la, lo) not in EN_TIERRA:
            return False
        if lado == "azul" and la > LINEA_ZDO - 0.03:
            return False
        if lado == "rojo" and la < LINEA_ZDO + 0.03:
            return False
        return True

    if valido(lat0, lon0):
        return round(lat0, 5), round(lon0, 5)
    for r in range(1, 25):
        for a in range(0, 360, 15):
            la, lo = mover(lat0, lon0, a, r * 0.5)
            if valido(la, lo):
                return round(la, 5), round(lo, 5)
    raise SystemExit(f"No hay tierra firme cerca de ({lat0:.3f}, {lon0:.3f})")


def armar():
    unidades, nombres = [], set()

    def u(nombre, bando, clase, lat, lon, **kw):
        if nombre in nombres:
            raise SystemExit(f"Nombre repetido: {nombre}")
        nombres.add(nombre)
        unidades.append({"nombre": nombre, "bando": bando, "clase": clase, "lat": lat, "lon": lon, **kw})

    def base(clave):
        bando, lugar, lat, lon, disp, cap = BASES[clave]
        nombre = f"Base {clave} ({lugar})"
        u(nombre, bando, "base_aerea", *en_tierra(lat, lon, lado=bando),
          stock_combustible=round(STOCK_BASE * disp / cap, 1))
        return nombre

    def grupos(clave_base, nombre, modelo_o_clase, total, por_grupo=8):
        """`total` aeronaves estacionadas en la base, en grupos de hasta `por_grupo`."""
        b = next(x for x in unidades if x["nombre"].startswith(f"Base {clave_base} "))
        if modelo_o_clase in catalogo.MODELOS:
            clase, modelo = catalogo.MODELOS[modelo_o_clase].clase, modelo_o_clase
        else:
            clase, modelo = modelo_o_clase, ""
        n_grupos = math.ceil(total / por_grupo)
        resto = total
        for i in range(n_grupos):
            n = min(por_grupo, resto)
            resto -= n
            sufijo = f" {i + 1}" if n_grupos > 1 else ""
            u(f"{nombre}{sufijo} ({clave_base})", b["bando"], clase, b["lat"], b["lon"], modelo=modelo, aeronaves=n,
              en_tierra=True, base=b["nombre"])

    def defensa(clave_base, nombre, clase, modelo, rumbo, km, centro=None):
        bando, _, lat, lon, *_ = BASES[clave_base]
        la, lo = centro or (lat, lon)
        u(f"{nombre} ({clave_base})", bando, clase, *en_tierra(la, lo, rumbo, km, lado=bando),
          **({"modelo": modelo} if modelo else {}))

    def tropa(clave_base, nombre, personal, escalon, rumbo, km, centro=None):
        bando, _, lat, lon, *_ = BASES[clave_base]
        la, lo = centro or (lat, lon)
        u(nombre, bando, "infanteria", *en_tierra(la, lo, rumbo, km, lado=bando), escalon=escalon, personal=personal)

    # ======================= REPÚBLICA FEDERAL AZUL (Situación Azul, Operación Guri) =======================
    for clave in ("Echo", "Golf", "Hotel", "Kilo", "Oscar", "November"):
        base(clave)
    grupos("Echo", "Escuadrón Kfir", "caza", 24)
    grupos("Echo", "Escuadrón F-16 Block 70", "f16", 48)
    grupos("Echo", "Escuadrón A-37 Dragonfly", "ataque_ligero", 12)
    grupos("Echo", "Boeing 737 tanquero", "cisterna", 2)
    grupos("Echo", "P-3 Orion (guerra electrónica)", "avion_ge", 2)
    defensa("Echo", "MIM-23 Hawk 1", "antiaerea", "", 45, 6)
    defensa("Echo", "MIM-23 Hawk 2", "antiaerea", "", 225, 6)
    for i, rumbo in enumerate((20, 110, 200, 290)):
        tropa("Echo", f"{i + 1}.er Batallón de Asalto Aéreo (Echo)" if i == 0 else f"{i + 1}.º Batallón de Asalto Aéreo (Echo)",
              750, "batallon", rumbo, 1.5)
    grupos("Golf", "UH-60 Black Hawk", "mh60m", 10, 5)
    grupos("Golf", "OV-10 Bronco", "ataque_ligero", 12)
    defensa("Golf", "NASAMS", "antiaerea", "", 0, 5)
    tropa("Golf", "1.er Batallón de Asalto Aéreo (Golf)", 600, "batallon", 90, 1.5)
    tropa("Golf", "2.º Batallón de Asalto Aéreo (Golf)", 600, "batallon", 270, 1.5)
    grupos("Hotel", "A-29 Super Tucano", "ataque_ligero", 12)
    defensa("Hotel", "MIM-23 Hawk", "antiaerea", "", 0, 6)
    defensa("Hotel", "NASAMS", "antiaerea", "", 180, 6)
    tropa("Hotel", "1.er Batallón de Asalto Aéreo (Hotel)", 725, "batallon", 90, 1.5)
    tropa("Hotel", "2.º Batallón de Asalto Aéreo (Hotel)", 725, "batallon", 270, 1.5)
    grupos("Kilo", "MQ-1 Predator", "uav_armado", 5)
    tropa("Kilo", "Compañía de Asalto Aéreo (Kilo)", 300, "compania", 90, 1.5)
    grupos("Oscar", "UH-60 Black Hawk", "mh60m", 10, 5)
    grupos("Oscar", "Bell 212", "helo_transporte", 1)
    defensa("Oscar", "NASAMS", "antiaerea", "", 0, 5)
    tropa("Oscar", "Batallón de Asalto Aéreo (Oscar)", 650, "batallon", 180, 1.5)
    grupos("November", "MQ-1 Predator", "uav_armado", 5)
    grupos("November", "MQ-9 Reaper", "mq9", 10, 5)
    grupos("November", "Bell 212", "helo_transporte", 2)
    grupos("November", "CH-47 Chinook", "mh47g", 5)
    defensa("November", "M-SHORAD 1", "antiaerea_portatil", "", 60, 3)
    defensa("November", "M-SHORAD 2", "antiaerea_portatil", "", 240, 3)
    tropa("November", "Compañía de Asalto Aéreo (November)", 150, "compania", 150, 1.5)
    # Infraestructura de Azul: estación terrena (comunicaciones) y la refinadora de tierras raras del centro del país
    i = INFRA["inf002"]
    u(i["nombre"], "azul", "centro_comunicaciones", i["lat"], i["lon"])
    u("Planta refinadora de tierras raras (centro de Azul)", "azul", "refineria", *en_tierra(5.75, -64.60, lado="azul"))

    # ======================= PAÍS ROJO (Situación Rojo, Escudo Protector Guri) =======================
    for clave in ("Aves", "Patos", "Roques", "Tortuga", "Orchila"):
        base(clave)
    grupos("Aves", "Escuadrón Su-30MK2", "su30", 14)
    grupos("Aves", "Escuadrón K-8W", "ataque_ligero", 10)
    grupos("Aves", "Y-8W (alerta temprana)", "alerta_temprana", 2)
    grupos("Aves", "Metro Merlin ELINT", "avion_ge", 1)
    for n, rumbo in enumerate((0, 120, 240)):
        defensa("Aves", f"S-300VM Antey-2500 {n + 1}", "antiaerea", "s300vm", rumbo, 12)
    defensa("Aves", "Buk-M3", "antiaerea", "buk_m2e", 60, 7)
    tropa("Aves", "1.er Batallón de Defensa de Base (Aves)", 750, "batallon", 300, 3)
    tropa("Aves", "2.º Batallón de Defensa de Base (Aves)", 750, "batallon", 150, 3)
    grupos("Patos", "AS532 Cougar", "helo_transporte", 4)
    defensa("Patos", "S-300VM Antey-2500", "antiaerea", "s300vm", 0, 10)
    defensa("Patos", "Buk-M3", "antiaerea", "buk_m2e", 120, 7)
    defensa("Patos", "S-125 Pechora-2M", "antiaerea", "pechora_2m", 240, 5)
    # Roques: sin aviones; su defensa aérea en capas protege la represa del Guri, y su guarnición está en la represa
    defensa("Roques", "S-300VM Antey-2500 (Guri)", "antiaerea", "s300vm", 0, 15, centro=GURI)
    defensa("Roques", "Buk-M3 (Guri)", "antiaerea", "buk_m2e", 210, 8, centro=GURI)
    defensa("Roques", "S-125 Pechora-2M (Guri)", "antiaerea", "pechora_2m", 90, 4, centro=GURI)
    tropa("Roques", "Compañía de Custodia de la Represa del Guri (Roques)", 170, "compania", 300, 2, centro=GURI)
    grupos("Tortuga", "Escuadrón F-16", "f16", 14)
    grupos("Tortuga", "Escuadrón K-8W", "ataque_ligero", 8)
    for n, rumbo in enumerate((0, 120, 240)):
        defensa("Tortuga", f"S-300VM Antey-2500 {n + 1}", "antiaerea", "s300vm", rumbo, 12)
    defensa("Tortuga", "Buk-M3", "antiaerea", "buk_m2e", 180, 7)
    for n, rumbo in enumerate((45, 135, 225, 315)):
        defensa("Tortuga", f"S-125 Pechora-2M {n + 1}", "antiaerea", "pechora_2m", rumbo, 5)
    tropa("Tortuga", "Batallón de Defensa de Base (Tortuga)", 650, "batallon", 270, 3)
    grupos("Orchila", "AT-27 Tucano", "ataque_ligero", 4)
    grupos("Orchila", "Shahed-136", "merodeadora", 20)
    defensa("Orchila", "S-300VM Antey-2500", "antiaerea", "s300vm", 0, 10)
    defensa("Orchila", "Buk-M3", "antiaerea", "buk_m2e", 180, 6)
    tropa("Orchila", "Compañía de Defensa de Base (Orchila)", 200, "compania", 90, 3)
    # Infraestructura de Rojo: el Guri y el Bajo Caroní, los puentes de Angostura y del Caroní, energía y refinación
    for clave in ("inf011", "inf010", "inf006", "inf009", "inf015", "inf025", "inf017", "inf016", "inf039", "inf035", "inf029"):
        i = INFRA[clave]
        extra = {"radio_km": 0.8} if i["clase"] == "puente" else {}
        lat, lon = (i["lat"], i["lon"]) if i["clase"] == "puente" else en_tierra(i["lat"], i["lon"], lado="rojo")
        u(i["nombre"], "rojo", i["clase"], lat, lon, **extra)
    return unidades


def objetivos(unidades):
    guri = INFRA["inf011"]["nombre"]
    obj = [
        # ---- Azul: neutralizar el poder aeroespacial de Rojo, introducir tropas y asegurar el Guri sin destruirlo ----
        {"bando": "azul", "tipo": "ocupar", "nombre": "Asegurar el Embalse y la represa del Guri", "puntos": 40,
         "lat": GURI[0], "lon": GURI[1], "radio_km": 12.0, "turnos_requeridos": 3},
        {"bando": "azul", "tipo": "proteger", "nombre": "Capturar el Guri sin destruir la central", "puntos": 20,
         "unidad": guri, "hasta_turno": 12},
        {"bando": "azul", "tipo": "proteger", "nombre": "Mantener operativa la Base Echo", "puntos": 10,
         "unidad": "Base Echo (Puerto Ayacucho)", "hasta_turno": 12},
        # ---- Rojo: contener y eliminar las fuerzas que penetren, defender el Guri sin abandonar la ofensiva ----
        {"bando": "rojo", "tipo": "proteger", "nombre": "Defender la Central Hidroeléctrica del Guri", "puntos": 30,
         "unidad": guri, "hasta_turno": 12},
        {"bando": "rojo", "tipo": "destruir", "nombre": "Destruir la planta refinadora de tierras raras", "puntos": 10,
         "unidad": "Planta refinadora de tierras raras (centro de Azul)"},
    ]
    for x in unidades:
        if x["bando"] == "rojo" and x["clase"] == "base_aerea":
            obj.append({"bando": "azul", "tipo": "neutralizar", "nombre": f"Neutralizar la {x['nombre']}", "puntos": 10,
                        "unidad": x["nombre"], "umbral": 50})
        if x["bando"] == "rojo" and x["clase"] == "antiaerea" and "(Guri)" in x["nombre"]:
            obj.append({"bando": "azul", "tipo": "neutralizar", "nombre": f"Suprimir la defensa del Guri: {x['nombre']}",
                        "puntos": 10, "unidad": x["nombre"], "umbral": 50})
        if x["bando"] == "rojo" and x["clase"] == "hidroelectrica" and x["nombre"] != guri:
            obj.append({"bando": "rojo", "tipo": "proteger", "nombre": f"Proteger {x['nombre']}", "puntos": 5,
                        "unidad": x["nombre"], "hasta_turno": 12})
        if x["bando"] == "azul" and x["clase"] == "base_aerea" and x["nombre"].split(" ")[1] in ("Echo", "Golf", "Oscar", "November"):
            puntos = 20 if "Echo" in x["nombre"] else 15
            obj.append({"bando": "rojo", "tipo": "neutralizar", "nombre": f"Neutralizar la {x['nombre']}", "puntos": puntos,
                        "unidad": x["nombre"], "umbral": 50})
    return obj


# ---------------------------------------------------------------- Problema Militar Operativo de cada bando
SITUACION_GENERAL = (
    "Juegos de Guerra 01-2026. El conflicto entre la República Federal Azul y el País Rojo es una guerra congelada desde "
    "la guerra civil de 1951-1954. El armisticio dividió el territorio por el Paralelo 7, que corta la cuenca del Orinoco; "
    "la frontera es la Zona Desmilitarizada del Orinoco (ZDO), una franja de 4 km. El Embalse del Guri quedó justo al norte "
    "de la línea, bajo control de Rojo, pero sus aguas y líneas de transmisión cruzan la ZDO hacia Azul. Azul compra a Rojo "
    "el 75 % de su electricidad y explota tierras raras en el límite de la ZDO; Rojo denuncia que los sedimentos obstruyen "
    "las turbinas del Guri. En mayo de 2026 Rojo declaró el fin del armisticio. El Guri es la principal reserva de agua dulce "
    "de la región y el núcleo hidroeléctrico de ambos países: Rojo lo ha convertido en su centro de gravedad defensivo, con "
    "defensa aérea rusa en capas."
)

PMO = {
    "azul": {
        "situacion_general": SITUACION_GENERAL + (
            " Situación Azul (Operación Guri, Capital DF, 01 21:00 JUN26): Rojo amenaza con cortar el suministro eléctrico; "
            "en abril se detectó un sobrevuelo de un dron de Rojo en la frontera; el Departamento de Inteligencia reporta "
            "sabotajes en las plantas refinadoras de tierras raras del centro del país, movimientos inusuales de unidades "
            "terrestres de Rojo en la frontera y la captura de individuos cerca de instalaciones militares. El Presidente "
            "decretó el Estado de Alerta y Movilización Nacional con 7 000 combatientes aerotransportados, especialistas en "
            "asalto aéreo y aseguramiento de áreas estratégicas."),
        "fuerzas_enemigas": (
            "Rojo ha fortificado el Guri con defensa aérea de fabricación rusa en capas (sistemas S-300VM Antey-2500, Buk y "
            "Pechora), aviación de combate (Su-30MK2, F-16 y aviones de ataque K-8W y AT-27), medios aéreos de inteligencia "
            "avanzados (alerta temprana y ELINT) y drones kamikaze. Se estima su aviación de combate en unas 60 aeronaves, "
            "en bases del norte y del este del país, y la defensa aérea concentrada en las bases y alrededor de la represa."),
        "fuerzas_propias": (
            "Fuerza de Tarea Aérea con seis bases al sur del Paralelo 7 (Echo, Golf, Hotel, Kilo, Oscar y November): más de "
            "140 aeronaves tripuladas (Kfir, F-16 Block 70, A-37, OV-10, A-29, UH-60, CH-47, Bell 212, tanqueros y P-3), "
            "20 drones (MQ-1 y MQ-9), defensa antiaérea de base (Hawk, NASAMS y M-SHORAD) y 6 750 combatientes de asalto "
            "aéreo distribuidos en las bases."),
        "mision_superior": (
            "Neutralizar el poder aeroespacial del país Rojo a fin de introducir tropas en el área del embalse del Guri, "
            "asegurando así el dominio total. (Situación Azul, punto 2.)"),
        "idea_general": (
            "Plan Militar de Campaña Timotocuica (Base Aérea Central, 01 09:00 JUN2026): a partir del día D a la hora H, "
            "operaciones ofensivas para neutralizar la defensa aérea del enemigo, introducir tropas en el área por delimitar, "
            "lograr el control de la zona en reclamación y evitar el ingreso de fuerzas de Rojo. El COC se reserva el empleo "
            "del componente aéreo, del sistema de defensa aérea y de los medios estratégicos; el componente naval pasa bajo su "
            "control operacional. Fases previstas: I, superioridad aérea y supresión de la defensa aérea (turnos 1 a 4); "
            "II, asalto aéreo al Guri (5 a 8); III, consolidación (9 a 12)."),
        "mision": {
            "tarea": "Neutralizar", "que": "el poder aeroespacial y la defensa aérea del País Rojo",
            "donde": "en el área del Embalse del Guri y las bases aéreas enemigas",
            "cuando": "a partir del día D a la hora H",
            "proposito": "introducir tropas de asalto aéreo y asegurar el Guri sin destruir la infraestructura hidroeléctrica"},
        "medios": (
            "Echo: 3 000 combatientes; 24 Kfir, 48 F-16 Block 70, 12 A-37 Dragonfly, 14 C-130J, 2 Boeing 737 tanqueros, "
            "2 P-3 Orion, 2 MIM-23 Hawk. JP-1 2 659 000 de 2 700 000 l. GBU-12 500, SPICE 2000 300, Python 4 600, "
            "AIM-120D 2 000, AGM-158 JASSM 1 000, cartuchos 7,62 mm 5 000, MK 82 1 000. Criogénicos O2/N2 12 000/7 000 psi.\n"
            "Golf: 1 200 combatientes; 10 UH-60 Black Hawk, 12 OV-10 Bronco, 1 NASAMS. JP-1 640 000 de 700 000 l. MK 82 300, "
            "MK 81 200, 7,62 mm 7 000. O2/N2 2 000/700 psi.\n"
            "Hotel: 1 450 combatientes; 12 A-29 Super Tucano, 2 C-208 Caravan, 1 MIM-23 Hawk, 1 NASAMS. JP-1 140 000 de "
            "900 000 l; AVGAS 1 000 l. MK 81 200, 7,62 mm 7 000. O2/N2 1 000/500 psi.\n"
            "Kilo: 300 combatientes; 5 MQ-1 Predator, 1 C-206. JP-1 180 000 de 300 000 l; AVGAS 200 l. MK 81 2 000. "
            "O2/N2 1 000/500 psi.\n"
            "Oscar: 650 combatientes; 10 UH-60 Black Hawk, 1 Bell 212, 1 C-206, 1 NASAMS. JP-1 110 000 de 500 000 l; "
            "AVGAS 100 l. AGM-114 400, FIM-92 Stinger 100, 7,62 mm 17 000. O2/N2 1 000/1 500 psi.\n"
            "November: 150 combatientes; 5 MQ-1 Predator, 10 MQ-9 Reaper, 2 Bell 212, 5 CH-47 Chinook, 2 M-SHORAD. JP-1 "
            "140 000 de 900 000 l; AVGAS 200 l. MK 81 2 000, 7,62 mm 7 000. O2/N2 2 000/2 500 psi."),
        "area_operaciones": (
            "Cuenca del Orinoco y del Caroní entre el Paralelo 7 y el Bajo Caroní: Embalse del Guri, represas de Tocoma, "
            "Caruachi y Macagua, Angostura (Ciudad Bolívar) y Puerto Ordaz, y las bases aéreas de Rojo en el norte y el este."),
        "limitaciones": (
            "Asegurar la infraestructura hidroeléctrica del Guri sin destruirla. Respetar la ZDO hasta la hora H. "
            "El combustible es crítico en Hotel, Oscar y November (menos del 25 % de la capacidad). En el simulador los "
            "C-130J, C-208 y C-206 no están representados: el asalto aéreo se hace con los helicópteros (UH-60, CH-47 y "
            "Bell 212), que llevan una unidad cada grupo."),
        "instrucciones": (
            "Las tropas embarcan en un helicóptero propio a menos de 3 km (orden Embarcar) y desembarcan con la orden "
            "Desembarcar sobre el área del Guri. El objetivo se cumple con tropas propias en el área durante 3 turnos y sin "
            "tropas enemigas en ella."),
    },
    "rojo": {
        "situacion_general": SITUACION_GENERAL + (
            " Situación Rojo (Escudo Protector Guri, Angostura, 01 23:00 JUN26): por más de una década Azul ha realizado "
            "acciones injerencistas; su explotación minera afecta la cuenca y la generación hidroeléctrica. El COSENA reporta "
            "una amplia posibilidad de ataque de Azul. La máxima autoridad ordenó fortificar toda la infraestructura del Guri y "
            "preparar a la nación contra cualquier ataque."),
        "fuerzas_enemigas": (
            "Azul tiene mayor número de aeronaves tácticas y medios aerotransportados: cazas Kfir y F-16, aviones de ataque "
            "ligero, helicópteros de transporte (UH-60 y CH-47), drones armados MQ-1 y MQ-9, tanqueros y del orden de 7 000 "
            "combatientes de asalto aéreo. Se estima que opera desde bases al sur del Paralelo 7 y que redespliega unidades "
            "aéreas del occidente hacia el centro del país."),
        "fuerzas_propias": (
            "Cinco bases (Aves, Patos, Roques, Tortuga y Orchila) con unas 57 aeronaves tripuladas (Su-30MK2, F-16, K-8W, "
            "AT-27, AS532 Cougar, Y-8W de alerta temprana y un Metro Merlin ELINT), 20 drones kamikaze Shahed-136 y defensa "
            "aérea en capas (9 S-300VM Antey-2500, 5 Buk-M3 y 6 S-125 Pechora-2M). Guarniciones de base: 2 520 combatientes."),
        "mision_superior": (
            "Ejecutar operaciones militares en todo el territorio nacional, a fin de neutralizar el posible carácter de las "
            "acciones del enemigo. (Situación Rojo, punto 2.)"),
        "idea_general": (
            "Plan Militar de Campaña Caribe (Base Aérea Central, 01 09:00 JUN2026): a partir del día D a la hora H, el COC "
            "ejecutará operaciones militares para contener y eliminar las fuerzas enemigas que intenten penetrar el territorio "
            "nacional, sin abandonar la ofensiva, y operaciones de orden interno. Coordinación por las REDI Oriental y "
            "Guayana; el componente naval pasa a la REDI Marítima Insular. El COC se reserva el componente aéreo y el sistema "
            "de defensa aérea."),
        "mision": {
            "tarea": "Defender", "que": "la represa y el Embalse del Guri y el sistema hidroeléctrico del Bajo Caroní",
            "donde": "en el territorio nacional al norte del Paralelo 7",
            "cuando": "a partir del día D a la hora H",
            "proposito": "contener y eliminar a las fuerzas de Azul que intenten penetrar, sin abandonar la ofensiva"},
        "medios": (
            "Aves: 1 500 combatientes; 14 Su-30MK2, 10 K-8W, 2 Y-8W, 1 Metro Merlin ELINT, 3 S-300VM Antey-2500, 1 Buk-M3. "
            "JP-1 1 600 000 de 1 700 000 l. KAB-500 1 000, OFAB-250/270 700, RVV-AE 300, R-27ET 200, R-27ER 100, R-73 250, "
            "7,62 mm 5 000, 30 mm 2 000, MK 82 1 400. O2/N2 2 000/2 000 psi.\n"
            "Patos: 4 AS532 Cougar, 2 Do 228 Dornier, 1 S-300VM, 1 Buk-M3, 1 S-125 Pechora-2M. JP-1 140 000 de 300 000 l. "
            "Cohetes FZ90 HE 420, 7,62 mm 7 000. O2/N2 500/400 psi.\n"
            "Roques: 170 combatientes; 1 S-300VM, 1 Buk-M3, 1 S-125 Pechora-2M (desplegados en la represa del Guri). "
            "JP-1 190 000 de 200 000 l. O2/N2 200/200 psi.\n"
            "Tortuga: 650 combatientes; 14 F-16, 8 K-8W, 2 Y-8, 2 C-550 Citation, 3 S-300VM, 1 Buk-M3, 4 S-125 Pechora-2M. "
            "JP-1 590 000 de 700 000 l; AVGAS 600 l. MK 81 200, MK 82 300, 20 mm 4 000. O2/N2 600/500 psi.\n"
            "Orchila: 200 combatientes; 4 AT-27 Tucano, 1 C-550 Citation, 20 drones kamikaze Shahed-136, 1 S-300VM, "
            "1 Buk-M3. JP-1 380 000 de 400 000 l. MK 81 1 000, cohetes FZ90 HE 420. O2/N2 1 000/500 psi."),
        "area_operaciones": (
            "Territorio nacional al norte del Paralelo 7, con prioridad en la REDI Guayana (Guri, Bajo Caroní, Angostura y "
            "Puerto Ordaz) y la REDI Oriental (Barcelona, Maturín, San Tomé)."),
        "limitaciones": (
            "No cruzar la ZDO antes de la hora H. Patos tiene menos de la mitad de su combustible. En el simulador los Y-8 de "
            "transporte, los Do 228 y los C-550 no están representados."),
        "instrucciones": (
            "La defensa aérea de Roques está desplegada alrededor de la represa del Guri. Los Shahed-136 tienen poca "
            "autonomía en el simulador (300 km): lánzelos desde Orchila (San Tomé) contra blancos al alcance."),
    },
}


def plantilla():
    unidades = armar()
    return {
        "id": "guri_2026",
        "nombre": "Juegos de Guerra 01-2026: Operación Guri",
        "descripcion": (
            "Ejercicio de los Juegos de Guerra 01-2026 sobre el mapa de Venezuela, con dos países ficticios. La República "
            "Federal Azul (sur del Paralelo 7) busca neutralizar el poder aeroespacial del País Rojo para introducir tropas "
            "de asalto aéreo y asegurar el Embalse del Guri sin destruirlo; el País Rojo (norte) lo defiende con defensa "
            "aérea rusa en capas. Fuerzas, combustible y armamento según la Situación de cada bando (junio de 2026); los "
            "planes de campaña Timotocuica y Caribe están en el Problema Militar de cada bando (pestaña TIEM). La ZDO se "
            "dibuja en 7° N. Supuestos: las bases con nombre clave se ubican en aeródromos reales (Azul: Echo Puerto "
            "Ayacucho, Golf Canaima, Hotel Santa Elena, Kilo Puerto Páez, Oscar La Paragua, November Kavanayén; Rojo: Aves "
            "Barcelona, Patos Maturín, Roques Puerto Ordaz con su defensa en el Guri, Tortuga Angostura, Orchila San Tomé); "
            "el transporte de ala fija no está representado. Requiere backend/data/ajustes_catalogo.json con 100 plazas "
            "por base y topes de 160 aeronaves y 40 drones por bando."
        ),
        "clima": "despejado", "hora_inicio_min": 300, "nacion_azul": "valdoria", "nacion_rojo": "ostrania",
        "ia_azul": False, "ia_rojo": False, "dia_noche": True, "con_estado": True,
        "conduce_azul": "alumnos", "conduce_rojo": "alumnos",
        "fecha_inicio": "2026-06-02", "turno_h": 1, "turno_final": 12,
        "fases": [{"nombre": "Superioridad aérea", "desde": 1, "hasta": 4},
                  {"nombre": "Asalto aéreo al Guri", "desde": 5, "hasta": 8},
                  {"nombre": "Consolidación", "desde": 9, "hasta": 12}],
        "pmo": PMO, "unidades": unidades, "objetivos": objetivos(unidades),
    }


def escribir_ajustes():
    """Plazas por base y topes por bando a la medida de los documentos (Echo tiene 88 aeronaves estacionadas)."""
    actual = json.loads(AJUSTES.read_text(encoding="utf-8")) if AJUSTES.exists() else {}
    actual.setdefault("_comentario", "Ajustes del instructor (ver ajustes_catalogo.ejemplo.json). Los de base_aerea y los "
                      "topes son los que pide el ejercicio Operación Guri (tools/crear_ejercicio_guri.py).")
    actual.setdefault("clases", {}).setdefault("base_aerea", {})["plazas_aeronaves"] = 100
    actual.setdefault("topes", {}).update({"MAX_AERONAVES_BANDO": 160, "MAX_DRONES_BANDO": 40})
    AJUSTES.write_text(json.dumps(actual, ensure_ascii=False, indent=2), encoding="utf-8")


def comprobar(p):
    estacionadas = {}
    for x in p["unidades"]:
        if x["clase"] != "puente" and T.clase(x["lat"], x["lon"]) == "agua":
            raise SystemExit(f"{x['nombre']} cae en el agua")
        lado = x["lat"] > LINEA_ZDO
        if x["clase"] not in ("puente",) and lado != (x["bando"] == "rojo"):
            raise SystemExit(f"{x['nombre']} queda del lado equivocado de la ZDO ({x['lat']:.3f})")
        if x.get("en_tierra"):
            estacionadas[x["base"]] = estacionadas.get(x["base"], 0) + x["aeronaves"]
    if max(estacionadas.values()) > 100:
        raise SystemExit("Una base supera las 100 plazas")
    return estacionadas


def crear_escenario():
    """Crea el escenario desde la plantilla y dibuja la ZDO (línea de fase visible para todos)."""
    from app.db import SessionLocal, init_db
    from app.engine import plantillas
    from app.models.grafico import Grafico

    init_db()
    plantillas.PLANTILLAS.pop("guri_2026", None)
    plantillas._cargar_sistema()
    with SessionLocal() as db:
        esc = plantillas.crear_desde_plantilla(db, "guri_2026")
        linea = {"type": "LineString", "coordinates": [[lon, LINEA_ZDO] for lon in (-70.5, -67.5, -64.5, -61.0)]}
        db.add(Grafico(escenario_id=esc.id, bando="todos", tipo="linea_fase", etiqueta="ZDO · Paralelo 7",
                       geojson=json.dumps(linea), autor_nombre="instructor", turno=1))
        db.commit()
        print(f"Escenario {esc.id} creado: {esc.nombre}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ajustes", action="store_true", help="escribir backend/data/ajustes_catalogo.json")
    ap.add_argument("--crear", action="store_true", help="crear el escenario en la base de datos local")
    args = ap.parse_args()
    p = plantilla()
    estacionadas = comprobar(p)
    SALIDA.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    aereas = [x for x in p["unidades"] if catalogo.CLASES[x["clase"]].tipo == "aerea"]
    for b in ("azul", "rojo"):
        g = [x for x in aereas if x["bando"] == b]
        print(f"{b}: {len(g)} grupos aéreos, {sum(x['aeronaves'] for x in g)} aeronaves; "
              f"{sum(1 for x in p['unidades'] if x['bando'] == b and x['clase'] in ('antiaerea', 'antiaerea_portatil'))} "
              f"sistemas antiaéreos; {sum(x.get('personal') or 0 for x in p['unidades'] if x['bando'] == b)} combatientes")
    for base, n in estacionadas.items():
        print(f"  {base}: {n} aeronaves")
    print(f"{len(p['unidades'])} unidades, {len(p['objetivos'])} objetivos -> {SALIDA}")
    if args.ajustes:
        escribir_ajustes()
        print(f"Ajustes escritos: {AJUSTES}")
    if args.crear:
        crear_escenario()


if __name__ == "__main__":
    main()
