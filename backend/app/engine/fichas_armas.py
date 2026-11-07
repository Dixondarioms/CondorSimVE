"""Fichas de las armas del Cóndor: misiles, bombas, cohetes, cañones y torpedos, con su foto real.

Cada ficha trae datos publicos de fuentes abiertas (nombre, tipo, pais y fabricante, guia, alcance, velocidad, ojiva o
calibre, peso y una descripcion breve) y la foto de Wikimedia Commons que baja tools/fotos/fotos_referencia.py
(seccion "armas" de frontend/static/fotos/referencias.json). Son de consulta: los valores de juego (alcance, Pk,
cantidades) siguen en engine/ota.py, engine/armas.py, engine/defensa_aerea.py y engine/misiles.py.

Correspondencias:
  - codigos de armamento de la OTA (aeronaves): DE_OTA; el cañon, los cohetes y las ametralladoras dependen del modelo
    (OTA_POR_MODELO y el origen del modelo);
  - armas de los sistemas antiaereos (defensa_aerea.SISTEMAS): DE_DA; sistemas historicos sin tabla de armas:
    POR_MODELO;
  - misiles de crucero y antibuque (modelos de la clase misil_crucero): DE_MISIL; lo que lanza cada buque o bateria:
    misiles.MISIL_DEL_LANZADOR (o el Tomahawk, el de siempre);
  - torpedos y misiles balisticos: POR_CLASE.
Una ficha puede usar la foto de un modelo o una clase del catalogo (foto_de), asi las armas repetidas comparten foto.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from app.engine import catalogo

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Ficha:
    id: str
    nombre: str
    tipo: str
    pais: str
    fabricante: str
    guia: str
    alcance: str
    velocidad: str
    ojiva: str  # ojiva o calibre
    peso: str
    descripcion: str
    foto_de: tuple[str, str] | None = None  # ("modelos"|"clases"|"armas", id): usa esa foto


def _f(id_, nombre, tipo, pais, fabricante, guia, alcance, velocidad, ojiva, peso, descripcion, foto_de=None):
    return Ficha(id_, nombre, tipo, pais, fabricante, guia, alcance, velocidad, ojiva, peso, descripcion, foto_de)


AA = "Misil aire-aire"
AS = "Misil aire-superficie"
AR = "Misil antirradiación"
AB = "Misil antibuque"
BG = "Bomba guiada"
BL = "Bomba de caída libre"
SAM = "Misil tierra-aire"
CAN = "Cañón"

_FICHAS = [
    # ------------------------------------------------------------------------------------------- aire-aire
    _f("r77", "R-77 (RVV-AE)", AA + " de alcance medio", "Rusia", "Vympel (KTRV)",
       "Inercial con enlace de datos y radar activo al final", "Hasta 80 km (exportación)", "Mach 4", "22 kg, varillas",
       "175 kg", "Misil «dispara y olvida» con aletas de rejilla en la cola; arma principal de los MiG-29SMT y Su-35."),
    _f("r27er", "R-27ER1", AA + " de alcance medio", "Unión Soviética / Rusia", "Vympel",
       "Radar semiactivo (el radar del avión ilumina el blanco)", "Hasta 130 km de frente (60 a 70 km en combate)",
       "Mach 4,5", "39 kg, varillas", "350 kg", "Versión de motor grande del R-27; el avión debe seguir iluminando el "
       "blanco hasta el impacto."),
    _f("r27et", "R-27ET1", AA + " de alcance medio", "Unión Soviética / Rusia", "Vympel", "Infrarrojo",
       "Hasta 120 km de frente", "Mach 4,5", "39 kg, varillas", "343 kg",
       "Gemelo infrarrojo del R-27ER: no avisa al blanco con su radar y se suele disparar en pareja con él."),
    _f("r73", "R-73E", AA + " de corto alcance", "Unión Soviética / Rusia", "Vympel",
       "Infrarrojo de todo aspecto, con empuje vectorial", "Hasta 30 km", "Mach 2,5", "7,4 kg, varillas", "105 kg",
       "Misil de combate cercano muy maniobrable; se apunta con el casco del piloto."),
    _f("python4", "Python 4", AA + " de corto alcance", "Israel", "Rafael", "Infrarrojo de todo aspecto",
       "Hasta 15 km", "Mach 3,5", "11 kg", "120 kg", "Misil de combate cercano que se puede lanzar casi de costado al "
       "blanco, con mira en el casco."),
    _f("aim9l", "AIM-9L Sidewinder", AA + " de corto alcance", "Estados Unidos", "Raytheon / Ford Aerospace",
       "Infrarrojo de todo aspecto", "Hasta 18 km", "Mach 2,5", "9,4 kg, fragmentación", "86 kg",
       "Primer Sidewinder que podía tirar de frente; decisivo en las Malvinas (1982)."),
    _f("aim120", "AIM-120 AMRAAM", AA + " de alcance medio", "Estados Unidos", "Raytheon",
       "Inercial con enlace de datos y radar activo al final", "Más de 100 km (versiones C-7 y D); 25 a 40 km "
       "lanzado desde tierra (NASAMS)", "Mach 4", "18 kg, fragmentación", "152 kg",
       "El misil aire-aire más difundido de Occidente; la batería NASAMS lo lanza desde tierra."),
    _f("aim9x", "AIM-9X Sidewinder", AA + " de corto alcance", "Estados Unidos", "Raytheon",
       "Infrarrojo por imagen, con empuje vectorial", "Hasta 35 km", "Mach 2,5", "9,4 kg, fragmentación", "85 kg",
       "Sidewinder moderno: se apunta con el casco y puede atacar blancos detrás del avión; también lo usa el NASAMS."),
    _f("aim7", "AIM-7 Sparrow", AA + " de alcance medio", "Estados Unidos", "Raytheon", "Radar semiactivo",
       "Hasta 70 km (AIM-7M)", "Mach 4", "40 kg, varillas", "231 kg",
       "Misil de alcance medio de la Guerra Fría; en la Tormenta del Desierto (1991) logró la mayoría de los derribos."),
    _f("aim54", "AIM-54 Phoenix", AA + " de largo alcance", "Estados Unidos", "Hughes",
       "Inercial, radar semiactivo y radar activo al final", "Hasta 190 km", "Mach 5", "60 kg", "453 kg",
       "Misil del F-14 Tomcat para defender la flota de los bombarderos; el F-14 podía guiar seis a la vez."),
    _f("shafrir2", "Shafrir 2", AA + " de corto alcance", "Israel", "Rafael", "Infrarrojo (por la cola)",
       "Hasta 5 km", "Mach 2,5", "11 kg", "93 kg", "Misil israelí de primera generación; lo usaron los Dagger "
       "argentinos en 1982."),
    _f("r550", "R550 Magic", AA + " de corto alcance", "Francia", "Matra", "Infrarrojo", "Hasta 10 km", "Mach 2,7",
       "12,5 kg", "89 kg", "Misil de combate cercano de los Mirage; muy ágil para su época."),
    _f("super530", "Super 530F", AA + " de alcance medio", "Francia", "Matra", "Radar semiactivo", "Hasta 35 km",
       "Mach 4,6", "30 kg", "245 kg", "Misil de alcance medio del Mirage F1 y del Mirage 2000 (versión D)."),
    _f("r23", "R-23 (AA-7 Apex)", AA + " de alcance medio", "Unión Soviética", "Vympel",
       "Radar semiactivo (R-23R) o infrarrojo (R-23T)", "Hasta 35 km", "Mach 3", "25 kg", "223 kg",
       "Misil del MiG-23 en los años setenta y ochenta."),
    _f("r40", "R-40 (AA-6 Acrid)", AA + " de largo alcance", "Unión Soviética", "Molniya (Bisnovat)",
       "Radar semiactivo (R-40R) o infrarrojo (R-40T)", "50 a 80 km", "Mach 4,5", "38 kg", "475 kg",
       "Misil grande del interceptor MiG-25, pensado contra bombarderos."),
    _f("r60", "R-60 (AA-8 Aphid)", AA + " de corto alcance", "Unión Soviética", "Molniya / Vympel", "Infrarrojo",
       "Hasta 8 km", "Mach 2,7", "3 kg, varillas", "44 kg", "Uno de los misiles aire-aire más livianos; lo llevan el "
       "MiG-21, el MiG-23 y el Su-25 para defenderse."),
    _f("mica", "MICA", AA + " de alcance medio", "Francia", "MBDA",
       "Infrarrojo por imagen (MICA IR) o radar activo (MICA EM)", "60 a 80 km", "Mach 4", "12 kg", "112 kg",
       "Misil del Rafale y del Mirage 2000-5; el mismo cuerpo sirve de corto y de medio alcance."),
    _f("meteor", "Meteor", AA + " de largo alcance", "Unión Europea", "MBDA",
       "Inercial con enlace de datos y radar activo; motor de estatorreactor", "Más de 100 km (zona sin escape de "
       "unos 60 km)", "Más de Mach 4", "Fragmentación", "190 kg", "Su estatorreactor mantiene el empuje hasta el "
       "final, por eso el blanco casi no puede escapar; lo usan Rafale, Gripen y Typhoon."),
    _f("iris_t", "IRIS-T", AA + " de corto alcance", "Alemania", "Diehl Defence",
       "Infrarrojo por imagen, con empuje vectorial", "Hasta 25 km", "Mach 3", "11,4 kg", "87 kg",
       "Misil europeo de combate cercano; puede derribar incluso misiles que vienen hacia el avión."),
    _f("pl15", "PL-15", AA + " de largo alcance", "China", "CAAA (Luoyang)",
       "Inercial con enlace de datos y radar activo", "Más de 145 km (PL-15E de exportación)", "Más de Mach 4",
       "Fragmentación", "Unos 210 kg", "Misil chino de largo alcance con motor de doble pulso; arma de los J-10C, "
       "J-15 y JF-17 Block III."),
    _f("pl10", "PL-10", AA + " de corto alcance", "China", "CAAA (Luoyang)",
       "Infrarrojo por imagen, con empuje vectorial", "Hasta 20 km", "Mach 3", "Fragmentación", "89 kg",
       "Misil chino de combate cercano, comparable al AIM-9X."),
    _f("pl12", "PL-12 (SD-10)", AA + " de alcance medio", "China", "CAAA (Luoyang)",
       "Inercial con enlace de datos y radar activo", "70 a 100 km", "Mach 4", "20 kg", "199 kg",
       "Primer misil chino «dispara y olvida»; el SD-10 es la versión que exporta (JF-17)."),
    # ----------------------------------------------------------------------------------- aire-superficie
    _f("kh29l", "Kh-29L", AS, "Unión Soviética / Rusia", "Molniya / Vympel", "Láser semiactivo", "Hasta 10 km",
       "Unos 1 400 km/h", "320 kg, penetrante", "660 kg", "Misil pesado contra búnkeres, puentes y buques; el blanco "
       "se marca con un láser."),
    _f("kh29te", "Kh-29TE", AS, "Unión Soviética / Rusia", "Vympel", "Televisión", "Hasta 30 km",
       "Unos 1 400 km/h", "320 kg, penetrante", "690 kg", "Versión del Kh-29 guiada por la imagen de una cámara: el "
       "piloto fija el blanco en su pantalla y se va.", ("armas", "kh29l")),
    _f("kh31a", "Kh-31A", AB, "Rusia", "Zvezda (KTRV)", "Inercial y radar activo; estatorreactor",
       "Hasta 50 km (exportación)", "Mach 3,5", "94 kg", "610 kg", "Misil antibuque supersónico de alcance corto."),
    _f("kh31p", "Kh-31P", AR, "Rusia", "Zvezda (KTRV)", "Pasiva: sigue la emisión de los radares; estatorreactor",
       "Hasta 110 km", "Mach 3,5", "87 kg", "600 kg", "Misil para destruir radares antiaéreos (SEAD).",
       ("armas", "kh31a")),
    _f("kh59me", "Kh-59ME Ovod", AS + " de largo alcance", "Rusia", "Raduga",
       "Inercial y televisión con enlace de datos", "Hasta 115 km", "Unos 1 000 km/h", "320 kg", "930 kg",
       "Misil de crucero del Su-30MK2 y del Su-35; el operador lo guía por la imagen que envía."),
    _f("agm88", "AGM-88 HARM", AR, "Estados Unidos", "Raytheon",
       "Pasiva (sigue la emisión de los radares) y GPS en la versión E", "Hasta 150 km", "Mach 2+",
       "66 kg, fragmentación", "355 kg", "Misil antirradiación de Occidente: obliga a los radares a callar o los "
       "destruye."),
    _f("agm154", "AGM-154 JSOW", "Bomba planeadora guiada", "Estados Unidos", "Raytheon",
       "Inercial y GPS (la versión C, con infrarrojo al final)", "22 km a baja cota, hasta 130 km desde gran altura",
       "Planea sin motor", "Submuniciones (A) o 227 kg (C)", "483 kg",
       "Arma «fuera del alcance» de la antiaérea: se suelta lejos y planea hasta el blanco."),
    _f("agm114", "AGM-114 Hellfire", AS + " antitanque", "Estados Unidos", "Lockheed Martin",
       "Láser semiactivo (la versión L, radar de ondas milimétricas)", "8 a 11 km", "Mach 1,3",
       "9 kg, carga hueca en tándem o fragmentación", "45 kg",
       "Misil antitanque de helicópteros y drones (AH-64, MQ-9); también contra vehículos y edificios."),
    _f("harpoon", "Harpoon (AGM-84 / RGM-84)", AB, "Estados Unidos", "Boeing",
       "Inercial y radar activo al final; vuela rozando el mar", "Más de 120 km", "Mach 0,85 (unos 860 km/h)",
       "221 kg", "519 kg (lanzado desde avión); 691 kg desde buque", "El misil antibuque más difundido de Occidente: "
       "lo lanzan aviones, buques, submarinos y baterías costeras.", ("modelos", "harpoon")),
    _f("exocet", "Exocet (AM39 / MM40)", AB, "Francia", "MBDA (Aérospatiale)",
       "Inercial y radar activo al final; vuela rozando el mar", "70 km (AM39, desde avión); hasta 180 km (MM40 "
       "Block 3, desde buque)", "Mach 0,93", "165 kg", "670 kg (AM39)", "Famoso por hundir el HMS Sheffield en 1982; "
       "lo usan fragatas, submarinos (SM39) y aviones.", ("modelos", "exocet")),
    _f("kh35", "Kh-35 (Uran)", AB, "Rusia", "Zvezda (KTRV)", "Inercial y radar activo; vuela rozando el mar",
       "Hasta 130 km (Kh-35E)", "Mach 0,8", "145 kg", "520 kg (desde avión); 610 kg desde buque o tierra",
       "El «Harpoonski»: misil antibuque de aviones, buques y de la batería costera Bal.", ("modelos", "kh35")),
    _f("mk54", "Mk 54 MAKO", "Torpedo ligero", "Estados Unidos", "Raytheon", "Sonar activo y pasivo",
       "Unos 9 km", "Más de 40 nudos", "44 kg", "276 kg (324 mm)",
       "Torpedo antisubmarino de aviones de patrulla, helicópteros y buques."),
    _f("kab500kr", "KAB-500Kr", BG, "Unión Soviética / Rusia", "GNPP Región",
       "Televisión (dispara y olvida por correlación de imagen)", "9 a 17 km según la altura de lanzamiento",
       "Caída libre", "380 kg", "520 kg", "Bomba guiada por cámara: el piloto fija el blanco y la bomba lo sigue sola."),
    _f("kab500od", "KAB-500OD", BG, "Rusia", "GNPP Región", "Televisión (como la KAB-500Kr)",
       "9 a 17 km según la altura de lanzamiento", "Caída libre", "250 kg, aire-combustible (termobárica)", "520 kg",
       "Versión de la KAB-500Kr con explosivo de aire-combustible, contra tropas y refugios livianos.",
       ("armas", "kab500kr")),
    _f("kab1500kr", "KAB-1500Kr", BG, "Unión Soviética / Rusia", "GNPP Región", "Televisión",
       "9 a 20 km según la altura de lanzamiento", "Caída libre", "1 180 kg, penetrante", "1 525 kg",
       "La bomba guiada pesada rusa, contra búnkeres y obras reforzadas."),
    _f("mk82", "Mk 82", BL, "Estados Unidos", "Varios (General Dynamics y otros)", "Ninguna", "Se suelta sobre el "
       "blanco", "Caída libre", "89 kg de Tritonal", "227 kg (500 lb)",
       "La bomba de propósito general más usada del mundo; con un kit láser es la GBU-12."),
    _f("mk84", "Mk 84", BL, "Estados Unidos", "Varios (General Dynamics y otros)", "Ninguna", "Se suelta sobre el "
       "blanco", "Caída libre", "429 kg de Tritonal", "907 kg (2 000 lb)",
       "Bomba pesada de propósito general; con kit láser es la GBU-10 y con GPS, la GBU-31 JDAM."),
    _f("gbu10", "GBU-10 Paveway II", BG, "Estados Unidos", "Raytheon (Texas Instruments)", "Láser semiactivo",
       "Hasta unos 15 km", "Caída libre", "Mk 84 (429 kg de explosivo)", "934 kg",
       "Bomba Mk 84 con kit de guía láser; usada desde Vietnam hasta hoy."),
    _f("gbu12", "GBU-12 Paveway II", BG, "Estados Unidos", "Raytheon (Texas Instruments)", "Láser semiactivo",
       "Hasta unos 15 km", "Caída libre", "Mk 82 (89 kg de explosivo)", "230 kg",
       "La bomba guiada por láser más usada; la llevan cazas, aviones de ataque y drones."),
    _f("natak", "NATAK", BL, "—", "—", "Ninguna (según el simulador)", "Se suelta sobre el blanco", "Caída libre",
       "—", "—", "Bomba del avión de ataque ligero K-8W según la OTA del simulador. No se encontraron datos públicos "
       "verificados ni foto libre de esta bomba."),
    _f("gbu31", "GBU-31 JDAM", BG, "Estados Unidos", "Boeing", "Inercial y GPS (todo tiempo)", "Hasta 28 km",
       "Caída libre", "Mk 84 o BLU-109 penetrante", "934 kg",
       "Kit de cola con GPS que convierte una bomba común en guiada; no le importan las nubes ni el humo."),
    _f("gbu27", "GBU-27 Paveway III", BG, "Estados Unidos", "Raytheon", "Láser semiactivo",
       "Hasta unos 15 km", "Caída libre", "BLU-109 penetrante (240 kg de explosivo)", "981 kg",
       "Bomba penetrante del F-117; en 1991 destruyó búnkeres de mando en Bagdad."),
    _f("agm45", "AGM-45 Shrike", AR, "Estados Unidos", "Texas Instruments / Sperry Rand",
       "Pasiva (sigue la emisión de un radar)", "Hasta 40 km", "Mach 2", "66 kg", "177 kg",
       "Primer misil antirradiación de Estados Unidos (Vietnam); lo reemplazó el HARM."),
    _f("scalp", "Storm Shadow / SCALP EG", "Misil de crucero aire-superficie", "Reino Unido / Francia", "MBDA",
       "Inercial, GPS, perfil del terreno e infrarrojo por imagen al final", "Más de 250 km (exportación)",
       "Mach 0,8", "450 kg, en tándem (BROACH)", "1 300 kg",
       "Misil furtivo de largo alcance contra blancos reforzados; lo llevan el Rafale y el Typhoon."),
    _f("c802", "C-802 (YJ-82 / YJ-83)", AB, "China", "CASIC", "Inercial y radar activo; vuela rozando el mar",
       "120 km (C-802A: 180 km)", "Mach 0,9", "165 kg", "715 kg",
       "Misil antibuque chino de buques, aviones y baterías costeras; muy exportado."),
    _f("fab500", "FAB-500 M-62", BL, "Unión Soviética / Rusia", "Varios (fábricas estatales)", "Ninguna",
       "Se suelta sobre el blanco", "Caída libre", "Unos 200 kg de explosivo", "500 kg",
       "La bomba rusa de propósito general más común (familia FAB de 250 y 500 kg)."),
    _f("agm65", "AGM-65 Maverick", AS, "Estados Unidos", "Raytheon (Hughes)",
       "Televisión, infrarrojo o láser según la versión", "22 a 27 km", "Mach 1", "57 kg (carga hueca) o 136 kg",
       "210 a 300 kg", "Misil contra tanques, vehículos y buques chicos; el arma clásica del A-10."),
    _f("kh22", "Kh-22 (AS-4 Kitchen)", AB + " de largo alcance", "Unión Soviética", "Raduga",
       "Inercial y radar activo o pasivo", "400 a 600 km", "Mach 4,6", "1 000 kg", "5 900 kg",
       "Misil enorme de los bombarderos Tu-22M3 contra portaaviones."),
    _f("tow", "BGM-71 TOW", "Misil antitanque", "Estados Unidos", "Raytheon (Hughes)",
       "Por cable, semiautomática (el tirador mantiene la mira en el blanco)", "3,75 a 4,5 km", "Unos 280 m/s",
       "5,9 kg, carga hueca en tándem (TOW-2A)", "22,6 kg", "Misil antitanque de vehículos y helicópteros (AH-1W); "
       "uno de los más fabricados del mundo."),
    _f("ataka", "9M120 Ataka", "Misil antitanque", "Rusia", "KBM Kolomna", "Por radio, semiautomática",
       "Hasta 6 km", "Unos 550 m/s", "7,4 kg, carga hueca en tándem", "49,5 kg (con tubo)",
       "Misil antitanque de los helicópteros Mi-28 y Ka-52."),
    _f("vikhr", "9K121 Vikhr", "Misil antitanque", "Rusia", "KBP Tula", "Por haz láser", "8 a 10 km", "Mach 1,8",
       "8 kg, carga hueca en tándem", "45 kg", "Misil antitanque supersónico del Ka-52 y del Su-25T."),
    _f("mam_l", "MAM-L", "Munición guiada liviana", "Turquía", "Roketsan", "Láser semiactivo", "Hasta 8 km",
       "Planea", "Carga hueca en tándem, termobárica o explosiva", "22 kg",
       "Arma del dron Bayraktar TB2; derivada del cohete guiado Cirit."),
    _f("ba7", "Blue Arrow 7 (BA-7)", "Misil antitanque", "China", "AVIC (Luoyang)", "Láser semiactivo",
       "Hasta 7 km", "Subsónico", "Carga hueca en tándem", "47 kg", "Misil antitanque de los drones Wing Loong."),
    _f("umtas", "L-UMTAS", "Misil antitanque", "Turquía", "Roketsan", "Láser semiactivo", "Hasta 8 km",
       "Supersónico al final", "Carga hueca en tándem", "37,5 kg", "Misil antitanque del helicóptero T129 ATAK."),
    # ------------------------------------------------------------------------- cañones, cohetes y ametralladoras
    _f("gsh23", "GSh-23", CAN + " doble de 23 mm", "Unión Soviética / Rusia", "KBP Tula", "Puntería del piloto o del "
       "artillero", "Hasta unos 2 km", "3 400 disparos por minuto", "23 × 115 mm", "50 kg",
       "Cañón de dos tubos del Mi-35M (en torreta), del MiG-23 y del MiG-21bis."),
    _f("2a42", "2A42", CAN + " de 30 mm", "Unión Soviética / Rusia", "KBP Tula", "Puntería del artillero",
       "Hasta unos 4 km", "200 a 800 disparos por minuto", "30 × 165 mm", "115 kg",
       "Cañón del Mi-28, del Ka-52 y del vehículo de infantería BMP-2."),
    _f("m230", "M230", "Cañón de cadena de 30 mm", "Estados Unidos", "Northrop Grumman (Hughes)",
       "Apunta adonde mira el casco del artillero", "1,5 a 4 km", "625 disparos por minuto", "30 × 113 mm", "55,9 kg",
       "Cañón bajo la nariz del AH-64 Apache; también en el MH-60 DAP."),
    _f("m197", "M197", CAN + " de tres tubos de 20 mm", "Estados Unidos", "General Dynamics",
       "Torreta que sigue el casco del artillero", "Hasta unos 2 km", "750 a 1 500 disparos por minuto",
       "20 × 102 mm", "66 kg", "Cañón rotativo de los helicópteros AH-1 Cobra y Viper y del T129 ATAK."),
    _f("30m781", "Nexter 30M781", CAN + " de 30 mm", "Francia", "Nexter (KNDS)", "Torreta que sigue el casco",
       "Hasta unos 2 km", "750 disparos por minuto", "30 × 113 mm", "65 kg", "Cañón en torreta del helicóptero Tigre."),
    _f("m134", "M134 Minigun", "Ametralladora rotativa de 7,62 mm", "Estados Unidos",
       "General Electric / Dillon Aero", "Puntería del artillero", "Hasta 1 km", "2 000 a 6 000 disparos por minuto",
       "7,62 × 51 mm", "18 kg", "Ametralladora de seis tubos en las puertas de helicópteros (MH-60, MH-47, MH-6, "
       "UH-1H) y en el AH-6."),
    _f("pkt", "PKT", "Ametralladora de 7,62 mm", "Unión Soviética / Rusia", "Degtyarev (Kovrov)",
       "Puntería del artillero", "Hasta 1,5 km", "700 a 800 disparos por minuto", "7,62 × 54 mm R", "10,5 kg",
       "Ametralladora de vehículos y de la nariz y las puertas del Mi-17."),
    _f("s8", "S-8", "Cohetes de 80 mm", "Unión Soviética / Rusia", "Nudelman (Tochmash)", "Ninguna",
       "1,3 a 4 km", "Unos 600 m/s", "3,6 kg (carga hueca o fragmentación)", "11,3 kg",
       "Cohete de los lanzadores B-8 (20 cohetes) de los Mi-35, Mi-17, Mi-28, Ka-52 y Su-25."),
    _f("hydra70", "Hydra 70", "Cohetes de 70 mm", "Estados Unidos", "General Dynamics", "Ninguna (APKWS: láser)",
       "Hasta 8 km", "Unos 700 m/s", "4,5 kg (M151)", "10,4 kg",
       "Cohete de 2,75 pulgadas en lanzadores de 7 o 19; también lo dispara el K-8W (lanzador belga de 70 mm)."),
    _f("cirit", "Cirit", "Cohetes guiados de 70 mm", "Turquía", "Roketsan", "Láser semiactivo", "Hasta 8 km",
       "Supersónico", "4 kg", "15 kg", "Cohete guiado del T129 ATAK; barato para blancos livianos."),
    # ------------------------------------------------------------------------------ defensa antiaérea
    _f("zu23", "ZU-23-2", CAN + " antiaéreo doble de 23 mm", "Unión Soviética", "Fábrica de Tula (KBP)",
       "Puntería óptica", "2,5 km (1,5 km de altura)", "2 000 disparos por minuto (los dos tubos)", "23 × 152 mm",
       "950 kg", "Cañón remolcado muy difundido; también defiende las baterías Pechora-2M.", ("modelos", "zu23_2")),
    _f("5v27", "5V27D / 5V27DE", SAM + " de alcance medio", "Unión Soviética / Rusia", "Fakel",
       "Radiocomando (la estación de guía lo dirige)", "3,5 a 32 km", "Unos 900 m/s", "72 kg", "980 kg",
       "Misil del S-125 Neva (SA-3) y de su modernización Pechora-2M de la FANB."),
    _f("9m317", "9M317E", SAM + " de alcance medio", "Rusia", "Almaz-Antey (Dolgoprudny)", "Radar semiactivo",
       "3 a 45 km (hasta 25 km de altura)", "Mach 4 (unos 1 200 m/s)", "70 kg", "715 kg",
       "Misil del Buk-M2E de la FANB.", ("modelos", "buk_m2e")),
    _f("9m317m", "9M317M", SAM + " de alcance medio", "Rusia", "Almaz-Antey (Dolgoprudny)",
       "Inercial y radar activo o semiactivo", "2,5 a 70 km (hasta 35 km de altura)", "Mach 4,5", "62 kg", "581 kg",
       "Misil del Buk-M3, que se lanza desde un contenedor cerrado (6 por vehículo).", ("modelos", "buk_m3")),
    _f("igla_s", "9K338 Igla-S (9M342)", SAM + " portátil", "Rusia", "KBM Kolomna", "Infrarrojo",
       "Hasta 6 km (3,5 km de altura)", "Unos 600 m/s", "2,5 kg", "11,7 kg el misil; 19 kg con el lanzador",
       "Misil portátil de la FANB; un solo soldado lo dispara desde el hombro.", ("modelos", "igla_s")),
    _f("mistral", "Mistral", SAM + " de muy corto alcance", "Francia", "MBDA", "Infrarrojo",
       "Hasta 6 km (3 km de altura)", "Mach 2,7", "3 kg", "19,7 kg", "Misil de corto alcance en afuste doble "
       "(ATLAS) o portátil.", ("modelos", "mistral")),
    _f("rbs70", "RBS 70", SAM + " de muy corto alcance", "Suecia", "Saab", "Por haz láser (el tirador mantiene la "
       "mira)", "Hasta 8 km (5 km de altura)", "Mach 2", "1,1 kg (Bolide)", "17 kg el misil",
       "Guiado por láser, no lo engañan las bengalas.", ("modelos", "rbs70")),
    _f("9m83", "9M83ME", SAM + " de largo alcance", "Rusia", "Novator", "Inercial y radar semiactivo",
       "6 a 150 km", "Unos 1 700 m/s", "150 kg", "3 500 kg", "Misil «chico» del S-300VM Antey-2500.",
       ("modelos", "s300vm")),
    _f("9m82", "9M82ME", SAM + " de muy largo alcance y antimisil", "Rusia", "Novator", "Inercial y radar "
       "semiactivo", "13 a 200 km", "Unos 2 400 m/s", "150 kg", "5 800 kg",
       "Misil grande del S-300VM: también derriba misiles balísticos.", ("modelos", "s300vm")),
    _f("57e6", "57E6", SAM + " de corto alcance", "Rusia", "KBP Tula", "Radiocomando, con seguimiento por radar y "
       "óptico", "1,2 a 20 km (15 km de altura)", "Unos 1 300 m/s", "20 kg", "74,5 kg",
       "Misil del Pantsir-S1; la primera etapa se desprende y el dardo sigue solo.", ("modelos", "pantsir_s1")),
    _f("2a38m", "2A38M", CAN + " antiaéreo doble de 30 mm", "Rusia", "KBP Tula", "Radar y óptica de tiro",
       "Hasta 4 km (3 km de altura)", "4 000 a 5 000 disparos por minuto", "30 × 165 mm", "195 kg",
       "Cañones del Pantsir-S1 y del Tunguska, contra drones y misiles cerca de la batería.",
       ("modelos", "pantsir_s1")),
    _f("9m338", "9M338", SAM + " de corto alcance", "Rusia", "Almaz-Antey (Kupol)", "Radiocomando",
       "1 a 16 km (10 km de altura)", "Unos 1 000 m/s", "15 kg", "163 kg",
       "Misil del Tor-M2: el vehículo lleva 16 y puede tirar en movimiento.", ("modelos", "tor_m2e")),
    _f("48n6", "48N6DM", SAM + " de largo alcance", "Rusia", "Fakel", "Inercial y seguimiento por el misil (TVM)",
       "3 a 250 km (hasta 27 km de altura)", "Mach 6 (unos 2 000 m/s)", "180 kg", "1 900 kg",
       "Misil pesado del S-400 Triumf.", ("modelos", "s400")),
    _f("9m96", "9M96E2", SAM + " de alcance medio", "Rusia", "Fakel", "Inercial y radar activo",
       "1 a 120 km (hasta 30 km de altura)", "Unos 1 000 m/s", "24 kg", "420 kg",
       "Misil chico y muy maniobrable del S-400; cuatro caben en el tubo de un 48N6.", ("modelos", "s400")),
    _f("hq9", "HQ-9", SAM + " de largo alcance", "China", "CASIC (CPMIEC)", "Inercial, enlace de datos y "
       "seguimiento por el misil", "6 a 200 km", "Mach 4,2", "180 kg", "1 300 kg",
       "Sistema antiaéreo chino de largo alcance; se lanza desde contenedores verticales.", ("modelos", "hq9")),
    _f("pac3", "PAC-3 MSE", SAM + " y antimisil", "Estados Unidos", "Lockheed Martin",
       "Inercial y radar activo de ondas milimétricas; choca contra el blanco", "Hasta unos 35 km contra misiles "
       "(más contra aviones)", "Mach 5", "Impacto directo (con carga auxiliar)", "312 kg",
       "Misil del Patriot que destruye balísticos chocando contra ellos.", ("modelos", "patriot")),
    _f("pac2", "MIM-104 PAC-2 GEM-T", SAM + " de largo alcance", "Estados Unidos", "Raytheon",
       "Seguimiento por el misil (TVM)", "Hasta 160 km", "Mach 4+", "90 kg", "900 kg",
       "Misil clásico del Patriot contra aviones y misiles de crucero.", ("modelos", "patriot")),
    _f("hawk", "MIM-23B Hawk (I-Hawk)", SAM + " de alcance medio", "Estados Unidos", "Raytheon",
       "Radar semiactivo", "1,5 a 40 km (hasta 18 km de altura)", "Mach 2,4", "54 kg", "638 kg",
       "Sistema antiaéreo de la Guerra Fría que todavía usan varios países.", ("modelos", "mim23")),
    _f("iris_t_slm", "IRIS-T SLM", SAM + " de alcance medio", "Alemania", "Diehl Defence",
       "Inercial, enlace de datos e infrarrojo por imagen", "Hasta 40 km (20 km de altura)", "Mach 3",
       "Fragmentación", "—", "Versión tierra-aire del IRIS-T con motor más grande; muy usada en Ucrania.",
       ("modelos", "iris_t_slm")),
    _f("9m33", "9M33M3", SAM + " de corto alcance", "Unión Soviética / Rusia", "Fakel", "Radiocomando",
       "1,5 a 10 km (5 km de altura)", "Unos 800 m/s", "15 kg", "170 kg", "Misil del 9K33 Osa-AKM (SA-8), "
       "anfibio y con radar propio.", ("modelos", "osa_akm")),
    _f("stinger", "FIM-92 Stinger", SAM + " portátil", "Estados Unidos", "Raytheon", "Infrarrojo y ultravioleta",
       "Hasta 8 km (3,8 km de altura)", "Mach 2,2 (unos 750 m/s)", "3 kg", "10,1 kg el misil; 15,2 kg con el "
       "lanzador", "Misil portátil de Estados Unidos; también va en el M-SHORAD.", ("modelos", "stinger")),
    _f("xm914", "XM914", "Cañón de cadena de 30 mm", "Estados Unidos", "Northrop Grumman", "Torreta con sensores",
       "Hasta unos 3 km", "200 disparos por minuto", "30 × 113 mm", "—",
       "Cañón del M-SHORAD (derivado del M230 del Apache), contra drones y helicópteros.", ("modelos", "m_shorad")),
    _f("oerlikon35", "Oerlikon KDA de 35 mm", CAN + " antiaéreo de 35 mm", "Suiza", "Oerlikon (Rheinmetall)",
       "Radar y óptica de tiro", "Hasta 4 km (3 km de altura)", "550 disparos por minuto cada tubo",
       "35 × 228 mm", "—", "Los dos cañones del Gepard y de la pieza remolcada GDF.", ("modelos", "gepard")),
    _f("azp23", "AZP-23 Amur", CAN + " antiaéreo cuádruple de 23 mm", "Unión Soviética", "KBP Tula",
       "Radar de tiro", "2,5 km (1,5 km de altura)", "3 400 disparos por minuto (los cuatro)", "23 × 152 mm", "—",
       "Los cuatro cañones del ZSU-23-4 Shilka.", ("modelos", "zsu23_4")),
    _f("bofors40", "Bofors 40 mm L/70", CAN + " antiaéreo de 40 mm", "Suecia", "Bofors (BAE Systems)",
       "Radar u óptica de tiro; espoleta de proximidad", "Hasta 4 km", "240 a 330 disparos por minuto",
       "40 × 364 mm R", "5 150 kg (pieza remolcada)", "Cañón antiaéreo clásico, con munición que estalla cerca del "
       "blanco.", ("modelos", "bofors40")),
    # sistemas de las operaciones historicas (sin tabla de armas en el simulador)
    _f("v750", "V-750 (S-75 Dvina, SA-2)", SAM + " de alcance medio", "Unión Soviética", "Fakel (Lavochkin)",
       "Radiocomando", "7 a 45 km (hasta 25 km de altura)", "Mach 3,5", "190 kg", "2 300 kg",
       "El misil que derribó al U-2 de Powers (1960); muy usado en Vietnam y Medio Oriente."),
    _f("3m9", "3M9 (2K12 Kub, SA-6)", SAM + " de alcance medio", "Unión Soviética", "Vympel (Toropov)",
       "Radar semiactivo; estatorreactor", "4 a 24 km (hasta 14 km de altura)", "Mach 2,8", "57 kg", "599 kg",
       "Sorprendió a la aviación israelí en 1973; tres misiles por vehículo."),
    _f("5v21", "5V21 (S-200 Vega, SA-5)", SAM + " de largo alcance", "Unión Soviética", "Fakel",
       "Radar semiactivo", "17 a 250 km (hasta 40 km de altura)", "Unos 1 200 m/s", "217 kg", "7 100 kg",
       "Misil enorme contra bombarderos y aviones de alerta; Libia lo disparó en 1986."),
    _f("roland", "Roland 2", SAM + " de corto alcance", "Francia / Alemania", "Euromissile (Aérospatiale / MBB)",
       "Radiocomando semiautomático", "0,5 a 6,3 km (5,5 km de altura)", "Mach 1,6", "9 kg", "66,5 kg",
       "Defendió Puerto Argentino en 1982 e Irak en 1991."),
    _f("r440", "R440 Crotale", SAM + " de corto alcance", "Francia", "Matra / Thomson-CSF", "Radiocomando",
       "0,5 a 10 km (hasta 5 km de altura)", "Mach 2,3", "15 kg", "85 kg",
       "Sistema francés de corto alcance; Libia lo tenía en 1986."),
    _f("s60", "S-60 de 57 mm", CAN + " antiaéreo de 57 mm", "Unión Soviética", "Fábrica estatal (diseño Grabin)",
       "Radar de tiro u óptica", "Hasta 6 km (4 km de altura)", "105 a 120 disparos por minuto", "57 × 348 mm SR",
       "4 500 kg", "Cañón remolcado de la Guerra Fría, todavía en servicio en muchos países."),
    # ---------------------------------------------------------------------- misiles de crucero y antibuque
    _f("tomahawk", "BGM-109 Tomahawk", "Misil de crucero", "Estados Unidos", "Raytheon (General Dynamics)",
       "Inercial, GPS, perfil del terreno y correlación de imagen", "Hasta 1 600 km (Block IV)",
       "Unos 880 km/h", "450 kg", "1 510 kg con acelerador",
       "Misil de crucero de buques y submarinos de Estados Unidos; vuela bajo siguiendo el terreno.",
       ("modelos", "crucero")),
    _f("kalibr", "3M-14 Kalibr", "Misil de crucero", "Rusia", "Novator", "Inercial, GLONASS y perfil del terreno",
       "1 500 a 2 500 km (300 km la versión de exportación Club)", "Mach 0,8", "450 kg", "1 770 kg",
       "Misil de crucero de corbetas, fragatas y submarinos rusos (Kilo, Grigorovich, Buyan-M).",
       ("modelos", "kalibr")),
    _f("brahmos", "BrahMos", "Misil de crucero supersónico", "India / Rusia", "BrahMos Aerospace",
       "Inercial, GPS y radar activo; estatorreactor", "290 km (versiones nuevas: 450 km o más)", "Mach 2,8 a 3",
       "200 a 300 kg", "3 000 kg", "Derivado del P-800 Oniks; uno de los misiles de crucero más rápidos.",
       ("modelos", "brahmos")),
    _f("oniks", "P-800 Oniks (Yakhont)", AB + " supersónico", "Rusia", "NPO Mashinostroyeniya",
       "Inercial y radar activo; estatorreactor", "Hasta 300 km (Yakhont de exportación)", "Mach 2,5",
       "200 a 250 kg", "3 000 kg", "Misil de la batería costera Bastion-P y de buques rusos.", ("modelos", "oniks")),
    _f("nsm", "NSM (Naval Strike Missile)", AB, "Noruega", "Kongsberg",
       "Inercial, GPS, perfil del terreno e infrarrojo por imagen", "Más de 185 km", "Mach 0,9", "125 kg", "410 kg",
       "Misil antibuque furtivo; identifica el buque por su imagen.", ("modelos", "nsm")),
    # ------------------------------------------------------------------- torpedos y misiles balisticos
    _f("mk48", "Mk 48 ADCAP", "Torpedo pesado", "Estados Unidos", "Lockheed Martin (Gould)",
       "Filoguiado y sonar activo y pasivo", "Unos 38 km a 55 nudos (50 km a 40 nudos)", "Hasta 55 nudos",
       "290 kg", "1 676 kg (533 mm)", "Torpedo pesado de los submarinos; en el simulador, el de todos los "
       "submarinos.", ("clases", "torpedo")),
    _f("9m723", "9M723 (Iskander-M)", "Misil balístico de corto alcance", "Rusia", "KBM Kolomna",
       "Inercial, GLONASS y óptica al final; maniobra en vuelo", "Hasta 500 km (Iskander-E: 280 km)",
       "Mach 6 a 7", "480 a 700 kg", "3 800 kg",
       "Misil cuasi balístico que maniobra para esquivar la defensa antimisil; dos por lanzador."),
    # ------------------------------------------------- armas de las aeronaves de las fuerzas aereas del mundo
    _f("pl8", "PL-8", AA + " de corto alcance", "China", "CAAA (Luoyang)", "Infrarrojo de todo aspecto",
       "Hasta 15 km", "Mach 2,5", "11 kg", "115 kg", "Versión china del Python 3 israelí; arma de los J-7, J-11 y L-15."),
    _f("r37", "R-37M (AA-13 Axehead)", AA + " de muy largo alcance", "Rusia", "Vympel (KTRV)",
       "Inercial con enlace de datos y radar activo", "Hasta 300 km", "Mach 6", "60 kg", "510 kg",
       "Misil del MiG-31BM y del Su-35 contra aviones de alerta temprana y cisternas lejanos."),
    _f("derby", "Derby", AA + " de alcance medio", "Israel", "Rafael", "Radar activo", "Hasta 50 km", "Mach 4",
       "23 kg", "118 kg", "Misil «dispara y olvida» derivado del Python; del Tejas, del Kfir y de la batería Spyder."),
    _f("jassm", "AGM-158 JASSM", "Misil de crucero aire-superficie furtivo", "Estados Unidos", "Lockheed Martin",
       "Inercial, GPS e infrarrojo por imagen", "370 km (JASSM-ER: 925 km)", "Subsónico", "450 kg, penetrante",
       "1 020 kg", "Misil furtivo de largo alcance del B-2, el B-1B y los cazas de Estados Unidos."),
    _f("kh101", "Kh-101", "Misil de crucero aire-superficie", "Rusia", "Raduga",
       "Inercial, GLONASS, perfil del terreno y óptica al final", "Hasta 2 500 km", "Unos 700 km/h",
       "400 kg", "2 400 kg", "Misil de crucero furtivo de los bombarderos Tu-95MS y Tu-160."),
    _f("cj20", "CJ-20 (KD-20)", "Misil de crucero aire-superficie", "China", "CASIC",
       "Inercial, satélite Beidou y perfil del terreno", "Hasta 1 500 km", "Subsónico", "—", "—",
       "Misil de crucero del bombardero H-6K."),
    _f("shturm", "9M114 Shturm (AT-6 Spiral)", "Misil antitanque", "Unión Soviética / Rusia", "KBM Kolomna",
       "Por radio, semiautomática", "Hasta 5 km", "Unos 400 m/s", "5,3 kg, carga hueca", "31,4 kg (con tubo)",
       "Misil antitanque de los Mi-24V y Mi-35."),
    _f("hj10", "HJ-10 (AKD-10)", "Misil antitanque", "China", "Norinco / CASC", "Láser semiactivo", "Hasta 8 km",
       "—", "Carga hueca en tándem", "—", "Misil antitanque del helicóptero Z-10; la versión AKD-10 va en drones."),
    _f("helina", "Helina (Dhruvastra)", "Misil antitanque", "India", "DRDO / Bharat Dynamics",
       "Infrarrojo por imagen (dispara y olvida)", "Hasta 7 km", "—", "8 kg, carga hueca en tándem", "43 kg",
       "Misil antitanque de los helicópteros Prachand y Rudra."),
    _f("mokopa", "ZT-6 Mokopa", "Misil antitanque", "Sudáfrica", "Denel Dynamics", "Láser semiactivo",
       "Hasta 10 km", "—", "Carga hueca en tándem", "49,8 kg", "Misil antitanque del helicóptero Rooivalk."),
    _f("ar1", "AR-1", AS + " ligero", "China", "CASC", "Láser semiactivo e inercial", "Hasta 8 km", "—",
       "10 kg", "45 kg", "Misil de los drones chinos CH-3 y CH-4."),
    _f("sadid", "Sadid-1", AS + " ligero", "Irán", "Industria de defensa de Irán",
       "Electroóptica (dispara y olvida)", "Hasta 6 km", "—", "—", "—", "Misil del dron iraní Shahed-129."),
    # ---------------------------------------------------------- misiles de buques que antes lanzaban el Tomahawk
    _f("yj18", "YJ-18", AB + " y de ataque a tierra", "China", "CASIC", "Inercial, satélite Beidou y radar activo",
       "Unos 540 km", "Subsónico; Mach 3 en los últimos 40 km", "Unos 300 kg", "—",
       "Misil de celdas verticales del destructor Tipo 052D; parecido al 3M-54 Klub ruso.", ("modelos", "yj18")),
    _f("moskit", "P-270 Moskit (SS-N-22)", AB + " supersónico", "Unión Soviética / Rusia", "Raduga",
       "Inercial y radar activo o pasivo; estatorreactor", "Hasta 120 km", "Mach 2,5 rozando el mar", "320 kg",
       "3 950 kg", "Misil de los destructores Sovremenny y de las corbetas Tarantul (Molniya).", ("modelos", "moskit")),
    _f("otomat", "Otomat Mk 2 (Teseo)", AB, "Italia / Francia", "OTO Melara / Matra (MBDA)",
       "Inercial y radar activo; turborreactor", "Hasta 180 km", "Mach 0,9", "210 kg", "770 kg",
       "Misil de las fragatas Lupo, también de las Mariscal Sucre de la Armada Bolivariana.", ("modelos", "otomat")),
    _f("granit", "P-700 Granit (SS-N-19)", AB + " de largo alcance", "Unión Soviética / Rusia",
       "NPO Mashinostroyeniya", "Inercial y radar activo; las salvas se reparten los blancos", "Hasta 625 km",
       "Mach 2,5", "750 kg", "7 000 kg", "Misil pesado contra portaaviones del Almirante Kuznetsov y de los cruceros "
       "Kirov.", ("modelos", "granit")),
    _f("kowsar", "Kowsar", AB + " ligero", "Irán", "Industrias aeroespaciales de Irán",
       "Televisión o radar activo", "Hasta 25 km", "Subsónico", "29 kg", "100 kg",
       "Misil antibuque chico de las lanchas rápidas iraníes, derivado del chino C-701."),
    # -------------------------------------------------------------------------------------- cañones navales
    _f("mk8_114", "4.5 in Mk 8 (114 mm)", "Cañón naval de 114 mm", "Reino Unido", "Vickers (VSEL / BAE Systems)",
       "Dirección de tiro por radar", "Hasta 22 km", "25 disparos por minuto", "114 mm (21 kg el proyectil)",
       "26 t la torre", "Cañón de los destructores Type 42 y las fragatas Type 21 en las Malvinas (1982)."),
    _f("mk6_114", "4.5 in Mk 6 (torre doble de 114 mm)", "Cañón naval de 114 mm", "Reino Unido", "Vickers",
       "Dirección de tiro por radar", "Hasta 17 km", "12 a 20 disparos por minuto cada tubo",
       "114 mm (25 kg el proyectil)", "45 t la torre", "Torre doble de las fragatas Rothesay y Leander."),
    _f("oto127", "OTO Melara 127/54 Compacto", "Cañón naval de 127 mm", "Italia", "OTO Melara (Leonardo)",
       "Dirección de tiro por radar", "Hasta 23 km", "40 disparos por minuto", "127 mm (32 kg el proyectil)",
       "37,5 t", "Cañón principal de las fragatas Lupo (Mariscal Sucre) de la Armada Bolivariana."),
    _f("oto76", "OTO Melara 76/62 Súper Rápido", "Cañón naval de 76 mm", "Italia", "OTO Melara (Leonardo)",
       "Dirección de tiro por radar", "Hasta 16 km (20 km con munición especial)", "120 disparos por minuto",
       "76 mm (6,3 kg el proyectil)", "7,5 t", "El cañón naval más difundido; lo llevan las FREMM, las Tamandaré y "
       "los patrulleros Guaiquerí y Guaicamacuto."),
    _f("ak176", "AK-176 (76 mm)", "Cañón naval de 76 mm", "Unión Soviética / Rusia", "Arsenal (San Petersburgo)",
       "Dirección de tiro por radar", "Hasta 15 km", "120 disparos por minuto", "76,2 mm (5,9 kg el proyectil)",
       "11 t", "Cañón de corbetas rusas como la Tarantul; el chino H/PJ-26 de la fragata Tipo 054A deriva de él."),
    _f("a190", "A-190 (100 mm)", "Cañón naval de 100 mm", "Rusia", "Arsenal / Burevestnik",
       "Dirección de tiro por radar y óptica", "Hasta 20 km", "80 disparos por minuto",
       "100 mm (15,6 kg el proyectil)", "15 t", "Cañón de las fragatas Grigorovich y las corbetas Buyan-M."),
    _f("ak130", "AK-130 (torre doble de 130 mm)", "Cañón naval de 130 mm", "Unión Soviética / Rusia", "Arsenal",
       "Dirección de tiro por radar", "Hasta 23 km", "Hasta 90 disparos por minuto (los dos tubos)",
       "130 mm (33 kg el proyectil)", "98 t", "Torre doble de los destructores Sovremenny; el chino H/PJ-38 del "
       "Tipo 052D es su versión de un tubo."),
    _f("mk45", "Mk 45 (127 mm)", "Cañón naval de 127 mm", "Estados Unidos", "BAE Systems (United Defense)",
       "Dirección de tiro por radar", "Hasta 24 km (Mod 4)", "16 a 20 disparos por minuto",
       "127 mm (31 kg el proyectil)", "28,9 t", "Cañón de los destructores Arleigh Burke y los cruceros Ticonderoga."),
    _f("phalanx", "Phalanx CIWS (Mk 15)", "Cañón de defensa cercana de 20 mm", "Estados Unidos", "Raytheon",
       "Radar propio: busca, sigue y tira solo", "Hasta 3,6 km", "4 500 disparos por minuto",
       "20 × 102 mm (tungsteno)", "6,2 t", "Última defensa del buque contra misiles en los buques de Estados Unidos."),
    _f("ak630", "AK-630 (30 mm, seis tubos)", "Cañón de defensa cercana de 30 mm", "Unión Soviética / Rusia",
       "Tulamashzavod", "Radar o puntería óptica", "Hasta 4 km", "5 000 disparos por minuto", "30 × 165 mm",
       "1,9 t", "Cañón rotativo de defensa cercana de los buques rusos."),
    _f("millennium35", "Oerlikon Millennium (35 mm)", "Cañón naval de 35 mm", "Suiza", "Rheinmetall (Oerlikon)",
       "Dirección de tiro electroóptica; munición AHEAD", "Hasta 3,5 km", "1 000 disparos por minuto",
       "35 × 228 mm", "3,3 t", "Cañón de los patrulleros Guaiquerí y Guaicamacuto; su munición estalla en una nube "
       "de esquirlas delante del blanco."),
    # ---------------------------------------------------------------------- misiles antiaéreos de buques
    _f("sea_dart", "Sea Dart (GWS-30)", "Misil antiaéreo naval", "Reino Unido", "Hawker Siddeley Dynamics",
       "Radar semiactivo; estatorreactor", "Hasta 74 km", "Mach 3", "—", "550 kg",
       "Misil de los destructores Type 42 y de los portaaviones Invincible; derribó siete aviones en 1982."),
    _f("sea_cat", "Sea Cat", "Misil antiaéreo naval de corto alcance", "Reino Unido", "Short Brothers",
       "Radiocomando (el tirador lo dirige con una palanca)", "Hasta 5 km", "Mach 0,8", "—", "63 kg",
       "Misil antiaéreo de los años sesenta; lo llevaban el Hermes y las fragatas Type 21 y Rothesay."),
    _f("aspide", "Aspide (Albatros)", "Misil antiaéreo naval", "Italia", "Selenia (MBDA)", "Radar semiactivo",
       "Hasta 15 km", "Mach 4", "35 kg", "220 kg", "Misil antiaéreo de las fragatas Lupo, derivado del Sparrow."),
    _f("sm2", "SM-2 Standard (RIM-66 / RIM-67)", "Misil antiaéreo naval de largo alcance", "Estados Unidos",
       "Raytheon", "Inercial con enlace de datos y radar semiactivo", "Hasta 170 km", "Mach 3,5", "62 kg",
       "708 kg", "Misil del sistema Aegis de los destructores Arleigh Burke y los cruceros Ticonderoga."),
    _f("essm", "ESSM (RIM-162)", "Misil antiaéreo naval de alcance medio", "Estados Unidos", "Raytheon",
       "Inercial con enlace de datos y radar semiactivo", "Hasta 50 km", "Mach 4", "39 kg", "280 kg",
       "Misil muy ágil contra misiles antibuque; caben cuatro en una celda de lanzamiento vertical."),
    _f("ram", "RAM (RIM-116)", "Misil de defensa cercana", "Estados Unidos / Alemania", "Raytheon / Diehl",
       "Pasiva: radiofrecuencia e infrarrojo", "Hasta 9 km", "Mach 2+", "11,3 kg", "73,5 kg",
       "Misil «dispara y olvida» contra misiles antibuque; lanzador de 21 tubos."),
    _f("aster", "Aster 15 / Aster 30", "Misil antiaéreo naval", "Francia / Italia", "MBDA (Eurosam)",
       "Inercial con enlace de datos y radar activo", "30 km (Aster 15) a 120 km (Aster 30)", "Mach 3 a 4,5",
       "15 kg", "310 a 450 kg", "Misil de las fragatas FREMM y del portaaviones Charles de Gaulle."),
    _f("hq16", "HQ-16", "Misil antiaéreo naval de alcance medio", "China", "CASIC",
       "Inercial y radar semiactivo", "Hasta 40 km (HQ-16B: 70 km)", "Mach 3", "—", "—",
       "Misil de lanzamiento vertical de la fragata Tipo 054A, emparentado con el ruso Buk."),
    _f("shtil", "Shtil", "Misil antiaéreo naval de alcance medio", "Rusia", "Altair / Dolgoprudny",
       "Inercial y radar semiactivo", "Hasta 50 km", "Mach 4", "62 kg", "715 kg",
       "Versión naval del Buk: de los destructores Sovremenny y las fragatas Grigorovich."),
    _f("camm", "Sea Ceptor (CAMM)", "Misil antiaéreo naval", "Reino Unido", "MBDA",
       "Inercial con enlace de datos y radar activo", "Hasta 25 km", "Mach 3", "—", "99 kg",
       "Misil de lanzamiento vertical de las fragatas Tamandaré."),
    # -------------------------------------------------------------------------------- torpedos de submarinos
    _f("sst4", "SST-4", "Torpedo pesado", "Alemania", "AEG-Telefunken (Atlas Elektronik)",
       "Filoguiado y sonar pasivo y activo", "Hasta 28 km", "Hasta 35 nudos", "260 kg", "1 414 kg (533 mm)",
       "Torpedo de los submarinos Tipo 209, como los Sábalo de la Armada Bolivariana."),
    _f("dm2a4", "DM2A4 (SeaHake)", "Torpedo pesado", "Alemania", "Atlas Elektronik", "Filoguiado por fibra óptica y "
       "sonar", "Más de 50 km", "Más de 50 nudos", "260 kg", "1 370 kg (533 mm)",
       "Torpedo eléctrico de los submarinos Tipo 212A."),
    _f("f21", "F21 Artemis", "Torpedo pesado", "Francia", "Naval Group", "Filoguiado por fibra óptica y sonar",
       "Hasta 50 km", "Hasta 50 nudos", "—", "1 500 kg (533 mm)", "Torpedo de los submarinos Scorpène."),
    _f("tt53", "53-65KE / TEST-71ME", "Torpedo pesado", "Unión Soviética / Rusia", "Dagdizel / Region",
       "Estela (53-65KE) o filoguiado con sonar (TEST-71ME)", "Hasta 19 km", "Hasta 45 nudos", "300 kg",
       "2 000 kg (533 mm)", "Torpedos de los submarinos Kilo."),
    # -------------------------------------------------------------------------------- tanques y vehículos
    _f("2a46", "2A46M (125 mm)", "Cañón de tanque de 125 mm de ánima lisa", "Unión Soviética / Rusia",
       "Fábrica n.º 9 (Ekaterimburgo)", "Telémetro láser y computadora de tiro; también lanza misiles",
       "2 a 3 km (5 km con misil)", "Unos 8 disparos por minuto (cargador automático)",
       "125 mm: flecha, carga hueca y explosivo", "2,5 t", "Cañón de los T-72 y T-90; el chino ZPT-98 del ZTZ-99A "
       "deriva de él."),
    _f("9m119", "9M119 Refleks (AT-11)", "Misil antitanque lanzado por el cañón", "Rusia", "KBP Tula",
       "Por haz láser", "Hasta 5 km", "Unos 350 m/s", "4,5 kg, carga hueca en tándem", "17,2 kg",
       "Misil que el T-72B1 y el T-90 disparan por el tubo del cañón."),
    _f("m256", "M256 (120 mm)", "Cañón de tanque de 120 mm de ánima lisa", "Estados Unidos / Alemania",
       "Watervliet Arsenal (licencia Rheinmetall)", "Telémetro láser y visión térmica", "Hasta 4 km",
       "6 a 8 disparos por minuto (cargador humano)", "120 mm: flecha M829 y multipropósito", "—",
       "Cañón del M1 Abrams, versión del Rheinmetall L44."),
    _f("l55", "Rheinmetall Rh-120 L55", "Cañón de tanque de 120 mm de tubo largo", "Alemania", "Rheinmetall",
       "Telémetro láser y visión térmica", "Hasta 5 km", "6 a 8 disparos por minuto", "120 mm: flecha y "
       "multipropósito", "—", "Cañón del Leopard 2A6, con tubo más largo para más velocidad del proyectil."),
    _f("cn105", "CN-105-F1 (105 mm)", "Cañón de tanque de 105 mm", "Francia", "GIAT (Nexter)",
       "Telémetro y computadora de tiro", "Hasta 3 km", "8 disparos por minuto", "105 mm", "—",
       "Cañón del AMX-30, con proyectil de carga hueca que no gira."),
    _f("cockerill90", "Cockerill Mk III (90 mm)", "Cañón de 90 mm", "Bélgica", "Cockerill (John Cockerill)",
       "Puntería del tirador con telémetro", "Hasta 2 km", "Unos 6 disparos por minuto", "90 mm", "—",
       "Cañón del Scorpion 90 del Ejército venezolano."),
    _f("2a70", "2A70 (100 mm)", "Cañón de 100 mm (también lanza misiles)", "Rusia", "KBP Tula",
       "Computadora de tiro; misiles 9M117 por haz láser", "4 km (5,5 km con misil)", "10 disparos por minuto",
       "100 mm explosivo y misil 9M117", "—", "Cañón del BMP-3, montado junto a un 2A72 de 30 mm."),
    _f("2a72", "2A72 (30 mm)", "Cañón automático de 30 mm", "Rusia", "KBP Tula", "Puntería del tirador",
       "Hasta 4 km", "350 a 400 disparos por minuto", "30 × 165 mm", "84 kg",
       "Cañón liviano del BMP-3 y del BTR-80A."),
    _f("konkurs", "9M113 Konkurs (AT-5)", "Misil antitanque", "Unión Soviética / Rusia", "KBP Tula",
       "Por cable, semiautomática", "Hasta 4 km", "Unos 200 m/s", "2,7 kg, carga hueca en tándem (M)", "14,6 kg",
       "Misil antitanque del BMP-2."),
    _f("m242", "M242 Bushmaster (25 mm)", "Cañón de cadena de 25 mm", "Estados Unidos", "Northrop Grumman",
       "Puntería del tirador con visión térmica", "Hasta 3 km", "200 disparos por minuto", "25 × 137 mm", "119 kg",
       "Cañón del Bradley y del LAV-25."),
    _f("m2hb", "M2 Browning (12,7 mm)", "Ametralladora pesada de 12,7 mm", "Estados Unidos",
       "Browning (hoy FN Herstal, General Dynamics y otros)", "Puntería del tirador", "Hasta 1,8 km",
       "450 a 600 disparos por minuto", "12,7 × 99 mm", "38 kg",
       "La ametralladora pesada más usada del mundo; va en el Stryker, el M113, el Humvee y el Tiuna."),
    _f("mk19", "Mk 19 (40 mm)", "Lanzagranadas automático", "Estados Unidos", "General Dynamics",
       "Puntería del tirador", "Hasta 1,5 km (2,2 km máximo)", "325 a 375 disparos por minuto", "40 × 53 mm",
       "35 kg", "Lanzagranadas del Stryker y del Humvee."),
    _f("kpvt", "KPVT (14,5 mm)", "Ametralladora pesada de 14,5 mm", "Unión Soviética", "Degtyarev (Kovrov)",
       "Puntería del tirador", "Hasta 2 km", "600 disparos por minuto", "14,5 × 114 mm", "52 kg",
       "Ametralladora de la torre del BRDM-2 y de los BTR."),
    # ----------------------------------------------------------------------------- artillería y cohetes
    _f("2a64", "2A64 (152 mm)", "Obús de 152 mm", "Rusia", "Fábrica n.º 9 (Ekaterimburgo)",
       "Computadora de tiro", "Hasta 25 km (29 km con proyectil de alcance extendido)", "7 a 8 disparos por minuto",
       "152 mm (43,6 kg el proyectil)", "—", "Obús del autopropulsado 2S19 Msta-S.", ("modelos", "msta_s")),
    _f("m284", "M284 (155 mm)", "Obús de 155 mm", "Estados Unidos", "Watervliet Arsenal", "Computadora de tiro y GPS",
       "Hasta 24 km (30 km con proyectil asistido; Excalibur: 40 km)", "4 disparos por minuto",
       "155 mm (43 kg el proyectil)", "—", "Obús del M109A7 Paladin.", ("modelos", "m109a7")),
    _f("caesar155", "Cañón de 155 mm L52 del CAESAR", "Cañón de 155 mm", "Francia", "Nexter (KNDS)",
       "Computadora de tiro y GPS", "Hasta 40 km (55 km con proyectil asistido)", "6 disparos por minuto",
       "155 mm", "—", "Cañón montado en un camión: tira y se va en un minuto.", ("modelos", "caesar")),
    _f("m777", "M777 (155 mm)", "Obús remolcado de 155 mm", "Reino Unido / Estados Unidos", "BAE Systems",
       "Computadora de tiro digital", "Hasta 24 km (30 km asistido; Excalibur: 40 km)", "2 a 5 disparos por minuto",
       "155 mm", "4,2 t", "Obús liviano de titanio: lo lleva un helicóptero.", ("modelos", "m777")),
    _f("d30", "D-30 (122 mm)", "Obús remolcado de 122 mm", "Unión Soviética", "Fábrica n.º 9 (Petrov)",
       "Puntería directa o indirecta", "Hasta 15 km (22 km asistido)", "7 a 8 disparos por minuto",
       "122 mm (21,8 kg el proyectil)", "3,2 t", "Obús de cureña en tres patas que gira 360°; muy difundido.",
       ("modelos", "d30")),
    _f("2a60", "2A60 (120 mm)", "Mortero-obús de 120 mm", "Rusia", "Motovilikha", "Computadora de tiro",
       "Hasta 8,8 km (13 km asistido)", "8 a 10 disparos por minuto", "120 mm (proyectil o granada de mortero)", "—",
       "Arma del 2S23 Nona-SVK: tira granadas de mortero y proyectiles de artillería.", ("modelos", "nona_svk")),
    _f("9m22u", "9M22U (cohete de 122 mm)", "Cohete de artillería de 122 mm", "Unión Soviética", "Splav",
       "Ninguna", "Hasta 20 km", "Unos 690 m/s", "18,4 kg de explosivo", "66 kg",
       "Cohete del BM-21 Grad: 40 en 20 segundos."),
    _f("9m55", "9M55K (cohete de 300 mm)", "Cohete de artillería de 300 mm", "Rusia", "Splav",
       "Corrección de vuelo inercial", "20 a 70 km (hasta 90 km)", "—", "243 kg de submuniciones", "800 kg",
       "Cohete del BM-30 Smerch: 12 en 38 segundos."),
    _f("gmlrs", "M31 GMLRS", "Cohete guiado de 227 mm", "Estados Unidos", "Lockheed Martin", "Inercial y GPS",
       "15 a 70 km (ER: 150 km)", "—", "90 kg (unitaria)", "306 kg", "Cohete guiado del HIMARS: seis por "
       "contenedor, impacta a metros del blanco."),
    _f("atacms", "MGM-140 ATACMS", "Misil balístico táctico", "Estados Unidos", "Lockheed Martin",
       "Inercial y GPS", "Hasta 300 km", "Mach 3", "230 kg (unitaria) o submuniciones", "1 670 kg",
       "Misil que el HIMARS lanza en lugar de los seis cohetes."),
    _f("astros_ss", "Cohetes SS-30 a SS-80 (ASTROS II)", "Cohetes de artillería de 127 a 300 mm", "Brasil",
       "Avibras", "Ninguna (el AV-TM 300: inercial y GPS)", "30 a 90 km (AV-TM 300: 300 km)", "—",
       "Explosivo o submuniciones", "—", "Familia de cohetes del ASTROS II, que usan Brasil, Arabia Saudita y "
       "Malasia, entre otros."),
]
FICHAS: dict[str, Ficha] = {f.id: f for f in _FICHAS}

# codigo de armamento de la OTA (engine/ota.py) -> ficha
DE_OTA = {
    "MAA": "r77", "MAB": "r27er", "MAC": "r27et", "MAD": "r73", "MPA": "python4", "MPB": "aim9l", "M120": "aim120",
    "M9X": "aim9x", "MA1": "kh29l", "MA2": "kh31a", "MA3": "kh31p", "MA4": "kh29te", "MA5": "kh59me",
    "HRM": "agm88", "JSW": "agm154", "HLF": "agm114", "HPN": "harpoon", "EXO": "exocet", "MA6": "kh35",
    "TOR": "mk54", "BKR": "kab500kr", "BOD": "kab500od", "BRK": "kab1500kr", "BMK": "mk82", "BKM": "mk84",
    "BGB": "gbu10", "BBU": "gbu12", "BTK": "natak", "JDM": "gbu31", "M7S": "aim7", "PHX": "aim54", "SHF": "shafrir2",
    "MAG": "r550", "S53": "super530", "R23": "r23", "R40": "r40", "R60": "r60", "SHR": "agm45", "G27": "gbu27",
    "MIC": "mica", "MTR": "meteor", "IRT": "iris_t", "P15": "pl15", "P10": "pl10", "P12": "pl12", "SCL": "scalp",
    "C80": "c802", "FAB": "fab500", "MAV": "agm65", "K22": "kh22", "TOW": "tow", "ATK": "ataka", "VKR": "vikhr",
    "MAM": "mam_l", "UMT": "umtas", "BA7": "ba7",
    "P8": "pl8", "R37": "r37", "DRB": "derby", "BRA": "brahmos", "JAS": "jassm", "K101": "kh101", "CJ20": "cj20",
    "SHT": "shturm", "HJ10": "hj10", "HEL": "helina", "MOK": "mokopa", "AR1": "ar1", "SAD": "sadid",
    # cañon, cohetes y ametralladoras: los occidentales (ver OTA_POR_MODELO y ORIENTAL)
    "CKH": "m230", "CKL": "hydra70", "ALP": "m134",
}
ORIENTAL = {"CKH": "gsh23", "CKL": "s8", "ALP": "pkt"}  # aeronaves de origen sovietico, ruso o chino
_PAISES_ORIENTALES = ("rusia", "soviética", "china", "ucrania")
OTA_POR_MODELO = {
    "mi28ne": {"CKH": "2a42"}, "ka52": {"CKH": "2a42"},
    "ah1z": {"CKH": "m197"}, "ah1w": {"CKH": "m197"}, "t129": {"CKH": "m197", "CKL": "cirit"},
    "tiger": {"CKH": "30m781"}, "ah6m": {"CKH": "m134"},
    "ataque_ligero": {"CKL": "hydra70"},  # K-8W: lanzador belga de 70 mm adaptado por la AMB
    "ch53e": {"ALP": "m2hb"},  # ametralladoras de 12,7 mm
}
# arma de un sistema antiaereo (defensa_aerea.SISTEMAS[...].armas, id) -> ficha
DE_DA = {
    "zu23": "zu23", "5v27de": "5v27", "9m317e": "9m317", "igla_s": "igla_s", "mistral": "mistral", "rbs70": "rbs70",
    "9m83me": "9m83", "9m82me": "9m82", "57e6": "57e6", "2a38m": "2a38m", "9m338": "9m338", "9m317m": "9m317m",
    "48n6dm": "48n6", "9m96": "9m96", "hq9": "hq9", "pac3": "pac3", "pac2": "pac2", "amraam": "aim120",
    "aim9x": "aim9x", "mim23b": "hawk", "iris_t_sl": "iris_t_slm", "9m33m3": "9m33", "9m342": "igla_s",
    "fim92": "stinger", "fim92_ms": "stinger", "xm914": "xm914", "kdb35": "oerlikon35", "azp23": "azp23",
    "l70": "bofors40",
}
# modelo de misil de crucero o antibuque (clase misil_crucero) -> ficha
DE_MISIL = {"crucero": "tomahawk", "kalibr": "kalibr", "brahmos": "brahmos", "exocet": "exocet", "harpoon": "harpoon",
            "oniks": "oniks", "kh35": "kh35", "nsm": "nsm", "yj18": "yj18", "yj83": "c802", "moskit": "moskit",
            "otomat": "otomat", "granit": "granit"}
# modelos sin tabla de armas en el simulador (antiaereas de las operaciones historicas)
POR_MODELO = {"s75_sa2": ["v750"], "s125m_sa3": ["5v27"], "kub_sa6": ["3m9"], "s200": ["5v21"],
              "roland2": ["roland"], "crotale": ["r440"], "s60_57mm": ["s60"]}
# clase -> fichas (torpedos y balisticos; los buques y submarinos suman el misil que lanzan)
POR_CLASE = {"torpedo": ["mk48"], "misil_balistico": ["9m723"], "lanzador_balistico": ["9m723"],
             "submarino": ["mk48"], "fragata": ["mk54"], "destructor": ["mk54"]}
# armas propias de buques, submarinos, tanques, vehiculos y artilleria (solo de consulta: el combate sigue saliendo
# de la tabla de combate). Con lista propia, el modelo no toma el torpedo generico de su clase (POR_CLASE).
ARMAS_PROPIAS = {
    # buques
    "type42": ["mk8_114", "sea_dart"], "hermes": ["sea_cat"], "invincible": ["sea_dart"],
    "type21": ["mk8_114", "sea_cat"], "rothesay": ["mk6_114", "sea_cat"],
    "lupo": ["oto127", "aspide"], "fremm": ["oto76", "aster"], "type054a": ["ak176", "hq16"],
    "grigorovich": ["a190", "shtil"], "tamandare": ["oto76", "camm"],
    "guaiqueri": ["oto76", "millennium35"], "guaicamacuto": ["oto76", "millennium35"],
    "molniya": ["ak176", "ak630"], "buyan_m": ["a190", "ak630"], "peykaap": ["kowsar"],
    "arleigh_burke": ["mk45", "sm2", "essm", "phalanx", "mk54"], "type052d": ["ak130", "hq9"],
    "sovremenny": ["ak130", "shtil"], "ticonderoga": ["mk45", "sm2", "phalanx", "mk54"],
    "nimitz": ["essm", "ram", "phalanx"], "gerald_ford": ["essm", "ram", "phalanx"], "kuznetsov": [],
    "charles_de_gaulle": ["aster", "mistral"], "shandong": [], "capana": ["bofors40"], "san_antonio": ["ram"],
    "wasp": ["essm", "ram", "phalanx"], "mistral_bpc": ["mistral"], "ivan_gren": ["ak630"],
    # submarinos: su torpedo
    "u209": ["sst4"], "kilo636": ["tt53"], "scorpene": ["f21"], "virginia": ["mk48"], "type212": ["dm2a4"],
    # tanques y vehiculos
    "t72b1": ["2a46", "9m119"], "t90a": ["2a46", "9m119"], "m1a2": ["m256", "m2hb"], "leopard2a6": ["l55"],
    "amx30": ["cn105"], "scorpion90": ["cockerill90"], "ztz99a": ["2a46"],
    "bmp3": ["2a70", "2a72"], "bmp2": ["2a42", "konkurs", "pkt"], "btr80a": ["2a72", "pkt"], "m2a3": ["m242", "tow"],
    "stryker": ["m2hb", "mk19"], "m113": ["m2hb"], "lav25": ["m242"], "brdm2": ["kpvt", "pkt"], "tiuna": ["m2hb"],
    "hmmwv": ["m2hb", "mk19", "tow"],
    # artilleria y lanzacohetes
    "msta_s": ["2a64"], "m109a7": ["m284"], "caesar": ["caesar155"], "m777": ["m777"], "d30": ["d30"],
    "nona_svk": ["2a60"], "bm21": ["9m22u"], "bm30": ["9m55"], "himars": ["gmlrs", "atacms"],
    "astros2": ["astros_ss"],
}
# clases que son el arma misma (la foto del modelo ya la muestra): no se les agregan fichas
SIN_FICHAS = ("municion_merodeadora",)


def oriental(modelo_id: str | None) -> bool:
    m = catalogo.MODELOS.get(modelo_id or "")
    return bool(m) and any(p in (m.pais or "").lower() for p in _PAISES_ORIENTALES)


def ficha_ota(codigo: str, modelo_id: str | None = None) -> str | None:
    """Ficha de un codigo de armamento de la OTA en ese modelo de aeronave."""
    propia = OTA_POR_MODELO.get(modelo_id or "", {}).get(codigo)
    if propia:
        return propia
    if codigo in ORIENTAL and oriental(modelo_id):
        return ORIENTAL[codigo]
    return DE_OTA.get(codigo)


def _unicas(ids) -> list[str]:
    vistas, out = set(), []
    for i in ids:
        if i and i in FICHAS and i not in vistas:
            vistas.add(i)
            out.append(i)
    return out


def de_modelo(modelo_id: str) -> list[str]:
    """Fichas de las armas de un modelo del catalogo (en orden)."""
    from app.engine import defensa_aerea, misiles, ota

    m = catalogo.MODELOS.get(modelo_id)
    if m is None:
        return []
    clase = catalogo.CLASES.get(m.clase)
    if m.clase in SIN_FICHAS:
        return []
    if m.clase == "misil_crucero":
        return _unicas([DE_MISIL.get(modelo_id)])
    if modelo_id in POR_MODELO:
        return _unicas(POR_MODELO[modelo_id])
    s = defensa_aerea.SISTEMAS.get(modelo_id)
    if s is not None:
        return _unicas(DE_DA.get(a.id) for a in s.armas)
    if clase is not None and clase.tipo == "aerea":
        return _unicas(ficha_ota(c, modelo_id) for c in ota.armas_de(modelo_id, clase))
    ids = []
    if modelo_id not in misiles.SIN_MISILES and (modelo_id in misiles.MISIL_DEL_LANZADOR
                                                 or (clase is not None and clase.lanza_misiles)):
        ids.append(DE_MISIL.get(misiles.MISIL_DEL_LANZADOR.get(modelo_id, misiles.MODELO)))
    ids += ARMAS_PROPIAS[modelo_id] if modelo_id in ARMAS_PROPIAS else POR_CLASE.get(m.clase, [])
    return _unicas(ids)


def de_clase(clase_id: str) -> list[str]:
    """Fichas de una unidad sin modelo (por su clase)."""
    from app.engine import misiles

    c = catalogo.CLASES.get(clase_id)
    if c is None or clase_id in SIN_FICHAS:
        return []
    ids = [DE_MISIL[misiles.MODELO]] if c.lanza_misiles else []
    return _unicas(ids + POR_CLASE.get(clase_id, []))


# ------------------------------------------------------------------------------------------------- fotos
FOTOS_ARMAS: dict[str, dict] = {}  # ficha -> {"foto", "credito"} (seccion "armas" de referencias.json)


def aplicar_fotos(ruta=None, raiz_static=None) -> list[str]:
    """Lee la seccion "armas" del manifiesto de fotos de referencia. Devuelve las fichas con foto propia."""
    ruta = Path(ruta or catalogo.RUTA_REFERENCIAS)
    raiz = Path(raiz_static or catalogo.RUTA_FOTOS)
    FOTOS_ARMAS.clear()
    if not ruta.is_file():
        return []
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        _log.warning("fotos de armas: no se pudo leer %s: %s", ruta, e)
        return []
    for id_, entrada in ((datos.get("armas") or {}) if isinstance(datos, dict) else {}).items():
        if id_ not in FICHAS:
            _log.warning("fotos de armas: ficha desconocida %r (se ignora)", id_)
            continue
        ref = catalogo._referencia_valida(entrada, f"armas.{id_}", raiz)
        if ref:
            FOTOS_ARMAS[id_] = ref
    return sorted(FOTOS_ARMAS)


def foto(ficha_id: str, _visto=None) -> dict | None:
    """{"foto", "credito"} de la ficha: la propia, o la del modelo, la clase o la ficha que indica foto_de."""
    if ficha_id in FOTOS_ARMAS:
        return FOTOS_ARMAS[ficha_id]
    f = FICHAS.get(ficha_id)
    if f is None or f.foto_de is None:
        return None
    seccion, id_ = f.foto_de
    if seccion == "armas":
        visto = (_visto or set()) | {ficha_id}
        return None if id_ in visto else foto(id_, visto)
    if seccion == "modelos":
        m = catalogo.MODELOS.get(id_)
        if m and m.foto and not m.foto.endswith(".svg") and m.credito:
            return {"foto": m.foto, "credito": dict(m.credito)}
        return None
    ref = catalogo.FOTOS_PROPIAS.get(f"clases:{id_}") or catalogo.FOTOS_CLASE.get(id_)
    return {"foto": ref["foto"], "credito": dict(ref["credito"])} if ref else None


def ficha_dict(f: Ficha) -> dict:
    ref = foto(f.id)
    return {"id": f.id, "nombre": f.nombre, "tipo": f.tipo, "pais": f.pais, "fabricante": f.fabricante,
            "guia": f.guia, "alcance": f.alcance, "velocidad": f.velocidad, "ojiva": f.ojiva, "peso": f.peso,
            "descripcion": f.descripcion, "foto": ref["foto"] if ref else None,
            "credito": ref["credito"] if ref else None}


def publico() -> dict:
    """Para GET /api/catalogo: las fichas con su foto y que armas tiene cada modelo y cada clase."""
    from app.engine import ota

    por_modelo = {m: ids for m in catalogo.MODELOS if (ids := de_modelo(m))}
    por_clase = {c: ids for c in catalogo.CLASES if (ids := de_clase(c))}
    # el codigo de la OTA cambia de ficha segun el modelo (cañon, cohetes, ametralladoras)
    ota_modelo = {}
    for m, modelo in catalogo.MODELOS.items():
        clase = catalogo.CLASES.get(modelo.clase)
        if clase is None or clase.tipo != "aerea":
            continue
        lleva = ota.armas_de(m, clase)
        cambios = {c: f for c in ("CKH", "CKL", "ALP") if c in lleva and (f := ficha_ota(c, m)) != DE_OTA[c]}
        if cambios:
            ota_modelo[m] = cambios
    return {"fichas": {i: ficha_dict(f) for i, f in FICHAS.items()},
            "de_ota": {c: f for c, f in DE_OTA.items() if c in ota.ARMAMENTO}, "ota_modelo": ota_modelo,
            "de_da": DE_DA, "por_modelo": por_modelo, "por_clase": por_clase, "sin_fichas": list(SIN_FICHAS)}


aplicar_fotos()
