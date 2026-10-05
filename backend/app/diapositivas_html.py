"""Diapositivas automaticas del AAR: presentacion HTML (sin JavaScript externo) para la sesion de analisis posterior.

Portada con el marcador, una diapositiva por turno con lo relevante (combates, novedades, ordenes rechazadas), resumen
por bando, evaluacion (rubrica) por bando y por alumno, y preguntas para la discusion. Se navega con las flechas, espacio o clic; Ctrl+P
imprime (o guarda en PDF) una diapositiva por hoja."""

from html import escape as e

_ESTILO = """
html, body { margin: 0; background: #0f1116; color: #e8ecef; font-family: 'Segoe UI', Arial, sans-serif; }
.dia { min-height: 100vh; box-sizing: border-box; padding: 6vh 8vw; display: none; flex-direction: column; justify-content: center; }
.dia.activa { display: flex; }
.dia h1 { font-size: 3.2em; margin: 0 0 .2em; color: #fff; }
.dia h2 { font-size: 2.2em; margin: 0 0 .4em; color: #9cc2ff; }
.dia h3 { font-size: 1.3em; margin: 1em 0 .3em; color: #ffd21f; }
.dia p, .dia li { font-size: 1.2em; line-height: 1.5; }
.dia ul { margin: 0; padding-left: 1.2em; }
.dia .sec { color: #9aa7b1; }
.dia .azul { color: #9cc2ff; } .dia .rojo { color: #ff8c9a; }
.marcador { display: flex; gap: 3em; font-size: 2em; margin: .4em 0; }
.marcador b { font-size: 1.6em; }
.nav { position: fixed; bottom: 14px; right: 18px; color: #9aa7b1; font-size: 13px; }
table { border-collapse: collapse; font-size: 1.05em; } td, th { padding: 4px 12px; border-bottom: 1px solid #2b3240; text-align: left; } th { color: #9cc2ff; }
@media print { .dia { display: flex !important; page-break-after: always; min-height: auto; padding: 1.5cm; background: #fff; color: #111; } .dia h1, .dia h2, .dia h3 { color: #1f4e8c; } .nav { display: none; } }
"""

_SCRIPT = """
const dias = [...document.querySelectorAll('.dia')]; let i = 0;
function ir(k) { i = Math.max(0, Math.min(dias.length - 1, k)); dias.forEach((d, j) => d.classList.toggle('activa', j === i));
  document.getElementById('nav').textContent = (i + 1) + ' / ' + dias.length + ' - flechas o clic para avanzar - Ctrl+P imprime todas'; }
document.addEventListener('keydown', (ev) => { if (['ArrowRight', ' ', 'PageDown'].includes(ev.key)) ir(i + 1); if (['ArrowLeft', 'PageUp'].includes(ev.key)) ir(i - 1); if (ev.key === 'Home') ir(0); if (ev.key === 'End') ir(dias.length - 1); });
document.addEventListener('click', () => ir(i + 1));
ir(0);
"""

PREGUNTAS = (
    "¿Qué información faltaba al decidir y cómo se podría haber obtenido?",
    "¿Las órdenes rechazadas revelan un problema de apreciación (distancias, alcances, logística)?",
    "¿Cómo se coordinaron los puestos del estado mayor y qué se haría distinto?",
    "¿Qué habría cambiado con otro clima, otra logística o sin niebla de guerra?",
)


def _puntos(marcador: dict, bando: str) -> int:
    v = (marcador or {}).get(bando, 0)
    if isinstance(v, dict):
        return int(v.get("puntos", 0) or 0)
    return int(v or 0)


def _marcador_html(marcador: dict) -> str:
    return (f'<div class="marcador"><span class="azul">Azul <b>{_puntos(marcador, "azul")}</b></span>'
            f'<span class="rojo">Rojo <b>{_puntos(marcador, "rojo")}</b></span></div>')


def _dia_turno(t: dict) -> str | None:
    if t.get("en_curso") or (not t["combates"] and not t["eventos"] and not t["ordenes"]):
        return None
    partes = []
    if t["combates"]:
        filas = "".join(
            f'<li><span class="{e(c["atacante_bando"])}">{e(c["atacante"])}</span> atacó a '
            f'<span class="{e(c["defensor_bando"])}">{e(c["defensor"])}</span> ({e(c["terreno"])}): '
            f'pérdidas {c["perdida_atacante"]:.0f} % / {c["perdida_defensor"]:.0f} %</li>'
            for c in t["combates"][:8])
        partes.append(f"<h3>Combates ({len(t['combates'])})</h3><ul>{filas}</ul>")
    eventos = [ev for ev in t["eventos"] if ev["tipo"] != "direccion"]
    if eventos:
        partes.append("<h3>Novedades</h3><ul>" + "".join(f"<li>{e(ev['descripcion'])}</li>" for ev in eventos[:8]) + "</ul>")
    rechazadas = [o for o in t["ordenes"] if o.get("estado") == "rechazada"]
    detalle = " · ".join(e(str(o.get("resultado", "")))[:90] for o in rechazadas[:3])
    partes.append(f'<p class="sec">Órdenes emitidas: {len(t["ordenes"])} · rechazadas: {len(rechazadas)}{" · " + detalle if detalle else ""}</p>')
    return (f'<section class="dia"><h2>Turno {t["turno"]}</h2><p class="sec">Clima: {e(str(t.get("clima", "")))}</p>'
            + "".join(partes) + "</section>")


def render_diapositivas(informe: dict, rubrica: dict | None = None) -> str:
    esc = informe["escenario"]
    res = informe["resumen"]
    marcador = informe.get("marcador") or {}
    dias = [
        f'<section class="dia activa"><p class="sec">S.I.E.T.E. · Informe posterior al ejercicio</p><h1>{e(esc["nombre"])}</h1>'
        f'<p>Turnos jugados: {max(0, int(esc.get("turno_actual", 1)) - 1)} · clima general: {e(str(esc.get("clima", "")))}</p>'
        f"{_marcador_html(marcador)}</section>"
    ]
    dias += [d for d in (_dia_turno(t) for t in informe["turnos"]) if d]
    filas = "".join(
        f'<tr><td class="{e(b)}">{e(b.capitalize())}</td><td>{r["unidades"]}</td><td>{r["destruidas"]}</td>'
        f'<td>{r["fuerza_perdida"]:.0f}</td><td>{r["dano_infligido"]:.0f}</td><td>{r["ordenes_emitidas"]}</td>'
        f'<td>{r["ordenes_rechazadas"]}</td></tr>' for b, r in res.items())
    dias.append('<section class="dia"><h2>Resumen del ejercicio</h2><table><tr><th>Bando</th><th>Unidades</th><th>Destruidas</th>'
                f"<th>Fuerza perdida</th><th>Daño infligido</th><th>Órdenes</th><th>Rechazadas</th></tr>{filas}</table>"
                f"{_marcador_html(marcador)}</section>")
    for b, datos in ((rubrica or {}).get("bandos") or {}).items():
        o = datos.get("ordenes") or {}
        cuerpo = (f"<p>Órdenes: {o.get('emitidas', 0)} emitidas, {o.get('rechazadas', 0)} rechazadas · turnos pasivos: "
                  f"{(datos.get('turnos_pasivos') or {}).get('cantidad', 0)} · objetivos cumplidos: "
                  f"{(datos.get('objetivos') or {}).get('cumplidos', 0)}</p>")
        obs = datos.get("observaciones") or []
        if obs:
            cuerpo += "<h3>Observaciones</h3><ul>" + "".join(f"<li>{e(x)}</li>" for x in obs[:7]) + "</ul>"
        dias.append(f'<section class="dia"><h2>Evaluación del bando {e(b.capitalize())}</h2>{cuerpo}</section>')
    alumnos = (rubrica or {}).get("alumnos") or []
    if alumnos:
        filas = "".join(
            f'<tr><td>{e(a["username"])}</td><td class="{e(a["bando"])}">{e(a["bando"].capitalize())}</td><td>{e(a["sigla"])}</td>'
            f'<td>{a["ordenes"]["emitidas"]}</td><td>{a["ordenes"]["rechazadas"]}</td>'
            f'<td>{a["turnos_pasivos"]["cantidad"]}</td><td>{a["misiones"]["planificadas"]}</td></tr>'
            for a in alumnos[:12])
        sin_autor = sum(n["ordenes"] + n["misiones"] for n in ((rubrica or {}).get("sin_autor") or {}).values())
        nota = f'<p class="sec">{sin_autor} orden(es) o misión(es) sin autor registrado.</p>' if sin_autor else ""
        dias.append('<section class="dia"><h2>Evaluación por alumno</h2><table><tr><th>Alumno</th><th>Bando</th><th>Puesto</th>'
                    f"<th>Órdenes</th><th>Rechazadas</th><th>Turnos pasivos</th><th>Misiones</th></tr>{filas}</table>{nota}</section>")
    dias.append('<section class="dia"><h2>Preguntas para la discusión</h2><ul>' + "".join(f"<li>{e(p)}</li>" for p in PREGUNTAS) + "</ul></section>")
    return (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Diapositivas · {e(esc["nombre"])}</title>'
            f"<style>{_ESTILO}</style></head><body>{''.join(dias)}<div class='nav' id='nav'></div><script>{_SCRIPT}</script></body></html>")
