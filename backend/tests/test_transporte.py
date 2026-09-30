"""Unidades anfibias y helitransportadas: embarcar, viajar a bordo, desembarcar, daño a bordo."""

from app.engine import transporte, vision
from app.models.evento import Evento
from tests.conftest import TerrenoFalso
from tests.test_ciclo_vuelo import _caza, _orden, _refrescar
from tests.test_orders import _avanzar, _escenario, _unidad

MAR = TerrenoFalso(lambda lat, lon: "agua" if lon < 0.47 else "llano")  # costa en lon 0,47: tierra al este
MAR_SUR = TerrenoFalso(lambda lat, lon: "agua" if lat < -0.001 else "llano")  # mar al sur del ecuador


def _buque(db, esc, **kw):
    return _unidad(db, esc, **{**dict(nombre="LST", tipo="naval", clase="buque_desembarco", velocidad_kmh=35, lat=0.0, lon=0.0), **kw})


def test_embarque_y_capacidad(db_session):
    esc = _escenario(db_session)
    lst = _buque(db_session, esc)
    inf = _unidad(db_session, esc, nombre="Inf", clase="infanteria", lat=0.01, lon=0.0)
    lejos = _unidad(db_session, esc, nombre="Lejos", clase="infanteria", lat=0.5, lon=0.0)
    helo = _caza(db_session, esc, nombre="Helo", clase="helicoptero_artillado", modelo="", lat=0.0, lon=0.0)
    tanque = _unidad(db_session, esc, nombre="Tk", clase="blindado", lat=0.0, lon=0.0)
    todas = [lst, inf, lejos, helo, tanque]
    assert transporte.error_de_embarque(inf, lst, todas) is None
    assert "acerquese" in transporte.error_de_embarque(lejos, lst, todas)
    assert "ligeras" in transporte.error_de_embarque(tanque, helo, todas)
    assert transporte.error_de_embarque(tanque, lst, todas) is None
    assert transporte.error_de_embarque(inf, tanque, todas)  # un tanque no transporta
    for k in range(3):
        _unidad(db_session, esc, nombre=f"A{k}", clase="infanteria", lat=0.0, lon=0.0, transporte_id=lst.id)
    todas = db_session.query(type(lst)).all()
    assert "carga maxima" in transporte.error_de_embarque(inf, lst, todas)


def test_viaje_a_bordo_oculto_y_desembarco_en_la_costa(db_session):
    esc = _escenario(db_session)
    lst = _buque(db_session, esc, lat=0.0, lon=0.0)
    inf = _unidad(db_session, esc, nombre="Inf", clase="infanteria", lat=0.01, lon=0.0)
    enemigo = _unidad(db_session, esc, nombre="Vigia", bando="rojo", lat=0.02, lon=0.0, deteccion_km=50)
    _orden(db_session, esc, inf, "embarcar", objetivo=lst)
    _avanzar(db_session, esc, MAR)
    _refrescar(db_session, inf, lst)
    assert inf.transporte_id == lst.id and (inf.lat, inf.lon) == (lst.lat, lst.lon)
    assert inf not in vision.unidades_visibles([lst, inf, enemigo], "rojo", MAR)  # a bordo no se la ve
    # una orden a la unidad embarcada se rechaza
    o = _orden(db_session, esc, inf, "mover", waypoints=[[0.1, 0.0]])
    # el buque navega hasta 0,45 (agua) y desembarca en 0,49 (tierra, a 4,4 km)
    d = _orden(db_session, esc, lst, "desembarcar", waypoints=[[0.0, 0.45], [0.0, 0.49]])
    _avanzar(db_session, esc, MAR)
    _refrescar(db_session, inf, lst, o, d)
    assert o.estado == "rechazada" and "a bordo" in o.resultado
    assert lst.lon > 0.3 and inf.transporte_id == lst.id  # todavia viaja (35 km/h: no llego)
    for _ in range(2):
        _orden(db_session, esc, lst, "desembarcar", waypoints=[[0.0, 0.45], [0.0, 0.49]])
        _avanzar(db_session, esc, MAR)
    _refrescar(db_session, inf, lst)
    assert inf.transporte_id is None and abs(inf.lon - 0.49) < 0.01
    assert any("desembarco" in e.descripcion for e in db_session.query(Evento).all())


def test_las_tropas_a_bordo_sufren_el_dano_del_transporte(db_session):
    esc = _escenario(db_session)
    lst = _buque(db_session, esc, lat=0.0, lon=0.0, fuerza=100)
    inf = _unidad(db_session, esc, nombre="Inf", clase="infanteria", lat=0.0, lon=0.0, transporte_id=lst.id)
    frag = _unidad(db_session, esc, nombre="Frag", bando="rojo", tipo="naval", clase="fragata", lat=0.1, lon=0.0, alcance_km=60, deteccion_km=60)
    _orden(db_session, esc, frag, "atacar", objetivo=lst)
    _avanzar(db_session, esc, MAR)
    _refrescar(db_session, lst, inf)
    perdida = 100 - lst.fuerza
    assert perdida > 0 and 100 - inf.fuerza == __import__("pytest").approx(perdida * transporte.DANO_A_BORDO, abs=0.05)


def test_api_embarcar_y_desembarcar(api, monkeypatch):
    from app import state as state_mod
    from app.engine import orders as orders_mod
    from app.routers import ordenes as router_ordenes
    from app.routers import unidades as router_unidades
    from tests.test_api import _preparar

    for modulo in (orders_mod, state_mod, router_unidades, router_ordenes):
        monkeypatch.setattr(modulo, "get_terreno", lambda: MAR_SUR)
    prof, base, a, r1, r2 = _preparar(api)
    r = prof.post(f"{base}/unidades", json=dict(nombre="LST", bando="azul", tipo="naval", clase="buque_desembarco", lat=-0.01, lon=0.0))
    assert r.status_code == 200, r.text
    lst = r.json()
    azul = api("alfa")
    r = azul.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "embarcar", "objetivo_unidad_id": lst["id"]})
    assert r.status_code == 200, r.text
    r = azul.post(f"{base}/ordenes", json={"unidad_id": lst["id"], "tipo": "desembarcar", "waypoints": [[0.0, 0.3]]})
    assert r.status_code == 400 and "a bordo" in r.json()["detail"]  # aun no embarco (se resuelve al avanzar)
    r = azul.post(f"{base}/ordenes", json={"unidad_id": r1["id"], "tipo": "embarcar", "objetivo_unidad_id": lst["id"]})
    assert r.status_code == 404  # enemiga: no es propia
