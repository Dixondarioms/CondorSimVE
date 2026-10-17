"""TIEM, etapa 6: evaluacion del trabajo de Estado Mayor y exportacion de los documentos (Word y pagina imprimible)."""

import io
import zipfile
from xml.etree import ElementTree

from tests.test_api import _preparar

MISION = {"tarea": "Conducir operaciones aéreas defensivas", "que": "para impedir la superioridad aérea enemiga",
          "donde": "en el área", "cuando": "desde H", "proposito": "preservar la soberanía"}
CONCEPTO = {"mision_especifica": MISION, "idea_general": "Primero la defensa aérea.",
            "cog": [{"lado": "propio", "cog": "Base"}, {"lado": "enemigo", "cog": "Radar"}],
            "objetivos": [{"prioridad": "1", "objetivo": "R1"}], "tareas": [{"tarea": "Impedir"}],
            "efecto_deseado": [{"efecto": "Radar fuera de servicio"}]}


def test_evaluacion_y_nota_del_instructor(api):
    prof, base, a, r1, r2 = _preparar(api)
    alfa = api("alfa")
    ev = alfa.get(f"{base}/tiem/evaluacion").json()
    assert list(ev) == ["azul"] and ev["azul"]["aplica"] is False and ev["azul"]["nota"] is None
    prof.patch(f"{base}/config", json={"turno_h": 2, "fecha_inicio": "2026-11-01"})
    alfa.put(f"{base}/tiem/azul/concepto", json={"contenido": CONCEPTO})
    alfa.post(f"{base}/tiem/azul/concepto/presentar")
    alfa.put(f"{base}/tiem/azul/guia", json={"contenido": {"nombre_clave": "Centinela"}})  # incompleta
    tareas = [{"id": "e0000001", "unidad_id": a["id"], "unidad_nombre": "A", "tipo": "atacar", "turno": 1,
               "objetivo": f"u:{r1['id']}", "objetivo_nombre": "R1"}]
    alfa.put(f"{base}/tiem/azul/plan_operaciones", json={"contenido": {"tareas": tareas}})
    alfa.post(f"{base}/tiem/azul/emitir", json={})
    r = prof.post(f"{base}/tiem/azul/concepto/revisar", json={"estado": "aprobado", "nota": 17})
    assert r.json()["nota"] == 17
    ev = prof.get(f"{base}/tiem/evaluacion").json()
    assert set(ev) == {"azul", "rojo"} and ev["rojo"]["aplica"] is False
    inds = {i["id"]: i for i in ev["azul"]["indicadores"]}
    assert inds["documentos"]["valor"].startswith("1 aprobado(s)")
    assert inds["forma"]["puntaje"] < 100  # la guia esta incompleta
    assert inds["oportunidad"]["puntaje"] == 100  # el concepto se presento en el turno 1, antes de H (turno 2)
    assert inds["ejecucion"]["puntaje"] == 100 and inds["ejecucion"]["valor"].startswith("1 de 1")
    assert ev["azul"]["nota_instructor"] == 17 and ev["azul"]["nota_automatica"] is not None
    assert ev["azul"]["nota"] == round((17 + ev["azul"]["nota_automatica"]) / 2, 1)
    doc = next(d for d in ev["azul"]["documentos"] if d["tipo"] == "concepto")
    assert (doc["estado"], doc["nota"]) == ("aprobado", 17)
    # va tambien en la rubrica del informe
    rub = prof.get(f"{base}/aar/rubrica").json()
    assert rub["bandos"]["azul"]["tiem"]["nota_instructor"] == 17
    assert prof.post(f"{base}/tiem/azul/concepto/revisar", json={"estado": "aprobado", "nota": 25}).status_code == 422


def test_exportacion_a_word_y_pagina_imprimible(api):
    prof, base, *_ = _preparar(api)
    prof.post(f"{base}/pmo/generar", json={})
    alfa = api("alfa")
    alfa.put(f"{base}/tiem/azul/concepto", json={"contenido": CONCEPTO})
    alfa.put(f"{base}/tiem/azul/guia", json={"contenido": {"nombre_clave": "Centinela", "capacidades_enemigo": [{"que": "Atacar <la base> & más"}]}})
    r = alfa.get(f"{base}/tiem/azul/legajo.docx")
    assert r.status_code == 200 and "legajo_tiem_azul" in r.headers["content-disposition"]
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert {"[Content_Types].xml", "word/document.xml", "word/styles.xml", "_rels/.rels"} <= set(z.namelist())
    xml = z.read("word/document.xml").decode("utf-8")
    ElementTree.fromstring(xml)  # XML bien formado (los < y & del texto quedan escapados)
    for texto in ("LEGAJO DEL TRABAJO INTEGRAL DE ESTADO MAYOR", "CONCEPTO DEL COMANDANTE", "CENTINELA",
                  "Atacar &lt;la base&gt; &amp; más", "a fin de preservar la soberanía", "USO ACADÉMICO", "FIRMA"):
        assert texto in xml, texto
    assert "Problema Militar Operativo".upper() in xml
    un = alfa.get(f"{base}/tiem/azul/concepto/documento.docx")
    assert un.status_code == 200
    ElementTree.fromstring(zipfile.ZipFile(io.BytesIO(un.content)).read("word/document.xml"))
    html = alfa.get(f"{base}/tiem/azul/legajo.html").text
    assert "Imprimir o guardar como PDF" in html and "LEGAJO DEL TRABAJO INTEGRAL" in html and "&lt;la base&gt;" in html
    assert api("bravo").get(f"{base}/tiem/azul/legajo.docx").status_code == 404
    assert prof.get(f"{base}/tiem/rojo/legajo.html").status_code == 200
