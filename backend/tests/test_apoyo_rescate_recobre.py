"""Reabastecimiento en vuelo con tiempos y escolta (engine/apoyo_aereo.py), rescate de tripulaciones derribadas
(engine/rescate.py) y puntos de recobre operacional (engine/recobre.py)."""

import json
from types import SimpleNamespace

import pytest

from app.engine import apoyo_aereo, ota, plataformas, recobre, rescate
from app.models.evento import Evento
from app.models.mision import Mision
from app.models.unidad import Unidad
from tests.test_aeronaves import _base_aerea
from tests.test_api import _preparar
from tests.test_ciclo_vuelo import _base, _caza, _refrescar
from tests.test_misiones import P, _mision, aterrizaje
from tests.test_orders import _avanzar, _escenario, _unidad

_ID = iter(range(1, 10_000))


def _av(clase="caza", modelo="f16", bando="azul", lat=0.0, combustible=50.0, aeronaves=4, **kw):
    return SimpleNamespace(id=next(_ID), nombre=f"{clase}{modelo}", tipo="aerea", clase=clase, modelo=modelo, bando=bando,
                           lat=lat, lon=0.0, combustible=combustible, aeronaves=aeronaves, fuerza=100.0, estado="activa",
                           en_tierra=False, carga=100.0, **kw)


class _Bit:
    def poner(self, u, variable, valor, causa):
        setattr(u, variable, valor)


SIEMPRE = lambda x, b: True  # noqa: E731


# ---------- reabastecimiento en vuelo ----------
def test_la_cisterna_atiende_por_tiempo_primero_a_los_de_menos_combustible():
    kc = _av("cisterna", "kc135", aeronaves=1)
    grupos = [_av(combustible=30.0 + i, lat=0.1) for i in range(3)]
    escolta = _av(lat=0.05, aeronaves=2, combustible=99)
    r = apoyo_aereo.reabastecer(kc, [kc, *grupos, escolta], _Bit(), SIEMPRE)
    # pertiga: 6 min de enganche + 2212 kg / 2900 kg/min por F-16 -> 8 aeronaves en 60 min
    assert grupos[0].combustible == pytest.approx(100) and grupos[1].combustible == pytest.approx(100)
    assert grupos[2].combustible == 32.0
    assert [k for _, k, _ in r["receptores"]] == [4, 4] and 50 <= r["minutos"] <= 60
    assert kc.carga == pytest.approx(100 - r["kg"] / 68000 * 100)


def test_con_manguera_atiende_menos_que_con_pertiga():
    def atendidas(modelo):
        kc = _av("cisterna", modelo, aeronaves=1)
        grupos = [_av(combustible=30.0, lat=0.1) for _ in range(3)]
        r = apoyo_aereo.reabastecer(kc, [kc, *grupos, _av(lat=0.05, aeronaves=2, combustible=99)], _Bit(), SIEMPRE)
        return sum(k for _, k, _ in r["receptores"])
    assert atendidas("") < atendidas("kc135")


def test_sin_dos_escoltas_y_con_cazas_enemigos_cerca_la_cisterna_se_repliega():
    kc = _av("cisterna", "kc135", aeronaves=1)
    receptor = _av(combustible=40, lat=0.33)  # 37 km: lo alcanza la cisterna pero no la escolta (30 km)
    enemigo = _av(bando="rojo", lat=1.0)  # 111 km
    r = apoyo_aereo.reabastecer(kc, [kc, receptor, enemigo], _Bit(), SIEMPRE)
    assert r["receptores"] == [] and "se repliega" in r["motivo"] and receptor.combustible == 40
    assert apoyo_aereo.reabastecer(kc, [kc, receptor, enemigo], _Bit(), lambda x, b: False)["receptores"]  # no lo ve
    receptor.combustible = 40
    escolta = _av(lat=0.05, aeronaves=2, combustible=99)
    assert apoyo_aereo.reabastecer(kc, [kc, receptor, enemigo, escolta], _Bit(), SIEMPRE)["receptores"]


def test_el_aew_dirige_la_intercepcion():
    caza, enemigo = _av(lat=0.0), _av(bando="rojo", lat=0.5)
    aew = _av("alerta_temprana", "e3g", lat=1.5, aeronaves=1)
    escolta = _av(lat=1.55, aeronaves=2)
    assert apoyo_aereo.factor_control(caza, enemigo, [caza, enemigo, aew, escolta], SIEMPRE) == apoyo_aereo.FACTOR_CONTROL_AEW
    # sin escolta y con el caza enemigo a 111 km, el AEW se protege y no dirige la intercepcion
    assert apoyo_aereo.factor_control(caza, enemigo, [caza, enemigo, aew], SIEMPRE) == 1.0
    assert apoyo_aereo.factor_control(caza, enemigo, [caza, enemigo], SIEMPRE) == 1.0
    tanque = SimpleNamespace(tipo="terrestre", en_tierra=False, estado="activa")
    assert apoyo_aereo.factor_control(caza, tanque, [caza, aew], SIEMPRE) == 1.0


def test_estimacion_del_reabastecimiento():
    e = apoyo_aereo.estimar_aar(plataformas.catalogo.MODELOS["f16"], 4, 30.0, "pertiga")
    assert e["kg_por_aeronave"] == round(0.7 * 3160) and e["kg"] == 4 * e["kg_por_aeronave"]
    assert e["minutos"] == round(4 * (6 + 0.7 * 3160 / 2900))


# ---------- rescate ----------
class _Esc:
    semilla, derribados_json = 3, None


def test_las_tripulaciones_derribadas_esperan_el_rescate():
    esc = _Esc()
    d = rescate.registrar(esc, _av("caza", "su30", lat=1.0), 1.0, 5)
    assert d["tripulantes"] == 2 and d["estado"] == "aislado" and d["medio"] == "tierra"  # 2 tripulantes x 0,8
    assert rescate.registrar(esc, _av("dron_ataque", "mq9"), 1.0, 5) is None
    helo = _av("helicoptero_artillado", "mh60m", lat=1.02, aeronaves=1)
    assert [x["id"] for x in rescate.rescatar(esc, helo, 7)] == [d["id"]]
    assert rescate.lista(esc)[0]["estado"] == "rescatado" and rescate.resumen(esc, "azul")["rescatado"] == 2
    assert rescate.rescatar(esc, _av(lat=1.0), 7) == []  # un caza no rescata


def test_el_enemigo_cercano_puede_capturarlos_y_el_tiempo_los_pierde():
    esc = _Esc()
    rescate.registrar(esc, _av(lat=1.0), 1.0, 1)
    patrulla = SimpleNamespace(bando="rojo", estado="activa", tipo="terrestre", lat=1.05, lon=0.0, nombre="Patrulla")
    for t in range(2, 40):
        rescate.avanzar(esc, [patrulla], t)
        if rescate.lista(esc)[0]["estado"] != "aislado":
            break
    assert rescate.lista(esc)[0]["estado"] == "capturado" and rescate.lista(esc)[0]["por"] == "Patrulla"
    esc2 = _Esc()
    agua = SimpleNamespace(clase=lambda lat, lon: "agua")
    rescate.registrar(esc2, _av(lat=1.0), 1.0, 1, agua)
    rescate.avanzar(esc2, [], 1 + rescate.SUPERVIVENCIA_TURNOS["agua"])
    assert rescate.lista(esc2)[0]["estado"] == "perdido"


def test_el_estado_muestra_a_cada_bando_sus_tripulaciones(api, db_engine):
    prof, base, *_ = _preparar(api)
    from sqlalchemy.orm import sessionmaker

    from app.models.escenario import Escenario
    with sessionmaker(bind=db_engine)() as db:
        esc = db.get(Escenario, int(base.rsplit("/", 1)[1]))
        esc.derribados_json = json.dumps([{"id": 1, "bando": "azul", "lat": 5.0, "lon": 5.0, "turno": 1, "tripulantes": 2,
                                           "grupo": "Halcon", "medio": "tierra", "estado": "aislado", "turno_fin": None, "por": ""}])
        db.commit()
    assert len(api("alfa").get(base).json()["derribados"]) == 1
    assert api("bravo").get(base).json()["derribados"] == []  # no tiene unidades cerca
    assert api("alfa").get(base).json()["recuperacion"]["azul"]["aislado"] == 2


def test_una_mision_csar_rescata_a_la_tripulacion(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    helo = _caza(db_session, esc, nombre="Rescate", clase="helicoptero_artillado", modelo="mh60m", lat=0.1, velocidad_kmh=250)
    esc.derribados_json = json.dumps([{"id": 1, "bando": "azul", "lat": 0.5, "lon": 0.0, "turno": 1, "tripulantes": 1,
                                       "grupo": "Halcon", "medio": "tierra", "estado": "aislado", "turno_fin": None, "por": ""}])
    db_session.commit()
    _mision(db_session, esc, "CSAR", [P("orbita", 0.5 * 111.195, turnos=1), aterrizaje(base)], unidad=helo)
    _avanzar(db_session, esc)
    _avanzar(db_session, esc)
    db_session.refresh(esc)
    assert rescate.lista(esc)[0]["estado"] == "rescatado"
    assert any("rescató" in e.descripcion for e in db_session.query(Evento))


def test_el_derribo_en_vuelo_deja_tripulantes_aislados(db_session):
    esc = _escenario(db_session)
    caza = _caza(db_session, esc, nombre="Halcon", modelo="f16", aeronaves=4, lat=0.3)
    _unidad(db_session, esc, nombre="SAM", bando="rojo", tipo="terrestre", clase="antiaerea", lat=0.32, alcance_km=40,
            deteccion_km=80)
    for _ in range(3):
        _avanzar(db_session, esc)
    db_session.refresh(esc)
    db_session.refresh(caza)
    assert caza.estado == "destruida"
    datos = rescate.lista(esc)
    assert datos and all(d["grupo"] == "Halcon" for d in datos) and sum(d["tripulantes"] for d in datos) >= 3
    assert any(d["estado"] == "capturado" and d["por"] == "SAM" for d in datos)  # la antiaerea enemiga esta al lado


# ---------- puntos de recobre operacional ----------
def test_requisitos_y_rearme_del_pro():
    pro = SimpleNamespace(id=1, nombre="PRO Norte", clase="punto_recobre", tipo="base", bando="azul", estado="activa",
                          fuerza=100.0, personal=None, lat=0.0, lon=0.0, pista_m=0, existencias_json=None,
                          combustible=100.0, municion=100.0, stock_combustible=400.0, stock_municion=400.0)
    falta = recobre.deficiencias(pro, [pro])
    assert any("Seguridad" in f for f in falta) and any("Sin pista" in f for f in falta)
    assert recobre.turnos_rearme(pro, 2) == recobre.REARME_TURNOS
    pro.fuerza = 50.0  # 15 de 30
    assert recobre.turnos_rearme(pro, 2) == 2 and any("Personal" in f for f in recobre.deficiencias(pro))
    assert "no tiene pista" in plataformas.error_de_pista(plataformas.catalogo.MODELOS["f16"], pro)
    assert plataformas.error_de_pista(plataformas.catalogo.MODELOS["mh60m"], pro) is None
    pro.pista_m = 1200
    assert "más corta" not in (plataformas.error_de_pista(plataformas.catalogo.MODELOS["f16"], pro) or "")


# ---------- planificacion ----------
def test_api_la_cisterna_exige_dos_escoltas_y_el_punto_aer(api):
    prof, base, *_ = _preparar(api)
    ba = _base_aerea(prof, base, lat=0.0, lon=0.3, pista_m=3500)
    alfa = api("alfa")
    aterr = {"tipo": "aterrizaje", "lat": ba["lat"], "lon": ba["lon"], "base_id": ba["id"]}
    cuerpo = {"rol": "AAR", "base_id": ba["id"], "modelo": "kc135", "aeronaves": 1,
              "puntos": [{"tipo": "orbita", "lat": 1.0, "lon": 0.3, "turnos": 4}, aterr]}
    r = alfa.post(f"{base}/misiones/previsualizar", json=cuerpo)
    assert any("2 cazas de escolta" in e for e in r.json()["errores"])
    r = alfa.post(f"{base}/misiones", json={**cuerpo, "escolta": {"base_id": ba["id"], "modelo": "f16", "aeronaves": 2}})
    assert r.status_code == 200, r.text
    # un ataque con punto de reabastecimiento: la estimacion lo llena y la OTA trae la linea ABA AER
    ataque = {"rol": "INTERDICCION", "base_id": ba["id"], "modelo": "f16", "aeronaves": 2,
              "puntos": [{"tipo": "paso", "lat": 1.0, "lon": 0.3, "reabastecimiento": True}, {"tipo": "blanco", "lat": 2.5, "lon": 0.3}, aterr]}
    r = alfa.post(f"{base}/misiones/previsualizar", json=ataque).json()
    assert r["errores"] == [] and r["plan"]["puntos"][0]["reabastece"] and r["plan"]["aar"]["kg"] > 0
    assert alfa.post(f"{base}/misiones", json=ataque).status_code == 200
    o = alfa.get(f"{base}/misiones/ota").json()
    f = next(x for x in o["misiones"] if x["rol"] == "INTERDICCION")
    assert f["aba"] and f["aba"][0].startswith("ABA / 02CFA / AER /") and "+AER" in f["aba"][0]
    assert "(AER)" in f["ruta"]


def test_el_grupo_espera_un_turno_en_el_punto_aer_y_sigue(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    caza = _caza(db_session, esc, lat=0.2, velocidad_kmh=300, combustible=60)
    _caza(db_session, esc, nombre="KC", clase="cisterna", modelo="kc135", lat=0.5, carga=100, alcance_km=0)
    _caza(db_session, esc, nombre="Escolta", lat=0.52, aeronaves=2)
    m = _mision(db_session, esc, "RECO", [P("paso", 0.5 * 111.195, reabastecimiento=True), P("paso", 200), aterrizaje(base)],
                unidad=caza)
    _avanzar(db_session, esc)
    _refrescar(db_session, m, caza)
    assert m.indice == 0 and m.espera == -3 and caza.combustible == pytest.approx(100)
    _avanzar(db_session, esc)
    _refrescar(db_session, m)
    assert m.indice >= 1
    assert ota.CODIGOS_MISION["AAR"][0] == "AAR"
    assert db_session.query(Mision).count() == 1 and db_session.query(Unidad).count() == 4
