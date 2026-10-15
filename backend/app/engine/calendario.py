"""Calendario de la operacion (TIEM): dia D, hora H y fases de la operacion.

Cada turno dura 1 h simulada; el turno 1 empieza a `hora_inicio_min` del dia `fecha_inicio`. La hora H cae en el
turno `turno_h` y el dia D es el dia de ese turno. Las referencias se escriben como en las ordenes: D-1, D, D+2 para
los dias y H-3, H, H+12 para las horas. Las fases de la operacion (alistamiento, concentracion y despliegue,
ejecucion y repliegue) se fijan en turnos; si el instructor no las define, se arman solas a partir de H y del
ultimo turno previsto. Todo es opcional: un escenario sin hora H ni fecha no muestra calendario.
"""

import json
from datetime import date, datetime, timedelta

FASES_OPERACION = ("Alistamiento", "Concentracion y despliegue", "Ejecucion", "Repliegue")
MAX_FASES = 8


def _dia_indice(esc, turno: int) -> int:
    """Dias transcurridos desde el dia del turno 1 hasta el del turno indicado."""
    return ((esc.hora_inicio_min or 0) + (max(1, turno) - 1) * 60) // 1440


def fecha_hora(esc, turno: int) -> datetime | None:
    """Fecha y hora simuladas en que empieza el turno (None si el escenario no tiene fecha de inicio)."""
    if not esc.fecha_inicio:
        return None
    try:
        inicio = date.fromisoformat(esc.fecha_inicio)
    except ValueError:
        return None
    return datetime(inicio.year, inicio.month, inicio.day) + timedelta(minutes=(esc.hora_inicio_min or 0) + (max(1, turno) - 1) * 60)


def _relativo(letra: str, n: int) -> str:
    return letra if n == 0 else f"{letra}{n:+d}"


def fases_por_defecto(turno_h: int | None, turno_final: int | None) -> list[dict]:
    """Alistamiento y concentracion antes de H, ejecucion desde H y repliegue en los dos ultimos turnos."""
    if not turno_h:
        return []
    h = max(1, int(turno_h))
    conc = min(2, h - 1)
    fases = []
    if h - 1 - conc >= 1:
        fases.append({"nombre": FASES_OPERACION[0], "desde": 1, "hasta": h - 1 - conc})
    if conc:
        fases.append({"nombre": FASES_OPERACION[1], "desde": h - conc, "hasta": h - 1})
    repliegue = 2 if turno_final and turno_final - h >= 6 else 0
    fases.append({"nombre": FASES_OPERACION[2], "desde": h, "hasta": (turno_final - repliegue) if turno_final else None})
    if repliegue:
        fases.append({"nombre": FASES_OPERACION[3], "desde": turno_final - repliegue + 1, "hasta": turno_final})
    return fases


def validar_fases(fases) -> list[dict]:
    """Normaliza la lista de fases [{"nombre", "desde", "hasta"}]; lanza ValueError con el motivo si no sirve."""
    if not isinstance(fases, list) or len(fases) > MAX_FASES:
        raise ValueError(f"Indique hasta {MAX_FASES} fases")
    limpias = []
    for f in fases:
        nombre = str((f or {}).get("nombre", "")).strip()[:60]
        desde, hasta = f.get("desde"), f.get("hasta")
        if not nombre or not isinstance(desde, int) or desde < 1:
            raise ValueError("Cada fase necesita un nombre y un turno de inicio (1 o mayor)")
        if hasta is not None and (not isinstance(hasta, int) or hasta < desde):
            raise ValueError(f"La fase {nombre} termina antes de empezar")
        limpias.append({"nombre": nombre, "desde": desde, "hasta": hasta})
    limpias.sort(key=lambda f: f["desde"])
    for a, b in zip(limpias, limpias[1:]):
        if a["hasta"] is None or a["hasta"] >= b["desde"]:
            raise ValueError(f"Las fases {a['nombre']} y {b['nombre']} se superponen")
    return limpias


def fases(esc) -> list[dict]:
    """Fases definidas por el instructor o, si no hay, las de por defecto."""
    if esc.fases_json:
        try:
            return json.loads(esc.fases_json)
        except ValueError:
            pass
    return fases_por_defecto(esc.turno_h, esc.turno_final)


def fase_de(esc, turno: int) -> str:
    for f in fases(esc):
        if f["desde"] <= turno and (f["hasta"] is None or turno <= f["hasta"]):
            return f["nombre"]
    return ""


def referencia(esc, turno: int) -> dict:
    """Como se nombra el turno en el calendario: fecha, hora, dia relativo a D, hora relativa a H y fase."""
    fh = fecha_hora(esc, turno)
    minutos = ((esc.hora_inicio_min or 0) + (max(1, turno) - 1) * 60) % 1440
    ref = {"turno": turno, "fecha": fh.date().isoformat() if fh else None, "hora": f"{minutos // 60:02d}:{minutos % 60:02d}",
           "dia": None, "hora_h": None, "fase": fase_de(esc, turno)}
    if esc.turno_h:
        ref["dia"] = _relativo("D", _dia_indice(esc, turno) - _dia_indice(esc, esc.turno_h))
        ref["hora_h"] = _relativo("H", turno - esc.turno_h)
    return ref


def texto(ref: dict) -> str:
    """"D+1 · H+29 · 10:00 · Ejecucion" (solo las partes que existen)."""
    partes = [ref.get("dia"), ref.get("hora_h"), ref.get("hora"), ref.get("fase")]
    return " · ".join(p for p in partes if p)


def resumen(esc) -> dict | None:
    """Calendario del escenario para la interfaz; None si no tiene hora H ni fecha."""
    if not esc.turno_h and not esc.fecha_inicio:
        return None
    dia_d = hora_h = None
    if esc.turno_h:
        ref_h = referencia(esc, esc.turno_h)
        dia_d, hora_h = ref_h["fecha"], ref_h["hora"]
    return {
        "fecha_inicio": esc.fecha_inicio, "turno_h": esc.turno_h, "turno_final": esc.turno_final,
        "dia_d": dia_d, "hora_h": hora_h, "fases": fases(esc), "fases_propias": bool(esc.fases_json),
        "actual": referencia(esc, esc.turno_actual),
    }
