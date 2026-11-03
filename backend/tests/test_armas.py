"""Cargas de armamento por aeronave y existencias de armas en bases y buques (engine/armas.py)."""

import json

from app.engine import aeronaves, armas, ota, tiempo_real, weaponeering
from app.models.unidad import Unidad
from tests.test_api import _preparar
from tests.test_orders import _escenario, _unidad
from tests.test_tiempo_real import CAZA, _correr, _orden, mundo_limpio  # noqa: F401 - fixture automatica

BASE = dict(tipo="base", clase="base_aerea", velocidad_kmh=0, alcance_km=25)


def test_cargas_segun_el_modelo():
    f16 = armas.cargas_de("f16")
    assert set(f16) == {"aire_aire", "ataque", "antibuque", "sead", "reconocimiento"}
    assert f16["aire_aire"] == {"M120": 4, "M9X": 2} and "HPN" in f16["antibuque"] and "HRM" in f16["sead"]
    assert armas.carga_por_defecto("f16") == "aire_aire"
    assert "MA6" in armas.cargas_de("su30")["antibuque"]
    assert set(armas.cargas_de("e2d")) == {"reconocimiento"}  # sin armas
    assert armas.alcance_arma("M120") == 75 and armas.alcance_arma("BMK") == armas.ALCANCE_BOMBA_KM
    assert 0 < armas.pk("M9X") <= 1 and armas.pk("BBU") == armas.PK_GUIADA


def test_el_despegue_arma_al_grupo_desde_las_existencias_de_la_base(db_session):
    esc = _escenario(db_session)
    base = _unidad(db_session, esc, nombre="BA", **BASE)
    o = _orden(db_session, esc, base, "despegar", detalle=aeronaves.codificar("f16", 2, "Halcon", "antibuque"))
    g = db_session.query(Unidad).filter(Unidad.nombre == "Halcon").one()
    assert "carga antibuque" in o.resultado
    assert armas.datos(g)["quedan"] == {"HPN": 4, "M9X": 4} and g.municion == 100.0
    assert armas.existencias(base)["HPN"] == armas.inicial(base, "HPN") - 4


def test_cada_pasada_gasta_misiles_reales_y_sin_armas_vuelve(db_session):
    esc = _escenario(db_session)
    _unidad(db_session, esc, nombre="BA", lat=-0.5, **BASE)
    c = _unidad(db_session, esc, nombre="Caza", modelo="f16", aeronaves=2, **CAZA)
    armas.armar(c, "aire_aire")
    intruso = _unidad(db_session, esc, nombre="Intruso", bando="rojo", lat=0.3, lon=0.0, fuerza=100.0, aeronaves=4,
                      **{k: v for k, v in CAZA.items()})
    db_session.commit()
    _orden(db_session, esc, c, "atacar", objetivo=intruso)
    _correr(db_session, esc, 30)  # a 33 km: con el AIM-120 (75 km) ya tira
    assert armas.datos(c)["quedan"]["M120"] == 6 and c.municion < 100
    for _ in range(12):
        _correr(db_session, esc, tiempo_real.RECARGA_AIRE_AIRE_S)
        if intruso.estado != "activa" or not armas.utiles(c, intruso):
            break
    assert armas.datos(c)["quedan"]["M120"] < 6


def test_bombas_solo_desde_cerca_y_contra_superficie(db_session):
    esc = _escenario(db_session)
    c = _unidad(db_session, esc, nombre="Ataque", modelo="f16", aeronaves=2, **CAZA)
    armas.armar(c, "ataque")
    blanco = _unidad(db_session, esc, nombre="Deposito", bando="rojo", lat=0.4, lon=0.0, velocidad_kmh=0)
    avion = _unidad(db_session, esc, nombre="Avion", bando="rojo", lat=0.1, **CAZA)
    assert armas.utiles(c, blanco) == ["BGB"]
    assert armas.alcance(c, blanco) == 12  # GBU-10: 12 km
    assert armas.utiles(c, avion) == ["M9X"]  # solo la autodefensa sirve contra aviones
    assert armas.por_pasada(c, "BGB") == 2  # la mitad de las bombas de cada aeronave
    sin = _unidad(db_session, esc, nombre="Viejo", **CAZA)
    assert armas.alcance(sin, blanco) == sin.alcance_km  # sin carga: como antes


def test_al_rearmar_devuelve_lo_que_no_tiro_y_carga_de_nuevo(db_session):
    esc = _escenario(db_session)
    base = _unidad(db_session, esc, nombre="BA", **BASE)
    c = _unidad(db_session, esc, nombre="Caza", modelo="f16", aeronaves=1, en_tierra=True, base_id=base.id, **CAZA)
    armas.armar(c, "aire_aire", base)
    armas.gastar(c, "M120")
    antes = armas.existencias(base)["M120"]
    c.espera_hasta, c.espera_restante = 10.0, 1
    db_session.commit()
    _correr(db_session, esc, 30)
    assert armas.datos(c)["quedan"]["M120"] == 4
    assert armas.existencias(base)["M120"] == antes + 3 - 4  # devolvio 3 y tomo 4


def test_existencias_escasas_dan_carga_incompleta(db_session):
    esc = _escenario(db_session)
    base = _unidad(db_session, esc, nombre="BA", **BASE)
    base.existencias_json = json.dumps({"M120": 1, "M9X": 0})
    g = _unidad(db_session, esc, nombre="G", modelo="f16", aeronaves=2, **CAZA)
    texto = armas.armar(g, "aire_aire", base)
    assert "incompleta" in texto and armas.datos(g)["quedan"] == {"M120": 1, "M9X": 0}
    assert armas.error_de_carga("f16", "aire_aire", 2, base) is not None  # sin AIM-9X no despega con esa carga


def test_weaponeering_usa_la_cantidad_de_la_carga():
    w = weaponeering.calcular("BGB", "radar", dmpi=2, aeronaves=2, por_aeronave=4)
    assert w["por_aeronave"] == 4 and w["lleva"] == 8


def test_api_despegue_con_carga_ota_y_existencias(api):
    prof, base_url, a, r1, r2 = _preparar(api)
    alfa = api("alfa")
    ba = prof.post(f"{base_url}/unidades", json=dict(nombre="BA Sur", bando="azul", tipo="base", clase="base_aerea",
                                                    lat=-0.5, lon=0.0)).json()
    r = alfa.post(f"{base_url}/ordenes", json={"unidad_id": ba["id"], "tipo": "despegar", "modelo": "f16", "aeronaves": 2,
                                              "indicativo": "Rayo", "carga": "sead"})
    assert r.status_code == 200, r.text
    assert "carga sead" in r.json()["resultado"].lower()
    r = alfa.post(f"{base_url}/ordenes", json={"unidad_id": ba["id"], "tipo": "despegar", "modelo": "e2d", "aeronaves": 1,
                                              "carga": "ataque"})
    assert r.status_code == 400 and "no lleva la carga" in r.json()["detail"]
    est = alfa.get(base_url).json()
    rayo = next(u for u in est["unidades"] if u["nombre"] == "Rayo")
    assert rayo["armamento"]["nombre"] == "sead" and "AGM-88" in rayo["armamento_texto"]
    base_est = next(u for u in est["unidades"] if u["id"] == ba["id"])
    assert base_est["existencias_armas"]["HRM"] == armas.inicial(type("B", (), {"tipo": "base"})(), "HRM") - 4
    assert api("bravo").get(base_url).status_code == 200
    r = prof.put(f"{base_url}/unidades/{ba['id']}/existencias", json={"HRM": 0})
    assert r.status_code == 200 and r.json()["HRM"] == 0
    assert alfa.put(f"{base_url}/unidades/{ba['id']}/existencias", json={"HRM": 5}).status_code == 403
    assert ota.validar("CAP", "f16", None, {"carga": "ataque"})
    assert not ota.validar("CAP", "f16", None, {"carga": "aire_aire", "armamento_primario": "M120"})
    cat = alfa.get("/api/catalogo").json()
    assert cat["cargas"]["f16"]["aire_aire"]["M120"] == 4 and cat["armas"]["HPN"]["tipo"] == "ab"
