"""Puntos medios de impacto (PMI): A-3 los pide, A-2 recibe la propuesta sobre la pista y la entrega, y con ellos el
ataque a la pista hace todo su daño (engine/pmi.py, routers/pmi.py)."""

from types import SimpleNamespace

from app.engine import geo, pmi
from app.models.pmi import PedidoPmi
from app.models.usuario import Usuario
from sqlalchemy.orm import sessionmaker
from tests.test_api import _preparar

SVPR = (8.28472, -62.76389)  # Base Aerea Luis Mendez (Ciudad Guayana): pista 08/26 de 2038 m en el plano


def _base(lat, lon, nombre="BA"):
    return SimpleNamespace(lat=lat, lon=lon, nombre=nombre, clase="base_aerea", pista_m=None)


def test_los_cortes_dejan_tramos_mas_cortos_que_la_franja_minima():
    assert pmi.cortes(2038) == 2 and pmi.cortes(3000) == 3 and pmi.cortes(700) == 1
    for largo in (900, 2038, 3000, 3600):
        assert largo / (pmi.cortes(largo) + 1) < pmi.MOS_M


def test_la_propuesta_va_sobre_el_eje_de_la_pista_real():
    puntos, pista = pmi.proponer(_base(*SVPR))
    if pista["estimada"]:  # sin los planos de los aerodromos (solo en el paquete de datos de mapa)
        return
    assert pista["ref"] == "08/26" and pista["largo_m"] == 2038 and len(puntos) == 2
    (la, loa), (lb, lob) = pista["extremos"]
    for k, p in enumerate(puntos, 1):
        a_cabecera = geo.distancia_km(la, loa, p["lat"], p["lon"]) * 1000
        assert abs(a_cabecera - 2038 * k / 3) < 15 and p["id"] == f"PMI-{k:02d}"


def test_sin_plano_la_pista_se_estima_centrada_en_la_base():
    puntos, pista = pmi.proponer(_base(30.0, -40.0))
    assert pista["estimada"] and pista["largo_m"] == 3000 and len(puntos) == 3
    assert geo.distancia_km(30.0, -40.0, puntos[1]["lat"], puntos[1]["lon"]) < 0.01  # el corte del medio, en la base


def test_sin_pmi_la_pista_recibe_la_mitad_del_dano():
    con = {("azul", 7)}
    assert pmi.factor_pista("azul", 7, con) == 1.0
    assert pmi.factor_pista("azul", 8, con) == pmi.FACTOR_SIN_PMI == 0.5
    assert pmi.factor_pista("rojo", 7, con) == 0.5  # los PMI son del bando que los pidio


def _puesto(api, nombre, puesto):
    with sessionmaker(bind=api.engine)() as db:
        db.query(Usuario).filter(Usuario.username == nombre).update({"puesto": puesto})
        db.commit()


def test_api_a3_pide_a2_propone_ajusta_y_entrega(api):
    prof, base, a, r1, r2 = _preparar(api)
    ba = prof.post(f"{base}/unidades", json=dict(nombre="BA Roja", bando="rojo", tipo="base", clase="base_aerea",
                                                lat=SVPR[0], lon=SVPR[1])).json()
    alfa = api("alfa")
    _puesto(api, "alfa", "a2")
    r = alfa.post(f"{base}/pmi", json={"base_id": ba["id"]})
    assert r.status_code == 403 and "Operaciones" in r.json()["detail"]  # pedir es de A-3
    _puesto(api, "alfa", "a3")
    assert alfa.post(f"{base}/pmi", json={"base_id": a["id"]}).status_code == 400  # una unidad propia, no una base enemiga
    r = alfa.post(f"{base}/pmi", json={"base_id": ba["id"]})
    assert r.status_code == 200, r.text
    pedido = r.json()
    assert pedido["estado"] == "pedido" and pedido["pedido_por"].startswith("A-3")
    assert alfa.post(f"{base}/pmi", json={"base_id": ba["id"]}).status_code == 400  # ya pedido
    assert alfa.post(f"{base}/pmi/{pedido['id']}/propuesta").status_code == 403  # proponer es de A-2
    _puesto(api, "alfa", "a2")
    prop = alfa.post(f"{base}/pmi/{pedido['id']}/propuesta").json()
    assert len(prop["puntos"]) >= 1 and prop["mos_m"] == pmi.MOS_M
    lejos = [{"id": "PMI-01", "lat": SVPR[0] + 0.2, "lon": SVPR[1]}]
    r = alfa.post(f"{base}/pmi/{pedido['id']}/entregar", json={"puntos": lejos})
    assert r.status_code == 400 and "no está sobre su pista" in r.json()["detail"]
    ajustados = [{**p, "lat": p["lat"] + 0.0002} for p in prop["puntos"]]  # A-2 los corre un poco
    r = alfa.post(f"{base}/pmi/{pedido['id']}/entregar", json={"puntos": ajustados})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "entregado" and r.json()["entregado_por"].startswith("A-2")
    assert r.json()["puntos"][0]["lat"] == round(ajustados[0]["lat"], 6)
    estado = alfa.get(f"{base}/pmi").json()
    assert [p["estado"] for p in estado] == ["entregado"]
    assert api("bravo").get(f"{base}/pmi").json() == []  # el otro bando no los ve
    with sessionmaker(bind=api.engine)() as db:
        assert pmi.entregados(db, db.get(PedidoPmi, pedido["id"]).escenario_id) == {("azul", ba["id"])}


def _dano_pista_en_vivo(db, con_pmi: bool) -> tuple[float, float]:
    """Una bateria azul ataca la pista de una base roja en tiempo real; devuelve (perdida de fuerza, daño a la pista)."""
    from app.engine import bases, tiempo_real
    from tests.test_orders import _escenario, _unidad
    from tests.test_tiempo_real import _correr, _orden

    tiempo_real.MUNDOS.clear()
    esc = _escenario(db)
    base = _unidad(db, esc, nombre="BA Roja", bando="rojo", tipo="base", clase="base_aerea", velocidad_kmh=0, lat=0.0)
    art = _unidad(db, esc, nombre="Art", bando="azul", clase="artilleria", lat=0.1, alcance_km=30, fuerza=100, municion=100)
    if con_pmi:
        db.add(PedidoPmi(escenario_id=esc.id, bando="azul", base_id=base.id, estado="entregado", puntos_json="[]"))
        db.commit()
    _orden(db, esc, art, "atacar", objetivo=base, detalle="pista")
    _correr(db, esc, 600)
    db.refresh(base)
    return 100 - base.fuerza + 0.0, bases.dano(base, "pista")


def test_en_vivo_el_ataque_a_la_pista_sin_pmi_hace_la_mitad(db_session):
    perdida_sin, pista_sin = _dano_pista_en_vivo(db_session, con_pmi=False)
    perdida_con, pista_con = _dano_pista_en_vivo(db_session, con_pmi=True)
    assert perdida_sin > 0 and perdida_con > 0
    # daño a la pista por punto de fuerza perdido: con PMI, el doble que sin ellos
    assert pista_con / perdida_con == __import__("pytest").approx(2 * pista_sin / perdida_sin, rel=0.05)
