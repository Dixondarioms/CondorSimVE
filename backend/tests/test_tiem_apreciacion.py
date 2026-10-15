"""TIEM, etapa 2: documentos de la apreciacion inicial (analisis de la mision, concepto del comandante, guia de
planeamiento y formas de accion con el criterio APA), sus permisos, estados, ayudas, PRC y archivos adjuntos."""

import base64
from types import SimpleNamespace

from app.engine import catalogo, plantillas, pmo, tiem
from app.models.unidad import Unidad
from tests.test_api import _preparar

MISION = {"tarea": "Conducir operaciones aéreas defensivas", "que": "para impedir la superioridad aérea enemiga",
          "donde": "en el área de operaciones", "cuando": "a partir de D/H", "proposito": "preservar la soberanía"}
FA = {"nombre": "F/A 1", "que": "Neutralizar la defensa aérea enemiga", "donde": "en la zona de R1", "cuando": "el día D",
      "quien": "Escuadrón de caza", "naturaleza": "si", "integridad": "si", "oportunidad": "si",
      "practicabilidad": "practicable"}


# ---------- motor ----------
def test_normalizar_limpia_tablas_opciones_y_formas():
    c = tiem.normalizar("concepto", {
        "cog": [{"lado": "propio", "nivel": "operacional", "cog": "Base", "otra": "x"}, {"lado": "marciano", "cog": "Y"}, {}],
        "mision_especifica": MISION, "basura": 1})
    assert c["cog"] == [{"lado": "propio", "nivel": "operacional", "cog": "Base", "cc": "", "rc": "", "vc": ""},
                        {"lado": "", "nivel": "", "cog": "Y", "cc": "", "rc": "", "vc": ""}]
    assert "basura" not in c and c["mision_especifica"]["tarea"] == MISION["tarea"]
    fa = tiem.normalizar("formas_accion", {"formas": [dict(FA, naturaleza="quizas")]})["formas"][0]
    assert fa["naturaleza"] == "" and fa["que"] == FA["que"]


def test_revisar_distingue_lo_que_falta_de_los_avisos():
    r = tiem.revisar("formas_accion", {"efecto_deseado": "x", "formas": [FA]})
    assert any("al menos dos" in f for f in r["faltan"])
    r = tiem.revisar("formas_accion", {"efecto_deseado": "x", "formas": [FA, dict(FA, nombre="F/A 2", que="Ataque a la base")]})
    assert r["faltan"] == [] and any("infinitivo" in a for a in r["avisos"])
    r = tiem.revisar("concepto", {"cog": [{"lado": "propio", "cog": "A"}, {"lado": "propio", "cog": "B"}]})
    assert any("uno enemigo" in f for f in r["faltan"])
    r = tiem.revisar("analisis_mision", {"mision_especifica": dict(MISION, tarea="Operaciones si se puede")})
    assert any("infinitivo" in a for a in r["avisos"]) and any("Resumen de la situación" in f for f in r["faltan"])


def test_poder_relativo_de_combate():
    esc = SimpleNamespace(semilla=7)
    u = lambda bando, clase, tipo="terrestre", n=1, fuerza=100: SimpleNamespace(  # noqa: E731
        bando=bando, clase=clase, tipo=tipo, modelo="", aeronaves=n, fuerza=fuerza, estado="activa")
    unidades = [u("azul", "caza", "aerea", 4), u("azul", "antiaerea"), u("azul", "radar"), u("azul", "infanteria"),
                u("rojo", "caza", "aerea", 2), u("rojo", "blindado"), u("rojo", "blindado"), u("rojo", "transporte")]
    r = tiem.poder_relativo(esc, unidades, "azul")
    f = {x["clave"]: x for x in r["filas"]}
    assert f["aviacion"]["propio"] == round(4 * (1.25 + catalogo.CLASES["caza"].defensa) / 2, 1)  # mejor ataque 1.25
    assert f["aviacion"]["conclusion"] in ("favorable", "muy favorable")
    assert f["defensa_aerea"]["valor"] is None and f["defensa_aerea"]["conclusion"] == "sin oposición"
    assert f["superficie"]["conclusion"] in ("desfavorable", "muy desfavorable")  # una infanteria contra dos blindados
    real = 2 * (1.25 + catalogo.CLASES["blindado"].defensa) / 2  # el transporte no suma: no es fuerza de combate
    assert 0.85 * real - 0.1 <= f["superficie"]["enemigo"] <= 1.15 * real + 0.1
    assert tiem.poder_relativo(esc, unidades, "azul") == r  # la estimacion es siempre la misma
    assert "Fortalezas: superioridad propia en aviación de combate" in tiem.fortalezas_debilidades(r)


def test_las_sugerencias_transcriben_pmo_objetivos_y_calendario(db_session):
    esc = plantillas.crear_desde_plantilla(db_session, "teatro_ficticio")
    pmo.generar(db_session, esc)
    db_session.commit()
    unidades = db_session.query(Unidad).filter(Unidad.escenario_id == esc.id).all()
    from app.models.objetivo import Objetivo
    objetivos = db_session.query(Objetivo).filter(Objetivo.escenario_id == esc.id).all()
    pm = pmo.normalizar(__import__("json").loads(pmo.obtener(db_session, esc, "azul").contenido_json))
    a = tiem.sugerencias("analisis_mision", esc, unidades, objetivos, "azul", pm, {})
    assert a["mision_to"] == pm["mision_superior"] and a["mision_especifica"] == pm["mision"]
    assert len(a["prc"]) == len(tiem.FACTORES_PRC) and a["tareas"] and all(t["origen"] == "impuesta" for t in a["tareas"])
    c = tiem.sugerencias("concepto", esc, unidades, objetivos, "azul", pm, {"analisis_mision": a})
    assert c["objetivos"][0]["prioridad"] == "1" and c["cog"] == [] and c["tareas"] == a["tareas"]  # el COG es de ellos
    g = tiem.sugerencias("guia", esc, unidades, objetivos, "azul", pm, {"concepto": c})
    assert "hora H" in g["condiciones"] and "Ejecucion" in g["criterios"]
    f = tiem.sugerencias("formas_accion", esc, unidades, objetivos, "azul", pm, {})
    assert ", a fin de " in f["efecto_deseado"] and f["formas"] == []


# ---------- API ----------
def _alumnos(api):
    prof = api("prof")
    for nombre, puesto in (("ua3", "a3"), ("ua4", "a4"), ("ujem", "jem")):
        assert prof.post("/api/usuarios", json={"username": nombre, "password": "clave-segura-1", "rol": "azul",
                                                "puesto": puesto}).status_code == 200
    return _preparar(api)


def _concepto_completo():
    return {"mision_especifica": MISION, "idea_general": "Neutralizar la defensa aérea y luego la aviación.",
            "cog": [{"lado": "propio", "nivel": "operacional", "cog": "Base aérea"},
                    {"lado": "enemigo", "nivel": "operacional", "cog": "Sistema de defensa aérea"}],
            "objetivos": [{"prioridad": "1", "objetivo": "R1"}], "tareas": [{"tarea": "Obtener la superioridad aérea"}],
            "efecto_deseado": [{"efecto": "Defensa aérea neutralizada", "nivel": "operacional"}]}


def test_cada_reparticion_redacta_lo_suyo_y_el_flujo_de_estados(api):
    prof, base, *_ = _alumnos(api)
    ruta = f"{base}/tiem"
    alfa, a3, a4, jem, bravo = api("alfa"), api("ua3"), api("ua4"), api("ujem"), api("bravo")
    vista = alfa.get(ruta).json()
    assert list(vista["documentos"]) == ["azul"] and vista["orden"] == list(tiem.ORDEN)
    assert vista["documentos"]["azul"]["concepto"]["puede_redactar"] is True
    assert a3.get(ruta).json()["documentos"]["azul"]["concepto"]["puede_redactar"] is False
    # el concepto es del Comandante y del JEM; las F/A, de A-3, A-3 D/A y A-2
    r = a3.put(f"{ruta}/azul/concepto", json={"contenido": _concepto_completo()})
    assert r.status_code == 403 and "CMDTE o JEM" in r.json()["detail"]
    assert a4.put(f"{ruta}/azul/formas_accion", json={"contenido": {}}).status_code == 403
    assert bravo.put(f"{ruta}/azul/concepto", json={"contenido": {}}).status_code == 403  # otro bando
    assert jem.put(f"{ruta}/azul/concepto", json={"contenido": {"idea_general": "borrador"}}).status_code == 200
    # incompleto no se presenta
    r = alfa.post(f"{ruta}/azul/concepto/presentar")
    assert r.status_code == 400 and "No se puede presentar" in r.json()["detail"]
    d = alfa.put(f"{ruta}/azul/concepto", json={"contenido": _concepto_completo()}).json()
    assert d["revision"]["faltan"] == [] and d["editado_por"] == "alfa" and d["editado_puesto"] == "comandante"
    d = alfa.post(f"{ruta}/azul/concepto/presentar").json()
    assert d["estado"] == "presentado" and d["presentado_turno"] == 1
    assert alfa.put(f"{ruta}/azul/concepto", json={"contenido": {}}).status_code == 400  # bloqueado mientras se revisa
    # el instructor lo devuelve con observaciones; vuelve a ser editable
    assert alfa.post(f"{ruta}/azul/concepto/revisar", json={"estado": "aprobado"}).status_code == 403
    r = prof.post(f"{ruta}/azul/concepto/revisar", json={"estado": "devuelto", "observaciones": "Falta el COG estratégico"})
    assert r.json()["estado"] == "devuelto"
    d = alfa.get(ruta).json()["documentos"]["azul"]["concepto"]
    assert d["observaciones"] == "Falta el COG estratégico"
    assert alfa.put(f"{ruta}/azul/concepto", json={"contenido": _concepto_completo()}).status_code == 200
    assert alfa.post(f"{ruta}/azul/concepto/presentar").json()["estado"] == "presentado"
    assert prof.post(f"{ruta}/azul/concepto/revisar", json={"estado": "aprobado"}).json()["estado"] == "aprobado"
    tipos = [e["descripcion"] for e in alfa.get(base).json()["eventos"] if e["tipo"] == "tiem"]
    assert any("aprobada" in t for t in tipos) and any("devuelta" in t for t in tipos)
    assert all(e["tipo"] != "tiem" for e in bravo.get(base).json()["eventos"])  # rojo no se entera
    # el instructor y el observador ven los dos bandos
    assert set(prof.get(ruta).json()["documentos"]) == {"azul", "rojo"}
    assert api("obs").get(ruta).json()["documentos"]["azul"]["concepto"]["puede_redactar"] is False


def test_formas_de_accion_por_api(api):
    prof, base, *_ = _alumnos(api)
    a3 = api("ua3")
    contenido = {"efecto_deseado": "Neutralizar la defensa aérea", "formas": [FA, dict(FA, nombre="F/A 2", que="Destruir la pista")]}
    d = a3.put(f"{base}/tiem/azul/formas_accion", json={"contenido": contenido}).json()
    assert len(d["contenido"]["formas"]) == 2 and d["revision"]["faltan"] == []
    assert a3.post(f"{base}/tiem/azul/formas_accion/presentar").json()["estado"] == "presentado"


def test_prc_y_sugerencias_por_api(api):
    prof, base, *_ = _alumnos(api)
    prof.post(f"{base}/pmo/generar", json={})
    alfa = api("alfa")
    r = alfa.get(f"{base}/tiem/azul/prc").json()
    assert [f["clave"] for f in r["filas"]] == [k for k, _ in tiem.FACTORES_PRC] and "estimación" in r["nota"]
    assert alfa.get(f"{base}/tiem/rojo/prc").status_code == 404
    s = alfa.get(f"{base}/tiem/azul/analisis_mision/sugerencias").json()["contenido"]
    assert s["mision_to"] and s["prc"]


def test_archivos_adjuntos(api):
    prof, base, *_ = _alumnos(api)
    alfa, a3 = api("alfa"), api("ua3")
    datos = base64.b64encode(b"PK\x03\x04 documento de prueba").decode()
    r = alfa.post(f"{base}/tiem/azul/guia/archivos", json={"nombre": "C:\\docs\\Guia de planeamiento.docx", "datos": datos})
    assert r.status_code == 200
    arch = r.json()["archivos"][0]
    assert arch["nombre"] == "Guia de planeamiento.docx" and arch["subido_por"] == "alfa"
    assert alfa.post(f"{base}/tiem/azul/guia/archivos", json={"nombre": "virus.exe", "datos": datos}).status_code == 400
    assert alfa.post(f"{base}/tiem/azul/guia/archivos", json={"nombre": "a.pdf", "datos": "no es base64!"}).status_code == 400
    bajada = a3.get(f"{base}/tiem/archivos/{arch['id']}")  # todo el bando lo lee
    assert bajada.status_code == 200 and bajada.content.startswith(b"PK") and "attachment" in bajada.headers["content-disposition"]
    assert api("bravo").get(f"{base}/tiem/archivos/{arch['id']}").status_code == 404
    assert prof.get(f"{base}/tiem/archivos/{arch['id']}").status_code == 200
    assert a3.delete(f"{base}/tiem/archivos/{arch['id']}").status_code == 403  # la guia no es de la A-3
    assert alfa.delete(f"{base}/tiem/archivos/{arch['id']}").json()["archivos"] == []


def test_el_instructor_que_conduce_redacta_como_comandante(api):
    prof, base, *_ = _alumnos(api)
    prof.patch(f"{base}/config", json={"conduccion_rojo": "instructor"})
    cab = {"X-Conduce-Bando": "rojo"}
    vista = prof.get(f"{base}/tiem", headers=cab).json()
    assert list(vista["documentos"]) == ["rojo"]
    d = prof.put(f"{base}/tiem/rojo/concepto", json={"contenido": _concepto_completo()}, headers=cab).json()
    assert d["editado_puesto"] == "comandante"
    assert prof.put(f"{base}/tiem/azul/concepto", json={"contenido": {}}, headers=cab).status_code == 403
