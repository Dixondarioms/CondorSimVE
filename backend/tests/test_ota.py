"""Orden de Tareas Aereas (engine/ota.py): formato AV/D 5-47, datos OTA de las misiones, paquete con comandante de
mision, TOT, punto de reunion, altura por tramo y efecto del armamento."""

import json
from datetime import datetime
from types import SimpleNamespace

from app.engine import misiones as misiones_mod
from app.engine import ota
from app.models.evento import Evento
from app.models.mision import Mision
from tests.test_aeronaves import _base_aerea
from tests.test_api import _preparar
from tests.test_ciclo_vuelo import _base, _caza, _refrescar
from tests.test_misiones import P, _mision, aterrizaje
from tests.test_orders import _avanzar, _escenario


# ---------- formato ----------
def test_formato_de_fechas_coordenadas_y_lineas():
    dt = datetime(2014, 9, 12, 6, 20)
    assert ota.f_encabezado(dt) == "1206:20SEP14"
    assert ota.f_ventana(dt) == "120620" and ota.f_alerta(dt) == "H06M20"
    assert ota.f_coord(10.7625, -67.6033) == "104545N-673612W"
    assert ota.linea("DATMI", "A0901", None, "") == "DATMI / A0901 / - / - //"
    assert ota.codigo_lugar("Base Aérea El Libertador") == "LIBE"
    assert ota.codigo_aeronave("su30") == "CMK" and ota.codigo_aeronave("f16") == "CFA"
    assert ota.codigo_mision("INTERDICCION") == "1OT" and ota.codigo_mision("CAP", elegido="2BC") == "2BC"
    assert ota.rumbo(0, 0, 1, 0) == 0 and ota.rumbo(0, 0, 0, 1) == 90
    # el codigo OACI del aerodromo donde esta la base; si no hay ninguno cerca, el formado con su nombre
    assert ota.codigo_base(SimpleNamespace(lat=10.485, lon=-66.843, nombre="Base La Carlota")) == "SVFM"
    assert ota.codigo_base(SimpleNamespace(lat=0.0, lon=0.0, nombre="Base Azul")) == "AZUL"


def test_validacion_del_armamento_iff_y_funcion():
    caza = misiones_mod.clase_de_modelo("su30")
    assert ota.validar("CAP", "su30", caza, {"armamento_primario": "MAA", "iff": "31701"}) == []
    assert any("aire-aire" in e for e in ota.validar("CAP", "su30", caza, {"armamento_primario": "BKR"}))
    assert any("no es armamento" in e for e in ota.validar("CAP", "su30", caza, {"armamento_primario": "M120"}))
    assert any("aire-superficie" in e for e in ota.validar("INTERDICCION", "su30", caza, {"armamento_primario": "MAA"}))
    assert any("IFF" in e for e in ota.validar("CAP", "su30", caza, {"iff": "38999"}))
    assert any("paquete" in e for e in ota.validar("CAP", "su30", caza, {"funcion": "CM"}))


def test_efecto_del_armamento_en_el_ataque():
    avion = SimpleNamespace(tipo="aerea", arma_elegida="BBU")
    tanque = SimpleNamespace(tipo="terrestre", clase="blindado", en_tierra=False)
    assert ota.factor_ataque(avion, tanque) == ota.FACTOR_GUIADA
    assert ota.factor_ataque(SimpleNamespace(tipo="aerea", arma_elegida="BMK"), tanque) == 1.0
    assert ota.factor_ataque(SimpleNamespace(tipo="aerea", arma_elegida=None), tanque) == 1.0
    assert ota.factor_ataque(SimpleNamespace(tipo="aerea", arma_elegida="MA3"), tanque) == 1.0


def test_la_altura_de_cada_tramo_cambia_el_consumo():
    pts = [P("paso", 100), P("paso", 200, perfil="rasante"), P("paso", 300)]
    alto = misiones_mod.estimar(0, 0, 900, 1800, 100, pts, 1.0)
    bajo = misiones_mod.estimar(0, 0, 900, 1800, 100, [P("paso", 100), P("paso", 200), P("paso", 300)], 1.0)
    assert alto["combustible_final"] < bajo["combustible_final"]  # dos tramos rasantes gastan mas
    t = ota.tramos(0, 0, pts, "medio")
    assert [x["perfil"] for x in t] == ["medio", "rasante", "rasante"] and t[1]["altitud_ft"] == 200
    assert t[0]["rumbo"] == 0 and t[0]["nm"] == round(100 / 1.852, 1)


# ---------- API ----------
def test_api_paquete_con_comandante_tot_y_documento_ota(api):
    prof, base, a, r1, r2 = _preparar(api)
    ba = _base_aerea(prof, base, lat=0.0, lon=0.3)
    alfa = api("alfa")
    aterr = {"tipo": "aterrizaje", "lat": ba["lat"], "lon": ba["lon"], "base_id": ba["id"]}
    blanco = {"tipo": "blanco", "lat": 1.8, "lon": 0.3, "perfil": "rasante"}
    datos = {"paquete": "tela", "funcion": "CM", "alerta": 1, "armamento_primario": "BBU", "armamento_secundario": "MPA",
             "iff": "31701", "tot_turno": 4}
    cuerpo = {"rol": "INTERDICCION", "base_id": ba["id"], "modelo": "f16", "aeronaves": 4, "nombre": "Bocono",
              "puntos": [{"tipo": "paso", "lat": 0.5, "lon": 0.3, "reunion": True}, blanco, aterr], "ota": datos}
    r = alfa.post(f"{base}/misiones/previsualizar", json=cuerpo)
    assert r.status_code == 200 and r.json()["errores"] == [], r.text
    plan = r.json()["plan"]
    llegada = plan["puntos"][1]["llegada_h"]
    assert r.json()["turno_despegue"] == 4 - int(llegada) and plan["tot_turno"] == 4
    assert [t["perfil"] for t in plan["tramos"]][1] == "rasante" and "reunion_turno" in plan
    m = alfa.post(f"{base}/misiones", json=cuerpo).json()
    assert m["ota"]["paquete"] == "TELA" and m["ota"]["funcion"] == "CM" and m["turno_despegue"] == 4 - int(llegada)
    # un paquete tiene un solo comandante de mision
    r = alfa.post(f"{base}/misiones", json={**cuerpo, "nombre": "Arpia"})
    assert r.status_code == 400 and "comandante" in r.json()["detail"]
    r = alfa.post(f"{base}/misiones", json={**cuerpo, "ota": {**datos, "funcion": "ACM", "armamento_primario": "MPA"}})
    assert r.status_code == 400 and "aire-superficie" in r.json()["detail"]
    r = alfa.post(f"{base}/misiones", json={**cuerpo, "ota": None})
    assert r.status_code == 400 and "paquete" in r.json()["detail"]  # punto de reunion sin paquete
    r = alfa.post(f"{base}/misiones", json={**cuerpo, "ota": {**datos, "funcion": "ACM", "tot_turno": 99}})
    assert r.status_code == 400 and "despegar" in r.json()["detail"]
    # el documento
    o = alfa.get(f"{base}/misiones/ota").json()
    assert o["bando"] == "azul" and o["encabezado"].startswith("ENT / A-")
    assert any(x.endswith(" / 004 / CFA / CM //") for x in o["asignacion"])
    [f] = o["misiones"]
    assert "/ PTELA / BOCONO / 04CFA / 1OT /" in f["datmi"] and f["datmi"].endswith("/ 1 / BBU / MPA / 31701 //")
    assert f["ruta"].startswith(ota.codigo_lugar("Base Azul") + " / RV1 /") and f["locob"][0].startswith("LOCOB / ")
    assert alfa.get(f"{base}/misiones/ota.docx").content[:2] == b"PK"
    assert "DATMI" in alfa.get(f"{base}/misiones/ota.html").text
    assert api("bravo").get(f"{base}/misiones/ota?bando=azul").json()["misiones"] == []  # cada bando, la suya
    assert prof.get(f"{base}/misiones/ota?bando=azul").json()["misiones"]


def test_api_la_escolta_entra_en_el_paquete(api):
    prof, base, *_ = _preparar(api)
    ba = _base_aerea(prof, base, lat=0.0, lon=0.3)
    alfa = api("alfa")
    aterr = {"tipo": "aterrizaje", "lat": ba["lat"], "lon": ba["lon"], "base_id": ba["id"]}
    r = alfa.post(f"{base}/misiones", json={
        "rol": "INTERDICCION", "base_id": ba["id"], "modelo": "f16", "aeronaves": 2, "puntos": [{"tipo": "blanco", "lat": 1.0, "lon": 0.3}, aterr],
        "ota": {"paquete": "ARPIA", "funcion": "CM", "armamento_primario": "BMK"}, "escolta": {"base_id": ba["id"], "modelo": "f16", "aeronaves": 2}})
    assert r.status_code == 200, r.text
    escolta = next(m for m in alfa.get(base).json()["misiones"] if m["rol"] == "ESCOLTA")
    assert escolta["ota"]["paquete"] == "ARPIA" and ota.ARMAMENTO[escolta["ota"]["armamento_primario"]][1] == "aa"


# ---------- motor ----------
def _con_ota(db, m, **datos):
    m.ota_json = json.dumps(datos)
    db.commit()


def test_el_paquete_se_espera_en_el_punto_de_reunion(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    rapido = _caza(db_session, esc, nombre="Rapido", lat=0.2)
    lento = _caza(db_session, esc, nombre="Lento", lat=1.5, velocidad_kmh=100)
    ruta = [P("paso", 55, reunion=True), P("orbita", 100, turnos=1), aterrizaje(base)]
    m1 = _mision(db_session, esc, "CAP", ruta, unidad=rapido)
    m2 = _mision(db_session, esc, "CAP", ruta, unidad=lento)
    for m in (m1, m2):
        _con_ota(db_session, m, paquete="TELA", armamento_primario="MPA")
    _avanzar(db_session, esc)
    _refrescar(db_session, m1, m2, rapido)
    assert m1.indice == 0 and "espera" in m1.resultado and rapido.arma_elegida == "MPA"
    for _ in range(3):
        _avanzar(db_session, esc)
    _refrescar(db_session, m1, m2)
    assert m1.indice >= 1 and m2.indice >= 1
    assert any("se reunió" in e.descripcion for e in db_session.query(Evento))


def test_sin_los_demas_sigue_tras_la_espera_maxima(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    solo = _caza(db_session, esc, lat=0.2)
    lejos = _caza(db_session, esc, lat=8.0, velocidad_kmh=50)
    ruta = [P("paso", 55, reunion=True), P("orbita", 100, turnos=1), aterrizaje(base)]
    m1 = _mision(db_session, esc, "CAP", ruta, unidad=solo)
    m2 = _mision(db_session, esc, "CAP", ruta, unidad=lejos)
    for m in (m1, m2):
        _con_ota(db_session, m, paquete="X")
    for _ in range(ota.ESPERA_REUNION_MAX + 2):
        _avanzar(db_session, esc)
    _refrescar(db_session, m1)
    assert m1.indice >= 1 and db_session.get(Mision, m1.id).estado in ("en_curso", "cumplida")
    assert any("No se completó la reunión" in e.descripcion for e in db_session.query(Evento))


def test_el_perfil_del_punto_cambia_la_altura_del_grupo(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    caza = _caza(db_session, esc, lat=0.2, velocidad_kmh=100)
    _mision(db_session, esc, "RECO", [P("paso", 400, perfil="rasante"), P("paso", 800), aterrizaje(base)], unidad=caza)
    _avanzar(db_session, esc)
    _avanzar(db_session, esc)
    _refrescar(db_session, caza)
    assert caza.perfil_vuelo == "rasante"
