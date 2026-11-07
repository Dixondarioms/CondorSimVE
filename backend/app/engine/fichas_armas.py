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
            "oniks": "oniks", "kh35": "kh35", "nsm": "nsm"}
# modelos sin tabla de armas en el simulador (antiaereas de las operaciones historicas)
POR_MODELO = {"s75_sa2": ["v750"], "s125m_sa3": ["5v27"], "kub_sa6": ["3m9"], "s200": ["5v21"],
              "roland2": ["roland"], "crotale": ["r440"], "s60_57mm": ["s60"]}
# clase -> fichas (torpedos y balisticos; los buques y submarinos suman el misil que lanzan)
POR_CLASE = {"torpedo": ["mk48"], "misil_balistico": ["9m723"], "lanzador_balistico": ["9m723"],
             "submarino": ["mk48"], "fragata": ["mk54"], "destructor": ["mk54"]}
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
    if modelo_id in misiles.MISIL_DEL_LANZADOR or (clase is not None and clase.lanza_misiles):
        ids.append(DE_MISIL.get(misiles.MISIL_DEL_LANZADOR.get(modelo_id, misiles.MODELO)))
    ids += POR_CLASE.get(m.clase, [])
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
