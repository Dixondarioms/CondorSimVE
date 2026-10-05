"""Renderiza el informe posterior al ejercicio como HTML imprimible (sin JavaScript)
y sus combates como CSV. Todo el texto variable se escapa."""

import csv
import io
from html import escape as e

from app.engine.aar import SIN_AUTOR

BANDO_COLOR = {"azul": "#1e5fa8", "rojo": "#a83232"}

ESTILO = """
body{font:14px/1.45 system-ui,Segoe UI,sans-serif;color:#1b1f24;max-width:960px;margin:24px auto;padding:0 16px}
h1{font-size:24px;margin:0 0 4px}h2{font-size:18px;border-bottom:2px solid #333;padding-bottom:4px;margin-top:28px}
h3{font-size:15px;margin:18px 0 6px}small,.meta{color:#555}
table{border-collapse:collapse;width:100%;margin:6px 0 12px;font-size:13px}
th,td{border:1px solid #bbb;padding:4px 6px;text-align:left;vertical-align:top}th{background:#eee}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.azul{color:#1e5fa8;font-weight:600}.rojo{color:#a83232;font-weight:600}
.rechazada{color:#a83232}.turno{page-break-inside:avoid}
@media print{body{margin:0;max-width:none}h2{page-break-after:avoid}}
"""


def _bando(b: str) -> str:
    return f'<span class="{e(b)}">{e(b)}</span>'


def _tabla(cabecera: list[str], filas: list[list[str]], num: tuple[int, ...] = (), cabecera_html: bool = False) -> str:
    """Las celdas llegan ya escapadas (o con HTML propio); la cabecera se escapa salvo `cabecera_html`."""
    if not filas:
        return "<p class='meta'>Sin registros.</p>"
    th = "".join(f"<th>{c if cabecera_html else e(c)}</th>" for c in cabecera)
    tr = "".join(
        "<tr>" + "".join(
            f"<td class='num'>{c}</td>" if i in num else f"<td>{c}</td>" for i, c in enumerate(fila)
        ) + "</tr>"
        for fila in filas
    )
    return f"<table><tr>{th}</tr>{tr}</table>"


def _barras(resumen: dict) -> str:
    """Grafico SVG de fuerza perdida por bando (puntos porcentuales acumulados)."""
    maximo = max([r["fuerza_perdida"] for r in resumen.values()] + [1.0])
    filas = []
    for i, (b, r) in enumerate(resumen.items()):
        y = 10 + i * 34
        ancho = 520 * r["fuerza_perdida"] / maximo
        filas.append(
            f'<text x="0" y="{y + 15}" font-size="13">{e(b)}</text>'
            f'<rect x="60" y="{y}" width="{ancho:.1f}" height="22" fill="{BANDO_COLOR.get(b, "#666")}"/>'
            f'<text x="{66 + ancho:.1f}" y="{y + 16}" font-size="12">{r["fuerza_perdida"]:.1f}</text>'
        )
    return f'<svg viewBox="0 0 640 {20 + 34 * len(resumen)}" width="100%" role="img" aria-label="Fuerza perdida por bando">{"".join(filas)}</svg>'


def _motivos(o: dict) -> str:
    return "; ".join(f'{e(m["motivo"])} ({m["veces"]})' for m in o["motivos_rechazo"]) or "-"


def _filas_alumnos(rubrica: dict) -> list[list[str]]:
    """Una fila por alumno (celdas ya escapadas) mas, por bando, lo que quedo sin autor registrado."""
    filas = [
        [e(a["username"]), _bando(a["bando"]), f'{e(a["sigla"])} · {e(a["puesto_nombre"])}',
         str(a["ordenes"]["emitidas"]), str(a["ordenes"]["resueltas"]), str(a["ordenes"]["rechazadas"]),
         f'{a["turnos_activos"]["cantidad"]} / {a["turnos_pasivos"]["cantidad"]}',
         str(a["misiones"]["planificadas"]), " ".join(e(o) for o in a["observaciones"])]
        for a in rubrica.get("alumnos") or []
    ]
    for b, n in (rubrica.get("sin_autor") or {}).items():
        if n["ordenes"] or n["misiones"]:
            filas.append([f"<i>{e(SIN_AUTOR)}</i>", _bando(b), "-", str(n["ordenes"]), "-", "-", "-",
                          str(n["misiones"]), "Ordenes o misiones anteriores al registro del autor."])
    return filas


def _rubrica_html(rubrica: dict | None) -> str:
    """Seccion 'Rubrica de evaluacion': una tabla de indicadores por bando, el desglose por puesto responsable,
    las observaciones automaticas y la evaluacion por alumno."""
    if not rubrica:
        return ""
    bandos = rubrica["bandos"]
    filas = []
    etiquetas = [
        ("Ordenes emitidas / resueltas / rechazadas",
         lambda x: f'{x["ordenes"]["emitidas"]} / {x["ordenes"]["resueltas"]} / {x["ordenes"]["rechazadas"]}'),
        ("Motivos de rechazo mas frecuentes",
         lambda x: "; ".join(f'{e(m["motivo"])} ({m["veces"]})' for m in x["ordenes"]["motivos_rechazo"]) or "-"),
        ("Turnos pasivos (sin ninguna orden)",
         lambda x: str(x["turnos_pasivos"]["cantidad"])
         + (" (turnos " + ", ".join(str(t) for t in x["turnos_pasivos"]["turnos"]) + ")" if x["turnos_pasivos"]["turnos"] else "")),
        (f'Unidades bajo el {rubrica["umbral_critico"]:.0f} % de combustible o municion',
         lambda x: ", ".join(f'{e(c["unidad"])} ({"/".join(c["variables"])} {c["minimo"]:.0f} %, turno {c["turno"]})'
                             for c in x["logistica"]["unidades_criticas"]) or "ninguna"),
        ("Reabastecimientos realizados", lambda x: str(x["logistica"]["reabastecimientos"])),
        ("Perdidas infligidas / sufridas (pts)",
         lambda x: f'{x["perdidas"]["infligidas"]:.1f} / {x["perdidas"]["sufridas"]:.1f}'),
        ("Unidades destruidas propias / enemigas",
         lambda x: f'{x["perdidas"]["unidades_destruidas"]} / {x["perdidas"]["enemigas_destruidas"]}'),
        ("Objetivos cumplidos / fallidos / pendientes",
         lambda x: f'{x["objetivos"]["cumplidos"]} / {x["objetivos"]["fallidos"]} / {x["objetivos"]["pendientes"]}'
         + f' ({x["objetivos"]["puntos"]} pts)'),
        ("Misiones aereas cumplidas / abortadas / fallidas (de N planificadas)",
         lambda x: f'{x["misiones"]["cumplidas"]} / {x["misiones"]["abortadas"]} / {x["misiones"]["fallidas"]}'
         f' (de {x["misiones"]["planificadas"]})'),
    ]
    for etiqueta, f in etiquetas:
        filas.append([e(etiqueta)] + [f(bandos[b]) for b in bandos])
    tabla = _tabla(["Indicador"] + [_bando(b) for b in bandos], filas, cabecera_html=True)

    partes = [f"<h2>Rubrica de evaluacion</h2>{tabla}"]
    for b, x in bandos.items():
        partes.append(f"<h3>Observaciones para {_bando(b)}</h3><ul>"
                      + "".join(f"<li>{e(o)}</li>" for o in x["observaciones"]) + "</ul>")
        puestos_filas = [
            [f'{e(pu["sigla"])} · {e(pu["nombre"])}', str(pu["ordenes"]["emitidas"]), str(pu["ordenes"]["resueltas"]),
             str(pu["ordenes"]["rechazadas"]), str(pu["misiones"]), _motivos(pu["ordenes"])]
            for pu in x["puestos"].values() if pu["ordenes"]["emitidas"] or pu["misiones"]
        ]
        if puestos_filas:
            partes.append(f"<h3>Por puesto responsable ({_bando(b)})</h3>" + _tabla(
                ["Puesto", "Ordenes", "Resueltas", "Rechazadas", "Misiones", "Motivos de rechazo"], puestos_filas,
                num=(1, 2, 3, 4)))
    partes.append(f'<p class="meta">{e(rubrica["nota_puestos"])}</p>')
    filas_alumnos = _filas_alumnos(rubrica)
    if filas_alumnos:
        partes.append("<h3>Evaluacion por alumno</h3>" + _tabla(
            ["Alumno", "Bando", "Puesto", "Ordenes", "Resueltas", "Rechazadas", "Turnos activos / pasivos",
             "Misiones", "Observaciones"], filas_alumnos, num=(3, 4, 5, 7)))
        partes.append(f'<p class="meta">{e(rubrica.get("nota_alumnos", ""))}</p>')
    return "".join(partes)


def render_html(informe: dict, rubrica: dict | None = None) -> str:
    esc = informe["escenario"]
    res = informe["resumen"]
    turnos = informe["turnos"]

    resumen_tabla = _tabla(
        ["Bando", "Unidades", "Destruidas", "Combates iniciados", "Combates recibidos",
         "Fuerza perdida (pts)", "Daño infligido (pts)", "Ordenes", "Rechazadas"],
        [[_bando(b), str(r["unidades"]), str(r["destruidas"]), str(r["combates_iniciados"]),
          str(r["combates_recibidos"]), f'{r["fuerza_perdida"]:.1f}', f'{r["dano_infligido"]:.1f}',
          str(r["ordenes_emitidas"]), str(r["ordenes_rechazadas"])] for b, r in res.items()],
        num=(1, 2, 3, 4, 5, 6, 7, 8),
    )

    secciones = []
    for t in turnos:
        if t["turno"] == 0 and not t["combates"] and not t["ordenes"]:
            continue
        partes = [f'<div class="turno"><h3>Turno {t["turno"]}'
                  + (" <small>(sin resolver)</small>" if t.get("en_curso") else "")
                  + (f' <small>· clima {e(t["clima"])}</small>' if t["clima"] else "") + "</h3>"]
        if t["eventos"]:
            partes.append("<ul>" + "".join(
                f'<li><b>{e(ev["tipo"])}</b> ({e(ev["bando_destino"])}): {e(ev["descripcion"])}</li>'
                for ev in t["eventos"]) + "</ul>")
        partes.append(_tabla(
            ["Unidad", "Orden", "Objetivo", "Estado", "Resultado"],
            [[e(o["unidad"]), e(o["tipo"]), e(o["objetivo"] or "-"),
              f'<span class="{e(o["estado"])}">{e(o["estado"])}</span>', e(o["resultado"])] for o in t["ordenes"]]))
        if t["combates"]:
            partes.append(_tabla(
                ["Atacante", "Defensor", "Ratio", "Perdida atac.", "Perdida def.", "Terreno", "Efectos"],
                [[f'{e(c["atacante"])} ({_bando(c["atacante_bando"])})',
                  f'{e(c["defensor"])} ({_bando(c["defensor_bando"])})', f'{c["ratio"]:.2f}',
                  f'{c["perdida_atacante"]:.1f}', f'{c["perdida_defensor"]:.1f}', e(c["terreno"]),
                  e(c["efectos"] or "-")] for c in t["combates"]], num=(2, 3, 4)))
        partes.append("</div>")
        secciones.append("".join(partes))

    # estado inicial vs final de cada unidad
    con_unidades = [t for t in turnos if t["unidades"]]
    inicial = {u["id"]: u for u in con_unidades[0]["unidades"]} if con_unidades else {}
    final = con_unidades[-1]["unidades"] if con_unidades else []
    unidades_tabla = _tabla(
        ["Unidad", "Bando", "Clase", "Fuerza inicial", "Fuerza final", "Estado", "Combustible", "Municion"],
        [[e(u["nombre"]), _bando(u["bando"]), e(u.get("clase") or u["tipo"]),
          f'{inicial.get(u["id"], u)["fuerza"]:.0f}%', f'{u["fuerza"]:.0f}%', e(u["estado"]),
          f'{u["combustible"]:.0f}%', f'{u["municion"]:.0f}%'] for u in final],
        num=(3, 4, 6, 7))

    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Informe posterior - {e(esc["nombre"])}</title><style>{ESTILO}</style></head><body>
<h1>Informe posterior al ejercicio</h1>
<p class="meta"><b>{e(esc["nombre"])}</b> · estado {e(esc["estado"])} · turnos resueltos {max(esc["turno_actual"] - 1, 0)}
 · clima actual {e(esc["clima"])} · azar {"activado" if esc["azar"] else "desactivado"}
 · creado {e(esc["creado_en"][:16].replace("T", " "))} UTC</p>
<h2>Resumen por bando</h2>{resumen_tabla}
<h3>Fuerza perdida acumulada</h3>{_barras(res)}
<h2>Estado final de las unidades</h2>{unidades_tabla}
{_rubrica_html(rubrica)}
<h2>Cronologia</h2>{"".join(secciones) or "<p class='meta'>Aun no se resolvio ningun turno.</p>"}
</body></html>"""


def render_csv(informe: dict) -> str:
    salida = io.StringIO()
    w = csv.writer(salida)
    w.writerow(["turno", "atacante", "atacante_bando", "defensor", "defensor_bando", "ratio",
                "perdida_atacante", "perdida_defensor", "terreno", "efectos", "lat", "lon"])
    for t in informe["turnos"]:
        for c in t["combates"]:
            w.writerow([c["turno"], _seguro(c["atacante"]), c["atacante_bando"], _seguro(c["defensor"]),
                        c["defensor_bando"], c["ratio"], c["perdida_atacante"], c["perdida_defensor"],
                        c["terreno"], _seguro(c["efectos"]), c["lat"], c["lon"]])
    return salida.getvalue()


def render_rubrica_csv(rubrica: dict) -> str:
    """Evaluacion por alumno (una fila por alumno y, si las hay, una por bando con lo que quedo sin autor)."""
    salida = io.StringIO()
    w = csv.writer(salida)
    w.writerow(["alumno", "bando", "puesto", "ordenes_emitidas", "ordenes_resueltas", "ordenes_rechazadas",
                "tasa_rechazo", "turnos_activos", "turnos_pasivos", "misiones_planificadas", "misiones_cumplidas",
                "misiones_abortadas", "misiones_fallidas", "motivos_rechazo", "observaciones"])
    for a in rubrica.get("alumnos") or []:
        o, mi = a["ordenes"], a["misiones"]
        w.writerow([_seguro(a["username"]), a["bando"], a["sigla"], o["emitidas"], o["resueltas"], o["rechazadas"],
                    o["tasa_rechazo"], a["turnos_activos"]["cantidad"], a["turnos_pasivos"]["cantidad"],
                    mi["planificadas"], mi["cumplidas"], mi["abortadas"], mi["fallidas"],
                    _seguro("; ".join(f'{m["motivo"]} ({m["veces"]})' for m in o["motivos_rechazo"])),
                    _seguro(" ".join(a["observaciones"]))])
    for b, n in (rubrica.get("sin_autor") or {}).items():
        if n["ordenes"] or n["misiones"]:
            w.writerow([SIN_AUTOR, b, "", n["ordenes"], "", "", "", "", "", n["misiones"], "", "", "", "", ""])
    return salida.getvalue()


def _seguro(valor: str) -> str:
    """Evita inyeccion de formulas al abrir el CSV en una hoja de calculo."""
    return "'" + valor if valor[:1] in ("=", "+", "-", "@", "\t", "\r") else valor
