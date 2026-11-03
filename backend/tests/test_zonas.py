"""Areas de referencia y zonas: patrulla de area, zonas de exclusion y de no vuelo (engine/zonas.py)."""

import json

from app.engine import geo, tiempo_real, zonas
from app.models.aar import Combate
from app.models.evento import Evento
from app.models.zona import Zona
from tests.test_api import _preparar
from tests.test_orders import _escenario, _unidad
from tests.test_tiempo_real import CAZA, _correr, _orden, mundo_limpio  # noqa: F401 - fixture automatica

CUADRO = [[-0.2, -0.2], [-0.2, 0.2], [0.2, 0.2], [0.2, -0.2]]  # ~44 km de lado alrededor de (0, 0)


def _zona(db, esc, tipo, bando="azul", puntos=CUADRO, armas=False, nombre="Z"):
    z = Zona(escenario_id=esc.id, bando=bando, tipo=tipo, nombre=nombre, puntos_json=json.dumps(puntos), armas=armas)
    db.add(z)
    db.commit()
    return z


def _avisos(db, bando, texto):
    return [e for e in db.query(Evento).filter(Evento.tipo == "zona", Evento.bando_destino == bando) if texto in e.descripcion]


def test_punto_dentro_del_poligono():
    p = [tuple(x) for x in CUADRO]
    assert zonas.dentro(0.0, 0.0, p) and zonas.dentro(0.19, -0.19, p)
    assert not zonas.dentro(0.3, 0.0, p) and not zonas.dentro(0.0, -0.25, p)


def test_intrusion_en_zona_de_exclusion_avisa_al_dueno_y_pausa(db_session):
    esc = _escenario(db_session)
    esc.pausa_auto_json = json.dumps({"zona": True})
    esc.estado = "activo"
    db_session.commit()
    _zona(db_session, esc, "exclusion", nombre="Litoral")
    _unidad(db_session, esc, nombre="Radar", deteccion_km=80)
    intruso = _unidad(db_session, esc, nombre="Patrulla roja", bando="rojo", lat=0.35, lon=0.0, velocidad_kmh=60)
    _orden(db_session, esc, intruso, "mover", waypoints=[[0.0, 0.0]])
    _correr(db_session, esc, 1500)  # 17 km a 60 km/h: entra a los ~17 minutos
    assert _avisos(db_session, "azul", "zona de exclusión «Litoral»")
    assert esc.estado == "pausado" and "Intrusión" in esc.pausa_motivo
    antes = len(_avisos(db_session, "azul", "Litoral"))
    esc.estado = "activo"
    _correr(db_session, esc, 600)
    assert len(_avisos(db_session, "azul", "Litoral")) == antes  # se avisa al entrar, no a cada paso


def test_zona_de_no_vuelo_del_director_avisa_al_bando_del_intruso(db_session):
    esc = _escenario(db_session)
    _zona(db_session, esc, "no_vuelo", bando="todos", nombre="Capital")
    c = _unidad(db_session, esc, nombre="Caza", lat=-0.5, **CAZA)
    tanque = _unidad(db_session, esc, nombre="Tanque", bando="rojo", lat=-0.3, velocidad_kmh=40)
    _orden(db_session, esc, tanque, "mover", waypoints=[[0.0, 0.0]])
    _orden(db_session, esc, c, "mover", waypoints=[[0.5, 0.0]])
    _correr(db_session, esc, 300)
    assert _avisos(db_session, "azul", "Caza entró a la zona de no vuelo «Capital»")
    assert not _avisos(db_session, "rojo", "Tanque")  # la de no vuelo es solo para aeronaves


def test_con_armas_en_la_zona_se_tira_aunque_la_doctrina_las_retenga(db_session):
    esc = _escenario(db_session)  # superficie: retenido por defecto (no tira sin orden)
    azul = _unidad(db_session, esc, nombre="Artilleria", alcance_km=20, deteccion_km=30)
    rojo = _unidad(db_session, esc, nombre="Infiltrado", bando="rojo", lat=0.1, lon=0.0, velocidad_kmh=0)
    _correr(db_session, esc, 120)
    assert rojo.fuerza == 100
    _zona(db_session, esc, "exclusion", armas=True)
    _correr(db_session, esc, 300)
    assert rojo.fuerza < 100 and db_session.query(Combate).filter(Combate.defensor_id == rojo.id).count() >= 0
    assert azul.estado == "activa"


def test_la_patrulla_de_area_recorre_el_poligono_y_ataca_lo_que_entra(db_session):
    esc = _escenario(db_session)
    z = _zona(db_session, esc, "patrulla", puntos=[[0.0, 0.0], [0.0, 1.0], [0.5, 1.0], [0.5, 0.0]])
    c = _unidad(db_session, esc, nombre="Caza", **CAZA)
    o = _orden(db_session, esc, c, "patrullar", waypoints=[[0.25, 0.5]], detalle=json.dumps({"zona": z.id}))
    assert o.estado == "en_ejecucion" and c.mision == ""
    visitados = set()
    for _ in range(40):
        _correr(db_session, esc, 60)
        for i, v in enumerate(zonas.puntos(z)):
            if geo.distancia_km(c.lat, c.lon, *v) < 5:
                visitados.add(i)
    assert len(visitados) >= 3  # va de vertice en vertice
    fuera = _unidad(db_session, esc, nombre="Afuera", bando="rojo", lat=0.9, lon=0.5, **CAZA)
    adentro = _unidad(db_session, esc, nombre="Adentro", bando="rojo", lat=0.25, lon=0.6, **CAZA)
    _correr(db_session, esc, 300)
    assert adentro.fuerza < 100 and fuera.fuerza == 100
    assert tiempo_real.mundo_de(esc.id).patrulla_idx.get(c.id) is not None


def test_api_zonas_por_bando_y_patrulla_de_area(api):
    prof, base, a, r1, r2 = _preparar(api)
    alfa, bravo = api("alfa"), api("bravo")
    r = alfa.post(f"{base}/zonas", json={"tipo": "patrulla", "nombre": "Sector Norte", "puntos": CUADRO})
    assert r.status_code == 200, r.text
    zona = r.json()
    assert zona["bando"] == "azul" and len(zona["puntos"]) == 4
    r = alfa.post(f"{base}/zonas", json={"tipo": "exclusion", "nombre": "Puerto", "puntos": CUADRO, "armas": True})
    assert r.json()["armas"] is True
    r = prof.post(f"{base}/zonas", json={"tipo": "no_vuelo", "nombre": "Capital", "puntos": CUADRO[:3]})
    assert r.json()["bando"] == "todos" and r.json()["armas"] is False
    assert {z["nombre"] for z in bravo.get(f"{base}/zonas").json()} == {"Capital"}  # no ve las del azul
    assert bravo.delete(f"{base}/zonas/{zona['id']}").status_code == 404
    assert alfa.patch(f"{base}/zonas/{zona['id']}", json={"armas": True}).status_code == 400  # patrulla: sin armas
    # una unidad de tierra patrulla un area, pero no orbita sobre un punto
    r = alfa.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "patrullar", "waypoints": [[0.1, 0.1]]})
    assert r.status_code == 400
    r = alfa.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "patrullar", "zona_id": zona["id"]})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "en_ejecucion" and json.loads(r.json()["detalle"]) == {"zona": zona["id"]}
    assert "zonas" in alfa.get(base).json()
    assert alfa.delete(f"{base}/zonas/{zona['id']}").status_code == 200
