"""Exportacion de los documentos del TIEM: cada documento o el legajo completo de un bando, en Word (.docx) y en una
pagina imprimible (para guardarla como PDF desde el navegador).

El formato sigue el del TIEM para toda apreciacion escrita: ENCABEZAMIENTO (clasificacion arriba y abajo; Cuartel
General que la prepara, lugar, fecha y hora, nombre clave de la operacion, numero de copia), TEXTO o cuerpo con los
parrafos del documento, y FINAL (firma, nombre, grado y cargo, anexos y distribucion).

El .docx se arma a mano (WordprocessingML dentro de un zip), sin dependencias: lo abren Word, LibreOffice y WPS.
"""

import html
import io
import json
import re
import zipfile
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.engine import calendario, lugares, naciones, pmo, tiem
from app.models.documento_tiem import DocumentoTiem
from app.models.escenario import Escenario
from app.models.unidad import Unidad

CLASIFICACION = "USO ACADÉMICO — EJERCICIO"
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


# ---------------------------------------------------------------- bloques (independientes del formato)
def _texto_bloques(texto: str) -> list:
    out = []
    for linea in str(texto or "").split("\n"):
        linea = linea.strip()
        if linea:
            out.append(("li", linea[2:]) if linea.startswith("- ") else ("p", linea))
    return out or [("p", "—")]


def _mayuscula(t: str) -> str:
    return t[:1].upper() + t[1:]


def _opcion(v: str) -> str:
    return {"si": "Sí", "no": "No"}.get(v, v.capitalize() if v else "")


def bloques_documento(tipo: str, contenido: dict, contexto: dict, ref_h) -> list:
    """Cuerpo de un documento del TIEM como bloques: titulos de parrafo, texto, viñetas y tablas."""
    d = tiem.DOCUMENTOS[tipo]
    c = tiem.normalizar(tipo, contenido)
    out = []
    for campo in d.campos:
        v = c[campo.clave]
        out.append(("h2", campo.titulo))
        if campo.tipo in ("texto", "linea"):
            out += _texto_bloques(v)
        elif campo.tipo == "mision":
            out.append(("mision", pmo.texto_mision(v) or "—"))
        elif campo.tipo == "tabla":
            if v:
                out.append(("tabla", [x.titulo for x in campo.columnas],
                            [[_opcion(f[x.clave]) if x.opciones else f[x.clave] for x in campo.columnas] for f in v]))
            else:
                out.append(("p", "—"))
        elif campo.tipo == "formas":
            if not v:
                out.append(("p", "—"))
            for i, fa in enumerate(v, 1):
                out.append(("p_negrita", f"{fa['nombre'] or f'F/A {i}'}: {fa['que']}"))
                filas = [[t, _opcion(fa[k]) if tp == "opcion" else fa[k]] for k, t, tp, _ in tiem.CAMPOS_FA
                         if k not in ("nombre", "que") and fa[k]]
                if filas:
                    out.append(("tabla", ["Elemento", "Contenido"], filas))
        elif campo.tipo == "matriz":
            formas = list(dict.fromkeys((contexto.get("formas") or []) + [x["fa"] for x in v]))
            caps = list(dict.fromkeys((contexto.get("capacidades") or []) + [x["capacidad"] for x in v]))
            celdas = {(x["fa"], x["capacidad"]): x for x in v}
            if formas and caps:
                filas = []
                for fa in formas:
                    fila = [fa]
                    for cap in caps:
                        x = celdas.get((fa, cap))
                        fila.append(f"{_opcion(x['efecto'])}{': ' + x['analisis'] if x and x['analisis'] else ''}" if x else "")
                    filas.append(fila)
                out.append(("tabla", ["F/A \\ Capacidad"] + caps, filas))
            else:
                out.append(("p", "—"))
        elif campo.tipo == "tareas":
            if v:
                filas = [[f"{t['turno'] or ''}{' (' + ref_h(t['turno']) + ')' if t['turno'] and ref_h(t['turno']) else ''}",
                          t["unidad_nombre"], tiem.TIPOS_TAREA.get(t["tipo"], ""), t["objetivo_nombre"], t["detalle"]]
                         for t in sorted(v, key=lambda t: t["turno"] or 0)]
                out.append(("tabla", ["Turno", "Unidad", "Acción", "Objetivo o destino", "Tarea"], filas))
            else:
                out.append(("p", "—"))
    return out


def _encabezado(info: dict, titulo: str) -> list:
    return [("clasif", CLASIFICACION),
            ("derecha", [info["cuartel"], info["lugar"], info["fecha"], f"Copia N.º 1"]),
            ("p_centro", info["nombre_clave"]), ("titulo", titulo.upper())]


def _final(info: dict) -> list:
    return [("p", ""), ("p", "FIRMA: ______________________"), ("p", "NOMBRE:"), ("p", "GRADO:"), ("p", "CARGO:"),
            ("p", "ANEXOS: —"), ("p", f"DISTRIBUCIÓN: Comandante, JEM y reparticiones del {info['cuartel']}."),
            ("clasif", CLASIFICACION)]


def informacion(db: Session, esc: Escenario, bando: str, documentos: dict) -> dict:
    nacion = naciones.obtener(getattr(esc, f"nacion_{bando}"))
    pais = nacion.nombre.replace(" (ficticia)", "") if nacion else f"Bando {bando.capitalize()}"
    base = (db.query(Unidad).filter(Unidad.escenario_id == esc.id, Unidad.bando == bando, Unidad.clase == "base_aerea")
            .order_by(Unidad.id).first())
    ref = calendario.referencia(esc, esc.turno_actual)
    fecha = f"{ref['fecha']} {ref['hora']}" if ref["fecha"] else datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    clave = ((documentos.get("plan_operaciones") or {}).get("nombre_clave")
             or (documentos.get("guia") or {}).get("nombre_clave") or "")
    return {"pais": pais, "cuartel": f"Cuartel General del Componente Aéreo — {pais}",
            "lugar": _mayuscula(lugares.describir(base.lat, base.lon)) if base else "",
            "fecha": f"Fecha y hora: {fecha}", "nombre_clave": clave.upper() or "(OPERACIÓN SIN NOMBRE CLAVE)",
            "escenario": esc.nombre}


def _contexto(db: Session, esc: Escenario, bando: str) -> tuple[dict, dict]:
    docs = {d.tipo: tiem.normalizar(d.tipo, json.loads(d.contenido_json))
            for d in db.query(DocumentoTiem).filter(DocumentoTiem.escenario_id == esc.id, DocumentoTiem.bando == bando)}
    return docs, tiem.contexto(docs)


def _ref_h(esc: Escenario):
    def ref(turno):
        return calendario.referencia(esc, turno)["hora_h"] or "" if turno else ""
    return ref


def bloques_un_documento(db: Session, esc: Escenario, bando: str, tipo: str) -> tuple[str, list]:
    docs, ctx = _contexto(db, esc, bando)
    info = informacion(db, esc, bando, docs)
    titulo = tiem.DOCUMENTOS[tipo].titulo
    return titulo, (_encabezado(info, titulo) + bloques_documento(tipo, docs.get(tipo, {}), ctx, _ref_h(esc)) + _final(info))


def bloques_legajo(db: Session, esc: Escenario, bando: str) -> tuple[str, list]:
    """Portada, Problema Militar Operativo y todos los documentos redactados del bando, cada uno en su pagina."""
    docs, ctx = _contexto(db, esc, bando)
    info = informacion(db, esc, bando, docs)
    out = [("clasif", CLASIFICACION), ("p", ""), ("titulo", "LEGAJO DEL TRABAJO INTEGRAL DE ESTADO MAYOR"),
           ("p_centro", info["cuartel"]), ("p_centro", info["nombre_clave"]), ("p_centro", f"Ejercicio: {info['escenario']}"),
           ("p_centro", info["fecha"]), ("p", ""), ("h2", "Contenido")]
    presentes = [t for t in tiem.ORDEN if t in docs]
    out += [("li", "Problema Militar Operativo")] + [("li", f"{tiem.DOCUMENTOS[t].paso}: {tiem.DOCUMENTOS[t].titulo}")
                                                     for t in presentes]
    pm = pmo.obtener(db, esc, bando)
    if pm is not None:
        p = pmo.normalizar(json.loads(pm.contenido_json))
        out += [("salto",)] + _encabezado(info, "Problema Militar Operativo")
        for clave, titulo in pmo.CAMPOS:
            out.append(("h2", titulo))
            out += [("mision", pmo.texto_mision(p["mision"]) or "—")] if clave == "mision" else _texto_bloques(p[clave])
    for t in presentes:
        out += [("salto",)] + _encabezado(info, tiem.DOCUMENTOS[t].titulo)
        out += bloques_documento(t, docs[t], ctx, _ref_h(esc)) + _final(info)
    return "Legajo del TIEM", out


# ---------------------------------------------------------------- Word (.docx)
def _x(t) -> str:
    return html.escape(_CONTROL.sub("", str(t)), quote=False)


def _run(texto: str, negrita=False, tam=None) -> str:
    props = ("<w:b/>" if negrita else "") + (f'<w:sz w:val="{tam}"/>' if tam else "")
    return f'<w:r>{"<w:rPr>" + props + "</w:rPr>" if props else ""}<w:t xml:space="preserve">{_x(texto)}</w:t></w:r>'


def _par(texto: str, estilo=None, alinear=None, negrita=False, tam=None, junto=False) -> str:
    ppr = ((f'<w:pStyle w:val="{estilo}"/>' if estilo else "") + ("<w:keepNext/>" if junto else "")
           + (f'<w:jc w:val="{alinear}"/>' if alinear else ""))
    return f'<w:p>{"<w:pPr>" + ppr + "</w:pPr>" if ppr else ""}{_run(texto, negrita, tam)}</w:p>'


def _tabla(encabezados: list, filas: list) -> str:
    borde = '<w:{0} w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
    bordes = "".join(borde.format(b) for b in ("top", "left", "bottom", "right", "insideH", "insideV"))
    sombra = '<w:shd w:val="clear" w:color="auto" w:fill="D9E2F3"/>'

    def celda(t, cab=False):
        lineas = str(t).split("\n") if str(t) else [""]
        return (f'<w:tc><w:tcPr>{sombra if cab else ""}</w:tcPr>'
                + "".join(_par(linea, alinear="left", negrita=cab, tam=18, junto=cab) for linea in lineas) + "</w:tc>")
    ancho = 9354 // max(1, len(encabezados))  # ancho util de la pagina A4 en vigesimos de punto
    grilla = "<w:tblGrid>" + "".join(f'<w:gridCol w:w="{ancho}"/>' for _ in encabezados) + "</w:tblGrid>"
    xml = [f'<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/><w:tblBorders>{bordes}</w:tblBorders></w:tblPr>{grilla}']
    # la fila de titulos se repite en cada pagina y no queda sola al pie
    xml.append("<w:tr><w:trPr><w:cantSplit/><w:tblHeader/></w:trPr>" + "".join(celda(h, True) for h in encabezados) + "</w:tr>")
    for f in filas:
        xml.append("<w:tr>" + "".join(celda(v) for v in f) + "</w:tr>")
    xml.append("</w:tbl>" + _par(""))
    return "".join(xml)


def _cuerpo_word(bloques: list) -> str:
    out = []
    for b in bloques:
        tipo = b[0]
        if tipo == "titulo":
            out.append(_par(b[1], "Title", "center"))
        elif tipo == "clasif":
            out.append(_par(b[1], alinear="center", negrita=True, tam=18))
        elif tipo == "derecha":
            out += [_par(linea, alinear="right", tam=18) for linea in b[1] if linea]
        elif tipo == "p_centro":
            out.append(_par(b[1], alinear="center", negrita=True))
        elif tipo == "h2":
            out.append(_par(b[1], "Heading2"))
        elif tipo == "p":
            out.append(_par(b[1]))
        elif tipo == "p_negrita":
            out.append(_par(b[1], negrita=True))
        elif tipo == "li":
            out.append(_par(f"• {b[1]}"))
        elif tipo == "mision":
            out.append(_par(b[1], negrita=True))
        elif tipo == "tabla":
            out.append(_tabla(b[1], b[2]))
        elif tipo == "salto":
            out.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
    return "".join(out)


_W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
_ESTILOS = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles {_W}>
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/><w:sz w:val="22"/>
<w:lang w:val="es-VE"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="80"/><w:jc w:val="both"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="120" w:after="240"/><w:jc w:val="center"/></w:pPr><w:rPr><w:b/><w:sz w:val="30"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="200" w:after="80"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:sz w:val="23"/></w:rPr></w:style>
</w:styles>"""


def word(titulo: str, bloques: list) -> bytes:
    """Documento .docx (A4, Arial 11) con los bloques."""
    documento = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {_W}><w:body>'
                 + _cuerpo_word(bloques)
                 + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" '
                   'w:left="1418" w:header="567" w:footer="567" w:gutter="0"/></w:sectPr></w:body></w:document>')
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    partes = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
            '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/></Types>'),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            '</Relationships>'),
        "word/_rels/document.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '</Relationships>'),
        "word/styles.xml": _ESTILOS,
        "word/document.xml": documento,
        "docProps/core.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties '
            'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f'<dc:title>{_x(titulo)}</dc:title><dc:creator>S.I.E.T.E.</dc:creator>'
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{ahora}</dcterms:created></cp:coreProperties>'),
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre, contenido in partes.items():
            z.writestr(nombre, contenido)
    return buf.getvalue()


# ---------------------------------------------------------------- pagina imprimible (PDF desde el navegador)
_CSS = """
body { font-family: Arial, sans-serif; font-size: 11pt; color: #111; max-width: 820px; margin: 24px auto; padding: 0 16px; }
.clasif { text-align: center; font-weight: bold; font-size: 9pt; letter-spacing: .05em; }
.derecha { text-align: right; font-size: 9pt; margin: 0; }
.centro { text-align: center; font-weight: bold; }
h1 { text-align: center; font-size: 15pt; margin: 12px 0 18px; }
h2 { font-size: 11.5pt; margin: 14px 0 4px; break-after: avoid; }
p { margin: 3px 0; text-align: justify; }
.mision { font-weight: bold; border-left: 3px solid #888; padding-left: 8px; }
table { border-collapse: collapse; width: 100%; margin: 4px 0 10px; font-size: 9pt; }
th, td { border: 1px solid #888; padding: 3px 5px; vertical-align: top; text-align: left; white-space: pre-wrap; }
th { background: #d9e2f3; }
.salto { break-before: page; }
.barra { position: sticky; top: 0; background: #fff; padding: 8px 0; text-align: right; }
.barra button { font-size: 11pt; padding: 6px 12px; }
@media print { .barra { display: none; } body { margin: 0; max-width: none; } }
"""


def pagina(titulo: str, bloques: list) -> str:
    e = lambda t: html.escape(str(t))  # noqa: E731
    out = [f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>{e(titulo)}</title><style>{_CSS}</style>'
           '</head><body><div class="barra"><button onclick="window.print()">Imprimir o guardar como PDF</button></div>']
    salto = False
    for b in bloques:
        tipo = b[0]
        clase = ' class="salto"' if salto else ""
        if tipo == "salto":
            salto = True
            continue
        if tipo == "titulo":
            out.append(f"<h1{clase}>{e(b[1])}</h1>")
        elif tipo == "clasif":
            out.append(f'<p class="clasif{" salto" if salto else ""}">{e(b[1])}</p>')
        elif tipo == "derecha":
            out += [f'<p class="derecha">{e(x)}</p>' for x in b[1] if x]
        elif tipo == "p_centro":
            out.append(f'<p class="centro">{e(b[1])}</p>')
        elif tipo == "h2":
            out.append(f"<h2>{e(b[1])}</h2>")
        elif tipo in ("p", "p_negrita"):
            out.append(f"<p>{'<b>' + e(b[1]) + '</b>' if tipo == 'p_negrita' else e(b[1]) or '&nbsp;'}</p>")
        elif tipo == "li":
            out.append(f"<p>• {e(b[1])}</p>")
        elif tipo == "mision":
            out.append(f'<p class="mision">{e(b[1])}</p>')
        elif tipo == "tabla":
            filas = "".join("<tr>" + "".join(f"<td>{e(v)}</td>" for v in f) + "</tr>" for f in b[2])
            out.append("<table><tr>" + "".join(f"<th>{e(h)}</th>" for h in b[1]) + f"</tr>{filas}</table>")
        salto = False
    out.append("</body></html>")
    return "".join(out)
