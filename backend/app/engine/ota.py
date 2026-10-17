"""Orden de Tareas Aereas (OTA) segun la directiva AV/D 5-47 de la AMB: datos de cada mision (paquete, comandante de
mision, indicativo, codigo de mision, alerta, armamento, IFF y ventana sobre el objetivo) y el documento con sus
lineas: encabezado, asignacion de medios, DATMI, ruta, LOCOB, RECO y mensajes (SPINS).

Formato de cada linea: los campos se separan con "/" y la linea termina con "//"; un dato que no aplica va como "-".
Fechas: DDHH:MMmmmAA en el encabezado (1206:00SEP14) y DDHHMM en las ventanas (120700). Coordenadas ggmmssN-gggmmssW.
Los codigos de mision, aeronave y armamento son los de la directiva (los de las aeronaves que no figuran se forman
con el nombre del modelo). La tabla de misiones del documento esta incompleta: el reconocimiento usa el 33RA de su
linea RECO y las misiones sin codigo (guerra electronica, traslado) van con la sigla OTAN.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from app.engine import calendario, catalogo, geo, relieve, transmisiones

# ---------------------------------------------------------------------------------------------------- codigos
# rol del simulador -> (codigo de conflicto, codigo de paz, nombre en la tabla de la AV/D 5-47)
CODIGOS_MISION = {
    "INTERDICCION": ("1OT", "1AT", "Ataque a objetivos en tierra"),
    "ESCOLTA": ("3EA", "2AA", "Escolta aérea"),
    "CAP": ("4PC", "3AA", "Patrulla aérea de combate"),
    "SEAD": ("5SD", "2AT", "Supresión de defensa"),
    "CAS": ("12AC", "5AT", "Apoyo aéreo cercano"),
    "RECO": ("33RA", "33RA", "Reconocimiento aerofotográfico"),
    "GE": ("EW", "EW", "Guerra electrónica (sigla OTAN)"),
    "TRASLADO": ("TAT", "TAT", "Transporte aéreo táctico (sigla OTAN)"),
    "AAR": ("AAR", "AAR", "Reabastecimiento aéreo (sigla OTAN)"),
    "AEW": ("AEW", "AEW", "Alerta temprana aerotransportada (sigla OTAN)"),
    "CSAR": ("CSAR", "CSAR", "Búsqueda y rescate en combate (sigla OTAN)"),
}
# otras misiones de la tabla, que el instructor o el alumno pueden elegir en lugar del codigo del rol
CODIGOS_OPCIONALES = {
    "INTERDICCION": ["9IP", "10IC", "11RA", "14AA", "17IM"],
    "CAP": ["2BC", "6AE", "7DA", "13CC"],
    "CAS": ["10IC", "11RA", "18DD"],
    "SEAD": ["8DS"],
}
NOMBRE_CODIGO = {
    "1OT": "Ataque a objetivos en tierra", "2BC": "Barrido de caza", "3EA": "Escolta aérea", "4PC": "Patrulla aérea de combate",
    "5SD": "Supresión de defensa", "6AE": "Emboscada aérea", "7DA": "Defensa aeroespacial activa aire-aire",
    "8DS": "Defensa aeroespacial activa superficie-aire", "9IP": "Interdicción en la profundidad",
    "10IC": "Interdicción en el campo de batalla", "11RA": "Reconocimiento armado", "12AC": "Apoyo aéreo cercano",
    "13CC": "Cobertura aérea de columnas o convoyes", "14AA": "Ataque aeronaval", "17IM": "Interdicción marítima",
    "18DD": "Apoyo aéreo directo en desembarcos", "33RA": "Reconocimiento aerofotográfico",
    "EW": "Guerra electrónica", "TAT": "Transporte aéreo táctico", "AAR": "Reabastecimiento aéreo",
    "AEW": "Alerta temprana aerotransportada", "CSAR": "Búsqueda y rescate en combate",
}
RETOS = ("ORO", "PLATA", "CONDOR", "TURPIAL", "ARAGUANEY", "SABANA", "TEPUY", "CAIMAN")
RESPUESTAS = ("DIAMANTE", "ESMERALDA", "TRUENO", "RELAMPAGO", "CEIBA", "MORICHE", "ORINOCO", "JAGUAR")
# modelo -> codigo de aeronave (el de la directiva; los demas, formados con el nombre)
CODIGOS_AERONAVE = {
    "su30": "CMK", "f16": "CFA", "ataque_ligero": "ETA", "helo_transporte": "TMI", "helo_ataque": "ECR",
    "f22": "F22", "f35a": "F35", "f35b": "F35", "fa18ef": "F18", "ea18g": "G18", "b1b": "B1B", "p8a": "P8A",
    "e2d": "E2D", "e3g": "E3G", "rc135": "R35", "ec130h": "E30", "kc135": "K35", "rq170": "Q17", "mq9": "MQ9",
    "mh47g": "H47", "mh60m": "H60", "mh60dap": "D60", "ah6m": "AH6", "mh6m": "MH6", "uav_reco": "UAR",
    "uav_armado": "UAA", "merodeadora": "MER", "lucas": "LUC", "ge_aereo": "AGE", "caza_embarcado": "CEM",
}


# armamento: codigo -> (nombre, tipo, guiada, alcance_km)
#   tipo: "aa" misil aire-aire | "as" misil aire-superficie | "ar" antirradiacion | "bomba" | "helo" (cañon, cohetes)
ARMAMENTO = {
    "MAA": ("RVV-AE (R-77)", "aa", True, 80), "MAB": ("R-27ER1", "aa", True, 60), "MAC": ("R-27ET1", "aa", True, 50),
    "MAD": ("R-73E", "aa", True, 20), "MPA": ("Python 4", "aa", True, 15), "MPB": ("AIM-9L", "aa", True, 15),
    "M120": ("AIM-120 AMRAAM", "aa", True, 75), "M9X": ("AIM-9X", "aa", True, 25),
    "MA1": ("Kh-29L", "as", True, 10), "MA2": ("Kh-31A", "as", True, 50), "MA3": ("Kh-31P (antirradiación)", "ar", True, 110),
    "MA4": ("Kh-29TE", "as", True, 30), "MA5": ("Kh-59ME", "as", True, 115),
    "HRM": ("AGM-88 HARM (antirradiación)", "ar", True, 100), "JSW": ("AGM-154 JSOW", "as", True, 110),
    "HLF": ("AGM-114 Hellfire", "as", True, 8),
    "BKR": ("KAB-500KR (guiada TV)", "bomba", True, 9), "BOD": ("KAB-500OD (aire-combustible)", "bomba", False, 0),
    "BRK": ("KAB-1500KR (guiada TV)", "bomba", True, 9), "BMK": ("Mk 82 (227 kg)", "bomba", False, 0),
    "BKM": ("Mk 84 (907 kg)", "bomba", False, 0), "BGB": ("GBU-10 (láser)", "bomba", True, 12),
    "BBU": ("GBU-12 (láser)", "bomba", True, 12), "BTK": ("NATAK", "bomba", False, 0),
    "JDM": ("GBU-31 JDAM", "bomba", True, 24),
    "CKH": ("Cañón", "helo", False, 2), "CKL": ("Cohetes", "helo", False, 6), "ALP": ("Ametralladoras laterales", "helo", False, 1),
}
_ORIENTAL = {"aa": ["MAA", "MAB", "MAC", "MAD"], "sup": ["MA1", "MA2", "MA3", "MA4", "MA5", "BKR", "BOD", "BRK"]}
_OCCIDENTAL = {"aa": ["M120", "M9X", "MPB"], "sup": ["HRM", "JSW", "BGB", "BBU", "JDM", "BMK", "BKM"]}
ARMAMENTO_POR_MODELO = {
    "su30": _ORIENTAL["aa"] + _ORIENTAL["sup"],
    "f16": ["MPA", "MPB", "M120", "M9X", "BMK", "BKM", "BGB", "BBU", "HRM"],
    "ataque_ligero": ["MPB", "BMK", "BTK", "CKL"],
    "caza_embarcado": _OCCIDENTAL["aa"] + _OCCIDENTAL["sup"],
    "f22": ["M120", "M9X", "JDM"], "f35a": ["M120", "M9X", "JDM", "BBU", "JSW", "HRM"],
    "f35b": ["M120", "M9X", "JDM", "BBU"], "fa18ef": _OCCIDENTAL["aa"] + _OCCIDENTAL["sup"],
    "ea18g": ["M120", "HRM"], "b1b": ["JDM", "BMK", "BKM", "JSW"], "p8a": ["JDM", "BMK"],
    "mq9": ["HLF", "BBU"], "uav_armado": ["HLF", "BBU"],
    "helo_ataque": ["CKH", "CKL", "HLF"], "helo_transporte": ["CKH", "CKL", "ALP"],
    "mh60dap": ["CKH", "CKL", "HLF"], "ah6m": ["CKH", "CKL", "HLF"], "mh60m": ["ALP"], "mh6m": ["ALP"], "mh47g": ["ALP"],
}
# efecto del armamento en el ataque (multiplica la potencia de fuego del grupo)
FACTOR_GUIADA = 1.15  # una bomba o un misil guiado contra un blanco fijo o de superficie
FACTOR_ANTIRRADIACION = 1.3  # un misil antirradiacion contra un radar o una antiaerea que emite
FACTOR_AA_LARGO = 1.1  # misil aire-aire de mas de 50 km en una intercepcion

TIPOS_OPERACION = ("ENT", "REA")
ALERTAS = (1, 2, 3)
FUNCIONES = ("CM", "ACM", "-")
MAX_PAQUETE = 16
VIGENCIA_TURNOS = 24  # la OTA cubre un dia de operaciones (ciclo de 24 h)
ESPERA_REUNION_MAX = 2  # turnos que un grupo espera a los demas del paquete en el punto de reunion

PERFIL_FT = {"alto": 20000, "medio": 5000, "rasante": 200}  # altitud aproximada de cada perfil (pies)


def armamento_publico() -> dict:
    return {
        "armamento": {k: {"nombre": n, "tipo": t, "guiada": g, "alcance_km": a} for k, (n, t, g, a) in ARMAMENTO.items()},
        "por_modelo": ARMAMENTO_POR_MODELO, "codigos_mision": {r: list(c[:2]) for r, c in CODIGOS_MISION.items()},
        "codigos_opcionales": CODIGOS_OPCIONALES, "nombre_codigo": NOMBRE_CODIGO, "funciones": list(FUNCIONES),
        "alertas": list(ALERTAS), "perfil_ft": PERFIL_FT,
    }


def armas_de(modelo_id: str | None, clase=None) -> list[str]:
    """Armamento que puede llevar el modelo (si no esta en la lista, el de su clase: aire-aire y/o superficie)."""
    if modelo_id in ARMAMENTO_POR_MODELO:
        return ARMAMENTO_POR_MODELO[modelo_id]
    if clase is None:
        return []
    out = []
    if clase.ataque_vs.get("aerea", 0) > 0:
        out += _OCCIDENTAL["aa"]
    if max(clase.ataque_vs.get("terrestre", 0), clase.ataque_vs.get("naval", 0)) > 0:
        out += ["BMK", "BBU"]
    return out


def codigo_aeronave(modelo_id: str | None) -> str:
    if modelo_id in CODIGOS_AERONAVE:
        return CODIGOS_AERONAVE[modelo_id]
    m = catalogo.MODELOS.get(modelo_id or "")
    letras = "".join(c for c in (m.nombre if m else modelo_id or "XXX").upper() if c.isalnum())
    return (letras + "XXX")[:3]


def codigo_mision(rol: str, tipo_operacion: str = "ENT", elegido: str | None = None) -> str:
    if elegido and (elegido in NOMBRE_CODIGO):
        return elegido
    c = CODIGOS_MISION.get(rol)
    if c is None:
        return "-"
    return c[0]  # el ejemplo de la directiva usa el codigo de conflicto aun en una OTA de entrenamiento


# ---------------------------------------------------------------------------------------------------- datos OTA
def datos(m) -> dict:
    try:
        d = json.loads(getattr(m, "ota_json", None) or "{}")
    except ValueError:
        d = {}
    return d if isinstance(d, dict) else {}


def validar(rol: str, modelo_id: str | None, clase, ota: dict) -> list[str]:
    """Errores de los datos OTA de una mision (armamento que no lleva o que no sirve para el rol, IFF, alerta)."""
    errores = []
    armas = armas_de(modelo_id, clase)
    for campo, titulo in (("armamento_primario", "primario"), ("armamento_secundario", "secundario")):
        a = ota.get(campo)
        if not a:
            continue
        if a not in ARMAMENTO:
            errores.append(f"Armamento {titulo} desconocido: {a}.")
        elif armas and a not in armas:
            errores.append(f"{ARMAMENTO[a][0]} no es armamento de esta aeronave (armamento {titulo}).")
    p = ota.get("armamento_primario")
    if p in ARMAMENTO:
        tipo = ARMAMENTO[p][1]
        if rol in ("CAP", "ESCOLTA") and tipo != "aa":
            errores.append(f"Para {rol} el armamento primario debe ser un misil aire-aire.")
        if rol in ("INTERDICCION", "CAS", "SEAD") and tipo == "aa":
            errores.append(f"Para {rol} el armamento primario debe ser aire-superficie (misil, bomba o cohetes).")
    iff = str(ota.get("iff") or "")
    if iff and not (len(iff) == 5 and iff.isdigit() and iff[0] in "123" and all(c in "01234567" for c in iff[1:])):
        errores.append("El IFF lleva el modo (1, 2 o 3) y el código de 4 dígitos octales (0 a 7), p. ej. 31701.")
    if ota.get("funcion", "-") not in FUNCIONES:
        errores.append("La función en el paquete es CM (comandante de misión), ACM (alterno) o ninguna.")
    if ota.get("funcion") in ("CM", "ACM") and not ota.get("paquete"):
        errores.append("El comandante de misión (CM) y su alterno (ACM) se designan dentro de un paquete.")
    return errores


def errores_del_paquete(db, escenario_id: int, bando: str, ota: dict, excluir_id: int | None = None) -> list[str]:
    """Un paquete tiene un solo comandante de mision (CM) y un solo alterno (ACM), y hasta MAX_PAQUETE misiones."""
    from app.models.mision import Mision  # importacion tardia: evita un ciclo

    paquete = (ota.get("paquete") or "").strip().upper()
    if not paquete:
        return []
    otras = [m for m in db.query(Mision).filter(Mision.escenario_id == escenario_id, Mision.bando == bando,
                                                Mision.estado.in_(("programada", "en_curso")))
             if m.id != excluir_id and (datos(m).get("paquete") or "").upper() == paquete]
    errores = []
    if len(otras) >= MAX_PAQUETE:
        errores.append(f"El paquete {paquete} ya tiene {MAX_PAQUETE} misiones.")
    for f, nombre in (("CM", "comandante de misión"), ("ACM", "alterno del comandante")):
        if ota.get("funcion") == f:
            ya = next((m for m in otras if datos(m).get("funcion") == f), None)
            if ya is not None:
                errores.append(f"El paquete {paquete} ya tiene {nombre}: la misión M{ya.id}.")
    return errores


def factor_ataque(atacante, blanco) -> float:
    """Efecto del armamento elegido para la mision sobre la potencia de fuego del grupo."""
    a = ARMAMENTO.get(getattr(atacante, "arma_elegida", None) or "")
    if a is None or getattr(atacante, "tipo", "") != "aerea":
        return 1.0
    _, tipo, guiada, alcance = a
    if blanco.tipo == "aerea" and not getattr(blanco, "en_tierra", False):
        return FACTOR_AA_LARGO if tipo == "aa" and alcance > 50 else 1.0
    if tipo == "ar":
        from app.engine import guerra_electronica as ge_mod  # importacion tardia

        return FACTOR_ANTIRRADIACION if ge_mod.emite_radar(blanco) else 1.0
    return FACTOR_GUIADA if guiada and tipo in ("as", "bomba") else 1.0


# ---------------------------------------------------------------------------------------------------- ruta
def rumbo(lat1, lon1, lat2, lon2) -> int:
    """Rumbo verdadero (grados, 0-359) de un tramo."""
    f1, f2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(f2)
    y = math.cos(f1) * math.sin(f2) - math.sin(f1) * math.cos(f2) * math.cos(dl)
    return int(round(math.degrees(math.atan2(x, y)))) % 360


def tramos(lat, lon, puntos: list, perfil_inicial: str | None) -> list[dict]:
    """Rumbo, distancia y perfil (altitud) de cada tramo de la ruta. El perfil de un tramo es el del punto al que va;
    si el punto no lo indica, sigue el anterior."""
    out, prev, perfil = [], (lat, lon), perfil_inicial
    for p in puntos:
        perfil = p.get("perfil") or perfil
        d = geo.distancia_km(prev[0], prev[1], p["lat"], p["lon"])
        out.append({"rumbo": rumbo(prev[0], prev[1], p["lat"], p["lon"]), "nm": round(d / 1.852, 1), "perfil": perfil,
                    "altitud_ft": PERFIL_FT.get(perfil)})
        prev = (p["lat"], p["lon"])
    return out


def turno_de_despegue_para_tot(tot_turno: int, llegada_h: float) -> int:
    """Turno de despegue para estar sobre el blanco en el turno del TOT (cada turno es una hora)."""
    return tot_turno - int(math.floor(llegada_h + 1e-9))


# ---------------------------------------------------------------------------------------------------- formato
_MESES = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
_MESES_ES = ("ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC")


def momento(esc, turno: int, minutos: int = 0) -> datetime:
    """Fecha y hora del inicio de un turno (o unos minutos despues). Sin fecha de inicio en el escenario, el dia de
    hoy es el del turno 1."""
    fh = calendario.fecha_hora(esc, turno)
    if fh is None:
        hoy = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        fh = hoy + timedelta(minutes=(esc.hora_inicio_min or 0) + (max(1, turno) - 1) * 60)
    return fh + timedelta(minutes=minutos)


def f_encabezado(dt: datetime) -> str:
    """DDHH:MMmmmAA (1206:00SEP14)."""
    return f"{dt.day:02d}{dt.hour:02d}:{dt.minute:02d}{_MESES_ES[dt.month - 1]}{dt.year % 100:02d}"


def f_ventana(dt: datetime) -> str:
    """DDHHMM (120700)."""
    return f"{dt.day:02d}{dt.hour:02d}{dt.minute:02d}"


def f_alerta(dt: datetime) -> str:
    """H06M20."""
    return f"H{dt.hour:02d}M{dt.minute:02d}"


def f_coord(lat: float, lon: float) -> str:
    """ggmmssN-gggmmssW como en el ejemplo de la directiva (104527N-673612W; 3 cifras solo desde 100 grados)."""
    def gms(v, ancho):
        v = abs(v)
        g = int(v)
        m = int((v - g) * 60)
        s = int(round(((v - g) * 60 - m) * 60))
        if s == 60:
            m, s = m + 1, 0
        if m == 60:
            g, m = g + 1, 0
        return f"{g:0{ancho}d}{m:02d}{s:02d}"
    return f"{gms(lat, 2)}{'N' if lat >= 0 else 'S'}-{gms(lon, 2)}{'W' if lon < 0 else 'E'}"


def codigo_lugar(nombre: str) -> str:
    """Codigo de 4 letras de una base o un punto (las iniciales y consonantes de su nombre)."""
    limpio = "".join(c for c in (nombre or "").upper() if c.isalnum() or c == " ")
    palabras = [p for p in limpio.split() if p not in ("BASE", "AEREA", "AÉREA", "DE", "LA", "EL", "DEL", "BA", "AEROPUERTO")]
    texto = "".join(palabras) or limpio.replace(" ", "") or "XXXX"
    return (texto + "XXXX")[:4]


INDICE_AERODROMOS = Path(__file__).resolve().parents[3] / "frontend" / "static" / "geo" / "aerodromos" / "indice.json"
RADIO_OACI_KM = 6.0


@lru_cache(maxsize=1)
def _oaci() -> tuple:
    try:
        datos = json.loads(INDICE_AERODROMOS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    return tuple((b["lat"], b["lon"], b["icao"]) for b in datos.get("bases", [])
                 if b.get("lat") is not None and len(str(b.get("icao") or "")) == 4 and str(b["icao"]).isalpha())


def codigo_base(base) -> str:
    """Codigo OACI del aerodromo donde esta la base (SVFM); si no hay uno cerca, el formado con su nombre."""
    if base is None:
        return "-"
    cerca = [(geo.distancia_km(base.lat, base.lon, a, b), c) for a, b, c in _oaci()
             if abs(a - base.lat) < 0.1 and abs(b - base.lon) < 0.1]
    cerca = [x for x in cerca if x[0] <= RADIO_OACI_KM]
    return min(cerca)[1] if cerca else codigo_lugar(base.nombre)


def linea(*campos) -> str:
    return " / ".join("-" if c in (None, "") else str(c) for c in campos) + " //"


# ---------------------------------------------------------------------------------------------------- documento
def lineas_ota(db, esc, bando: str, misiones: list, unidades: dict, nombre_operacion: str, emisor: str = "CAO",
               tipo_operacion: str = "ENT") -> dict:
    """Lineas de la OTA del bando: {encabezado, asignacion, misiones: [{datmi, ruta, locob, reco, ...}], spins}."""
    desde_turno = esc.turno_actual
    hasta_turno = desde_turno + VIGENCIA_TURNOS
    validez = f"{bando[0].upper()}-{momento(esc, desde_turno).day:02d}"
    encabezado = linea(tipo_operacion, validez, (nombre_operacion or esc.nombre).upper().replace("/", "-")[:30], emisor,
                       f_encabezado(momento(esc, desde_turno)), f_encabezado(momento(esc, hasta_turno)))
    ms = sorted(misiones, key=lambda m: (m.turno_despegue, m.id))
    # asignacion de medios: una linea por unidad (grupo aereo) y base, con su funcion en el paquete
    asignacion, vistos = [], {}
    for m in ms:
        o = datos(m)
        base = unidades.get(m.base_id) if m.base_id else None
        grupo = unidades.get(m.unidad_id) if m.unidad_id else None
        if base is None and grupo is not None:
            base = unidades.get(getattr(grupo, "base_id", None)) if getattr(grupo, "base_id", None) else None
        unidad = o.get("unidad") or _unidad_aerea(m, grupo, base, unidades)
        clave = (unidad, base.id if base else None, m.modelo, o.get("funcion", "-"))
        if clave in vistos:
            vistos[clave][2] += m.aeronaves or 0
            continue
        fila = [unidad.upper()[:20], codigo_base(base), m.aeronaves or 0,
                codigo_aeronave(m.modelo), o.get("funcion") or "-"]
        vistos[clave] = fila
        asignacion.append(fila)
    asignacion_txt = [linea(u, b, f"{n:03d}", c, f) for u, b, n, c, f in asignacion]

    filas = []
    mes = momento(esc, desde_turno).month
    for i, m in enumerate(ms, 1):
        o = datos(m)
        pts = json.loads(m.puntos_json or "[]")
        plan = json.loads(m.plan_json or "{}")
        numero = f"A{mes:02d}{i:02d}"
        paquete = (o.get("paquete") or "").strip().upper()
        indicativo = (m.nombre or o.get("indicativo") or f"M{m.id}").upper().replace("/", "-")
        despegue = momento(esc, m.turno_despegue)
        datmi = linea("DATMI", numero, f"P{paquete}" if paquete else f"I{indicativo[:8]}", indicativo[:16],
                      f"{m.aeronaves or 0:02d}{codigo_aeronave(m.modelo)}", codigo_mision(m.rol, tipo_operacion, o.get("codigo")),
                      f_alerta(despegue - timedelta(minutes=30)), f_alerta(despegue), o.get("alerta") or 1,
                      o.get("armamento_primario"), o.get("armamento_secundario"), o.get("iff"))
        # ruta: salida / ingreso / corredor / egreso / reabastecimiento aereo / aterrizaje
        g = unidades.get(m.unidad_id) if m.unidad_id else None
        salida = unidades.get(m.base_id) if m.base_id else (unidades.get(g.base_id) if g is not None and g.base_id else None)
        nombres, n_paso, n_orb, n_bl = [], 0, 0, 0
        for p in pts:
            if p["tipo"] == "aterrizaje":
                continue
            if p.get("reunion"):
                nombres.append("RV" + str(len([x for x in nombres if x.startswith("RV")]) + 1))
            elif p["tipo"] == "orbita":
                n_orb += 1
                nombres.append(f"ORB{n_orb}")
            elif p["tipo"] == "blanco":
                n_bl += 1
                x = unidades.get(p.get("objetivo_unidad_id")) if p.get("objetivo_unidad_id") else None
                nombres.append(codigo_lugar(x.nombre) if x else f"OBJ{n_bl}")
            else:
                n_paso += 1
                nombres.append(f"P{n_paso}")
        aterr = next((unidades.get(p.get("base_id")) for p in pts if p["tipo"] == "aterrizaje"), None)
        aer = next((n for n, p in zip(nombres, [q for q in pts if q["tipo"] != "aterrizaje"]) if p.get("reabastecimiento")), None)
        ruta = linea(codigo_base(salida) if salida is not None else "EN VUELO", nombres[0] if nombres else "-",
                     "-".join(nombres[1:-1]) if len(nombres) > 2 else "-", nombres[-1] if len(nombres) > 1 else "-",
                     f"{aer} (AER)" if aer else "-", codigo_base(aterr) if aterr else "-")
        # LOCOB: ventana sobre cada blanco (el turno en que llega) y sus coordenadas
        locob, reco, n_pdi = [], [], 0
        for p, est in zip(pts, plan.get("puntos") or []):
            if p["tipo"] != "blanco":
                continue
            n_pdi += 1
            t_tot = int(o.get("tot_turno") or (m.turno_despegue + int(math.floor(est.get("llegada_h", 0) + 1e-9))))
            ini = momento(esc, t_tot)
            x = unidades.get(p.get("objetivo_unidad_id")) if p.get("objetivo_unidad_id") else None
            locob.append(linea("LOCOB", f_ventana(ini), f_ventana(ini + timedelta(minutes=59)),
                               (x.nombre if x else "OBJETIVO DE OPORTUNIDAD").upper()[:24], o.get("altura_objetivo"),
                               f_coord(p["lat"], p["lon"]), o.get("pdi") or f"PDI{n_pdi:02d}"))
        if m.rol == "RECO":
            primero = next((p for p in pts if p["tipo"] in ("orbita", "paso")), None)
            if primero is not None:
                llegada = float(((plan.get("puntos") or [{}])[0]).get("llegada_h", 0))
                reco.append(linea("RECO", f"{codigo_base(salida) if salida is not None else 'GRP'}{i:02d}",
                                  f_ventana(despegue + timedelta(hours=llegada)), f_coord(primero["lat"], primero["lon"]),
                                  "33RA", codigo_base(aterr) if aterr else "-", "01"))
        # ABA: reabastecimiento en vuelo (AER) en el punto marcado y en tierra (TER) si aterriza en un PRO
        aba = []
        k_aer = next((k for k, p in enumerate(pts) if p.get("reabastecimiento")), None)
        reto, resp = RETOS[(m.id * 7) % len(RETOS)], RESPUESTAS[(m.id * 5) % len(RESPUESTAS)]
        cant = f"{m.aeronaves or 0:02d}{codigo_aeronave(m.modelo)}"
        if k_aer is not None and k_aer < len(plan.get("puntos") or []):
            ini = despegue + timedelta(hours=float(plan["puntos"][k_aer]["llegada_h"]))
            kg = (plan.get("aar") or {}).get("kg")
            nombre_aer = nombres[[q for q in pts if q["tipo"] != "aterrizaje"].index(pts[k_aer])] if pts[k_aer]["tipo"] != "aterrizaje" else "AER"
            aba.append(linea("ABA", cant, "AER", f_ventana(ini), f_ventana(ini + timedelta(minutes=59)), f"{nombre_aer}+AER",
                             f_coord(pts[k_aer]["lat"], pts[k_aer]["lon"]), reto, resp, f"{kg}K JP1" if kg else None))
        if aterr is not None and (aterr.clase or "") == "punto_recobre" and plan.get("puntos"):
            pros = sorted(x.id for x in unidades.values() if (x.clase or "") == "punto_recobre" and x.bando == m.bando)
            ini = despegue + timedelta(hours=float(plan["puntos"][-1]["llegada_h"]))
            aba.append(linea("ABA", cant, "TER", f_ventana(ini), f_ventana(ini + timedelta(hours=1, minutes=59)),
                             f"PR{pros.index(aterr.id) + 1:02d}", f_coord(aterr.lat, aterr.lon), reto, resp, None))
        filas.append({"mision_id": m.id, "numero": numero, "rol": m.rol, "paquete": paquete, "funcion": o.get("funcion") or "-",
                      "indicativo": indicativo, "datmi": datmi, "ruta": ruta, "locob": locob, "reco": reco,
                      "aba": aba,
                      "despegue": despegue.strftime("%H:%M"), "tot": o.get("tot_turno")})
    return {"encabezado": encabezado, "asignacion": asignacion_txt, "misiones": filas, "spins": spins(esc, ms, bando)}


def _unidad_aerea(m, grupo, base, unidades: dict) -> str:
    """Unidad (grupo aereo o escuadrilla) que aporta los medios: la del grupo que vuela la mision o la escuadrilla
    propia del mismo modelo (la mas cercana a la base de despegue); si no hay, el grupo aereo de la base."""
    if grupo is not None:
        return grupo.nombre
    mismas = [u for u in unidades.values() if u.bando == m.bando and u.tipo == "aerea" and u.modelo == m.modelo
              and u.estado != "destruida"]
    if mismas and base is not None:
        return min(mismas, key=lambda u: geo.distancia_km(base.lat, base.lon, u.lat, u.lon)).nombre
    return f"GA {codigo_base(base)}" if base is not None else "-"


def spins(esc, misiones: list, bando: str = "azul") -> list[str]:
    """Linea de mensajes (SPINS): informacion general, procedimientos y medidas de coordinacion del dia."""
    paquetes = sorted({(datos(m).get("paquete") or "").upper() for m in misiones} - {""})
    cms = [f"{(datos(m).get('paquete') or '').upper()}: M{m.id} {m.nombre or ''}".strip()
           for m in misiones if datos(m).get("funcion") == "CM"]
    out = [
        "INFORMACIÓN GENERAL: OTA de ejercicio generada por el S.I.E.T.E.; cada turno del simulador es una hora.",
        "BLOQUES DE ALTURA: alta performance FL120 a FL210; baja performance FL040 a FL110. Desconflicto: 1000 ft o 5 NM.",
        "ESCOLTA: entra 5 min antes que el primer atacante y sale no menos de 10 NM detrás del último. "
        "Ventana sobre el blanco no menor de 5 min.",
        f"PAQUETES: {', '.join(paquetes) if paquetes else 'ninguno'}. Comandantes de misión: {'; '.join(cms) if cms else 'no designados'}.",
        "PUNTOS DE REUNIÓN (RV): los grupos del paquete se esperan hasta "
        f"{ESPERA_REUNION_MAX} turnos; luego sigue cada uno su ruta.",
        "RECUPERACIÓN DE PERSONAL: tripulación derribada informa posición en la frecuencia de guardia; SAR/CSAR en alerta.",
        "REABASTECIMIENTO: según línea ABA de cada misión; autenticación reto-respuesta antes del contacto.",
        transmisiones.lineas_spins(esc, bando),
    ]
    return out


def bloques(info_lineas: dict) -> list:
    """Bloques del documento (para legajo.word / legajo.pagina)."""
    b = [("h2", "1. Encabezado"), ("mono", info_lineas["encabezado"]),
         ("h2", "2. Asignación de medios"), *[("mono", x) for x in info_lineas["asignacion"] or ["-"]],
         ("h2", "3. Misiones (DATMI, ruta, localización del objetivo, reconocimiento y abastecimiento)")]
    for f in info_lineas["misiones"]:
        b.append(("p_negrita", f"{f['numero']} · M{f['mision_id']} · {f['rol']} · {f['indicativo']}"
                  + (f" · paquete {f['paquete']} ({f['funcion']})" if f["paquete"] else "") + f" · despegue {f['despegue']}"))
        b += [("mono", f["datmi"]), ("mono", f["ruta"])] + [("mono", x) for x in f["locob"] + f["reco"] + f["aba"]]
    if not info_lineas["misiones"]:
        b.append(("p", "Sin misiones programadas o en curso."))
    b.append(("h2", "4. Línea de mensajes (SPINS)"))
    b += [("li", x) for x in info_lineas["spins"]]
    b.append(("h2", "Leyenda"))
    b += [("li", "DATMI: número / paquete (P) o individual (I) / indicativo / cantidad y aeronave / código de misión / "
                 "inicio y fin de la alerta / tipo de alerta / armamento primario / secundario / IFF (modo + código)."),
          ("li", "Ruta: salida / punto de ingreso / puntos del corredor / punto de egreso / reabastecimiento aéreo / aterrizaje."),
          ("li", "LOCOB: inicio y fin de la ventana sobre el objetivo / objetivo / altura / coordenadas / PDI.")]
    return b


def perfil_valido(clase_id: str | None, tipo: str, perfil: str | None) -> bool:
    if not perfil:
        return True
    from types import SimpleNamespace

    return perfil in relieve.perfiles_permitidos(SimpleNamespace(tipo=tipo, clase=clase_id, modelo=None))
