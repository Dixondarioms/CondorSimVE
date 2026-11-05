"""Tropas aerotransportadas: el avion de transporte embarca en la base y lanza a los paracaidistas sobre la zona."""

import json

import pytest

from app.engine import catalogo, tiempo_real, transporte
from app.models.evento import Evento
from app.models.orden import Orden
from tests.conftest import TerrenoFalso
from tests.test_orders import _escenario, _unidad

TIERRA = TerrenoFalso(lambda lat, lon: "agua" if lon < -0.5 else "llano")


def _avion(db, esc, **kw):
    return _unidad(db, esc, **{**dict(nombre="C-130", tipo="aerea", clase="avion_transporte", modelo="c130h",
                                     velocidad_kmh=540, alcance_km=0, deteccion_km=20, autonomia_km=3800,
                                     combustible=3800, en_tierra=True), **kw})


def _base(db, esc, **kw):
    return _unidad(db, esc, **{**dict(nombre="BA", tipo="base", clase="base_aerea", velocidad_kmh=0, alcance_km=25), **kw})


def _dar(db, esc, u, tipo, objetivo=None, waypoints=None):
    o = Orden(escenario_id=esc.id, unidad_id=u.id, tipo=tipo, objetivo_unidad_id=objetivo.id if objetivo else None,
              waypoints_json=json.dumps(waypoints or []), turno_emitida=1)
    db.add(o)
    db.flush()
    tiempo_real.aplicar_orden(db, esc, o, u)
    db.commit()
    return o


def _correr(db, esc, segundos, paso=300):
    for _ in range(int(segundos // paso)):
        tiempo_real.paso(db, esc, paso, TIERRA)
    db.commit()


def test_catalogo_y_capacidad():
    assert catalogo.obtener("avion_transporte", "aerea").movilidad == "aerea"
    assert catalogo.obtener("paracaidistas", "terrestre").movilidad == "ligera"
    c130 = type("U", (), dict(clase="avion_transporte", modelo="c130h", aeronaves=1))()
    il76 = type("U", (), dict(clase="avion_transporte", modelo="il76md", aeronaves=2))()
    an26 = type("U", (), dict(clase="avion_transporte", modelo="an26", aeronaves=1))()
    assert (transporte.capacidad(c130), transporte.capacidad(il76), transporte.capacidad(an26)) == (2, 6, 1)


def test_embarca_solo_en_tierra_y_solo_ligeras(db_session):
    esc = _escenario(db_session)
    avion = _avion(db_session, esc)
    para = _unidad(db_session, esc, nombre="Para", clase="paracaidistas", lat=0.01)
    tanque = _unidad(db_session, esc, nombre="Tk", clase="blindado", lat=0.01)
    todas = [avion, para, tanque]
    assert transporte.error_de_embarque(para, avion, todas) is None
    assert "ligeras" in transporte.error_de_embarque(tanque, avion, todas)
    # estacionado lejos en la plataforma: se sube en la base
    base = _base(db_session, esc, lat=0.0, lon=0.0)
    avion.lat, avion.base_id = 0.09, base.id
    assert "acerquese" in transporte.error_de_embarque(para, avion, todas)  # sin la base, mide al avion
    todas.append(base)
    assert transporte.error_de_embarque(para, avion, todas) is None
    avion.en_tierra = False
    assert "aterrícelo" in transporte.error_de_embarque(para, avion, todas)


def test_vuela_salta_dispersos_y_regresa(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc)
    avion = _avion(db_session, esc, base_id=base.id)
    para = _unidad(db_session, esc, nombre="Para", clase="paracaidistas", fuerza=100.0, lat=0.0, lon=0.0, transporte_id=avion.id)
    inf = _unidad(db_session, esc, nombre="Inf", clase="infanteria", lat=0.0, lon=0.0, transporte_id=avion.id)
    vigia = _unidad(db_session, esc, nombre="Vigia", bando="rojo", lat=0.6, lon=0.0, deteccion_km=60)
    assert transporte.error_de_salto(avion, [0.5, 0.0], TIERRA, [avion, para, inf]) is None
    assert "tierra firme" in transporte.error_de_salto(avion, [0.0, -1.0], TIERRA, [avion, para, inf])
    o = _dar(db_session, esc, avion, "paracaidistas", waypoints=[[0.5, 0.0]])  # 55 km al norte
    _correr(db_session, esc, 1800)
    assert o.estado == "resuelta" and "lanzó en paracaídas" in o.resultado
    assert para.transporte_id is None and para.fuerza == pytest.approx(100 - transporte.PERDIDA_SALTO, abs=0.5)
    from app.engine import geo
    assert geo.distancia_km(para.lat, para.lon, 0.5, 0.0) <= transporte.DISPERSION_KM + transporte.RADIO_SALTO_KM + 0.1
    assert para.recarga_hasta and para.recarga_hasta > esc.sim_segundos - 1800 + 600  # se reagrupa antes de combatir
    assert inf.transporte_id == avion.id  # la infanteria comun no salta
    regreso = db_session.query(Orden).filter(Orden.unidad_id == avion.id, Orden.tipo == "aterrizar").one()
    assert regreso.detalle == "regreso tras el salto" and avion.en_tierra  # ya volvio a la base
    eventos = [e for e in db_session.query(Evento).all()]
    assert any(e.bando_destino == "rojo" and "Paracaidistas enemigos" in e.descripcion for e in eventos)
    assert vigia.estado == "activa"


def test_en_la_base_desembarca_donde_esta(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc)
    avion = _avion(db_session, esc, base_id=base.id, lat=0.07, lon=0.01)  # en la plataforma, a 8 km del centro
    inf = _unidad(db_session, esc, nombre="Inf", clase="infanteria", lat=0.07, lon=0.01, transporte_id=avion.id)
    assert transporte.error_de_desembarco(avion, None, TIERRA, [avion, inf]) is None
    o = _dar(db_session, esc, avion, "desembarcar")
    assert o.estado == "resuelta" and inf.transporte_id is None and (inf.lat, inf.lon) == (0.0, 0.0)  # bajan en la base
    avion.en_tierra = False
    inf.transporte_id = avion.id
    assert "aterrícelo" in transporte.error_de_desembarco(avion, [0.0, 0.0], TIERRA, [avion, inf])


def test_sin_paracaidistas_no_hay_salto(db_session):
    esc = _escenario(db_session)
    avion = _avion(db_session, esc)
    inf = _unidad(db_session, esc, nombre="Inf", clase="infanteria", transporte_id=avion.id)
    assert "no lleva paracaidistas" in transporte.error_de_salto(avion, [0.5, 0.0], TIERRA, [avion, inf])
    helo = _unidad(db_session, esc, nombre="Helo", tipo="aerea", clase="helicoptero_artillado")
    assert "avión de transporte" in transporte.error_de_salto(helo, [0.5, 0.0], TIERRA, [helo])


def test_api_lanzar_paracaidistas(api, monkeypatch):
    from app import state as state_mod
    from app.engine import orders as orders_mod
    from app.routers import ordenes as router_ordenes
    from app.routers import unidades as router_unidades
    from tests.test_api import _preparar

    for modulo in (orders_mod, state_mod, router_unidades, router_ordenes):
        monkeypatch.setattr(modulo, "get_terreno", lambda: TIERRA)
    prof, base, a, r1, r2 = _preparar(api)
    r = prof.post(f"{base}/unidades", json=dict(nombre="C-130", bando="azul", tipo="aerea", clase="avion_transporte", lat=0.0, lon=0.0))
    assert r.status_code == 200, r.text
    avion = r.json()
    azul = api("alfa")
    r = azul.post(f"{base}/ordenes", json={"unidad_id": avion["id"], "tipo": "paracaidistas", "waypoints": [[0.5, 0.0]]})
    assert r.status_code == 400 and "paracaidistas" in r.json()["detail"]
    r = azul.post(f"{base}/ordenes", json={"unidad_id": avion["id"], "tipo": "paracaidistas", "waypoints": []})
    assert r.status_code in (400, 422)
