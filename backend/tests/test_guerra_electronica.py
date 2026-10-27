"""Guerra electronica (interferencia y escucha), radares y drones."""

from pathlib import Path

import pytest

from app.engine import aeronaves, catalogo, vision
from app.engine import guerra_electronica as ge_mod
from app.models.evento import Evento
from app.models.interferencia import Interferencia
from app.models.unidad import Unidad
from tests.conftest import TerrenoFalso
from tests.test_api import _preparar
from tests.test_ciclo_vuelo import _orden, _refrescar
from tests.test_orders import _avanzar, _escenario, _unidad

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
KM = 1 / 111.195  # grados de latitud por km
T = TerrenoFalso()


def _u(id_, bando, clase, km_norte=0.0, **kw):
    """Unidad suelta (sin base de datos) de la clase indicada, `km_norte` km al norte del origen."""
    c = catalogo.CLASES[clase]
    datos = dict(id=id_, nombre=f"{clase}-{id_}", bando=bando, tipo=c.tipo, clase=clase, lat=km_norte * KM, lon=0.0,
                 deteccion_km=c.deteccion_km, estado="activa", en_tierra=False)
    datos.update(kw)
    return Unidad(**datos)


def _zona(bando, km_norte=0.0, radio=25.0, unidad_id=99):
    return Interferencia(bando=bando, lat=km_norte * KM, lon=0.0, radio_km=radio, turno=1, unidad_id=unidad_id)


def _ge(db, esc, bando="azul", **kw):
    return _unidad(db, esc, **{**dict(nombre="GE", bando=bando, clase="guerra_electronica", alcance_km=40,
                                      deteccion_km=10, velocidad_kmh=35), **kw})


# ---------- catalogo ----------
def test_catalogo_de_sensores_guerra_electronica_y_drones_con_sus_imagenes():
    c = catalogo.CLASES
    assert c["radar"].solo_aereo and c["radar"].emisor and c["radar"].celula == "ge"
    assert c["guerra_electronica"].interferencia_km > 0 and c["guerra_electronica"].escucha_km > 0
    assert c["avion_ge"].interferencia_km > c["guerra_electronica"].interferencia_km
    assert c["antiaerea"].emisor and not c["antiaerea_portatil"].emisor  # la portatil es infrarroja
    assert all(c[x].dron and c[x].firma < 1 for x in ("dron_reconocimiento", "dron_ataque", "municion_merodeadora"))
    assert c["municion_merodeadora"].se_consume and not c["dron_ataque"].se_consume
    for m in ("uav_reco", "uav_armado", "merodeadora", "ge_aereo"):
        foto = catalogo.MODELOS[m].foto
        assert (FRONTEND / foto.lstrip("/")).is_file(), foto
    assert {"interferencia_km", "escucha_km", "firma", "dron", "celula", "solo_aereo", "emisor"} <= set(
        catalogo.como_dict(c["guerra_electronica"]))


# ---------- vision ----------
def test_los_drones_se_detectan_a_menos_distancia_por_su_firma_radar():
    ojo = _u(1, "azul", "caza", deteccion_km=40)
    assert vision.detecta(ojo, _u(2, "rojo", "caza", 30), T)
    assert not vision.detecta(ojo, _u(3, "rojo", "dron_reconocimiento", 30), T)  # 40 x 0,5 = 20 km
    assert vision.detecta(ojo, _u(4, "rojo", "dron_reconocimiento", 15), T)


def test_el_radar_ve_aviones_muy_lejos_pero_lo_que_esta_en_tierra_solo_de_cerca():
    radar = _u(1, "azul", "radar")  # 150 km
    assert vision.detecta(radar, _u(2, "rojo", "caza", 140), T)
    assert not vision.detecta(radar, _u(3, "rojo", "infanteria", 20), T)
    assert vision.detecta(radar, _u(4, "rojo", "infanteria", 5), T)
    assert not vision.detecta(radar, _u(5, "rojo", "caza", 20, en_tierra=True), T)  # estacionado en la pista


def test_un_sensor_interferido_ve_mucho_menos_y_un_radar_aun_menos():
    ge = ge_mod.Contexto([_zona("rojo", 0.0)])
    ojo = _u(1, "azul", "reconocimiento", deteccion_km=16)
    lejos = _u(2, "rojo", "infanteria", 10)
    assert vision.detecta(ojo, lejos, T) and not vision.detecta(ojo, lejos, T, ge=ge)  # 16 x 0,3 = 4,8 km
    assert vision.detecta(ojo, _u(3, "rojo", "infanteria", 2), T, ge=ge)  # a ojo siempre se ven 3 km
    radar = _u(4, "azul", "radar")
    assert not vision.detecta(radar, _u(5, "rojo", "caza", 40), T, ge=ge)  # 150 x 0,2 = 30 km
    assert vision.detecta(radar, _u(6, "rojo", "caza", 25), T, ge=ge)
    # la interferencia propia no degrada a los sensores propios
    assert vision.detecta(ojo, lejos, T, ge=ge_mod.Contexto([_zona("azul", 0.0)]))


def test_la_escucha_localiza_emisores_lejanos_pero_no_a_quien_no_emite():
    escucha = _u(1, "azul", "guerra_electronica")  # deteccion 10 km, escucha 120 km
    assert vision.detecta(escucha, _u(2, "rojo", "radar", 100), T)
    assert vision.detecta(escucha, _u(3, "rojo", "antiaerea", 100), T)
    assert not vision.detecta(escucha, _u(4, "rojo", "infanteria", 100), T)
    assert not vision.detecta(escucha, _u(5, "rojo", "radar", 130), T)
    interferidor = _u(6, "rojo", "guerra_electronica", 100)
    assert not vision.detecta(escucha, interferidor, T)  # callado no se lo oye...
    assert vision.detecta(escucha, interferidor, T, ge=ge_mod.Contexto([_zona("rojo", 300, unidad_id=6)]))  # ...emitiendo si


def test_el_interferidor_queda_visible_para_el_bando_interferido_mientras_emite():
    azul = _u(1, "azul", "infanteria")
    interferidor = _u(2, "rojo", "guerra_electronica", 300)
    ids = lambda us: {u.id for u in us}  # noqa: E731
    assert 2 not in ids(vision.unidades_visibles([azul, interferidor], "azul", T))
    ge = ge_mod.Contexto([_zona("rojo", 30, unidad_id=2)])
    assert 2 in ids(vision.unidades_visibles([azul, interferidor], "azul", T, ge=ge))


# ---------- resolucion del turno ----------
def test_interferir_crea_la_zona_que_rige_la_planificacion_siguiente_y_avisa_al_enemigo(db_session):
    esc = _escenario(db_session)
    ge_u = _ge(db_session, esc)
    o = _orden(db_session, esc, ge_u, "interferir", waypoints=[[20 * KM, 0.0]])
    _avanzar(db_session, esc)
    _refrescar(db_session, o)
    assert o.estado == "resuelta" and "radio de 25 km" in o.resultado
    zonas = ge_mod.contexto(db_session, esc).zonas  # planificacion del turno 2: rige la emitida en el turno 1
    assert [(z.bando, z.radio_km, z.turno, z.unidad_id) for z in zonas] == [("azul", 25.0, 1, ge_u.id)]
    avisos = db_session.query(Evento).filter(Evento.tipo == "guerra_electronica").all()
    assert [e.bando_destino for e in avisos] == ["rojo"]
    _avanzar(db_session, esc)  # sin renovarla, deja de regir
    assert ge_mod.contexto(db_session, esc).zonas == []


@pytest.mark.parametrize("caso", ["lejos", "sin_capacidad", "avion_en_tierra"])
def test_interferencias_imposibles_se_rechazan(db_session, caso):
    esc = _escenario(db_session)
    if caso == "sin_capacidad":
        u = _unidad(db_session, esc, nombre="Inf", clase="infanteria")
    elif caso == "avion_en_tierra":
        u = _unidad(db_session, esc, nombre="GE aereo", tipo="aerea", clase="avion_ge", alcance_km=60, en_tierra=True)
    else:
        u = _ge(db_session, esc)
    punto = [100 * KM, 0.0] if caso == "lejos" else [5 * KM, 0.0]
    o = _orden(db_session, esc, u, "interferir", waypoints=[punto])
    _avanzar(db_session, esc)
    _refrescar(db_session, o)
    assert o.estado == "rechazada", o.resultado
    assert db_session.query(Interferencia).count() == 0


def test_un_dron_enemigo_dentro_de_la_interferencia_pierde_el_enlace(db_session):
    esc = _escenario(db_session)
    ge_u = _ge(db_session, esc)
    dron = dict(bando="rojo", tipo="aerea", clase="dron_reconocimiento", velocidad_kmh=150, autonomia_km=1500)
    dentro = _unidad(db_session, esc, nombre="Dron cercano", lat=20 * KM, **dron)
    fuera = _unidad(db_session, esc, nombre="Dron lejano", lat=100 * KM, **dron)
    _orden(db_session, esc, ge_u, "interferir", waypoints=[[20 * KM, 0.0]])
    o1 = _orden(db_session, esc, dentro, "mover", waypoints=[[20 * KM, 1.0]])
    o2 = _orden(db_session, esc, fuera, "mover", waypoints=[[100 * KM, 1.0]])
    _avanzar(db_session, esc)
    _refrescar(db_session, o1, o2, dentro, fuera)
    assert o1.estado == "rechazada" and "Sin enlace" in o1.resultado and dentro.lon == 0.0
    assert o2.estado == "resuelta" and fuera.lon > 0.0


def _perdida_de_un_caza_atacado_por_antiaerea(db, interferida: bool) -> float:
    esc = _escenario(db)
    aa = _unidad(db, esc, nombre="AA", clase="antiaerea", alcance_km=20, deteccion_km=20)
    caza = _unidad(db, esc, nombre="Caza", bando="rojo", tipo="aerea", clase="caza", lat=10 * KM, alcance_km=80,
                   deteccion_km=60, velocidad_kmh=900)
    if interferida:
        ge_rojo = _ge(db, esc, bando="rojo", lat=30 * KM)
        _orden(db, esc, ge_rojo, "interferir", waypoints=[[0.0, 0.0]])
    o = _orden(db, esc, aa, "atacar", objetivo=caza)
    _avanzar(db, esc)
    _refrescar(db, caza, o)
    assert o.estado == "resuelta", o.resultado
    assert ("interferida" in o.resultado) == interferida
    return 100.0 - caza.fuerza


def test_la_antiaerea_guiada_por_radar_interferida_pierde_efecto_contra_los_aviones(db_session):
    normal = _perdida_de_un_caza_atacado_por_antiaerea(db_session, False)
    interferida = _perdida_de_un_caza_atacado_por_antiaerea(db_session, True)
    assert normal > 0 and interferida < normal


def test_la_municion_merodeadora_se_destruye_al_atacar(db_session):
    esc = _escenario(db_session)
    k = _unidad(db_session, esc, nombre="Kamikaze 1", tipo="aerea", clase="municion_merodeadora", alcance_km=5,
                deteccion_km=15, velocidad_kmh=180)
    blanco = _unidad(db_session, esc, nombre="Blindado rojo", bando="rojo", clase="blindado", lat=2 * KM)
    o = _orden(db_session, esc, k, "atacar", objetivo=blanco)
    _avanzar(db_session, esc)
    _refrescar(db_session, o, k, blanco)
    assert o.estado == "resuelta" and blanco.fuerza < 100
    assert k.estado == "destruida" and k.fuerza == 0
    assert any("impacto contra su blanco" in e.descripcion for e in db_session.query(Evento).all())


def test_los_drones_tienen_su_propio_tope_y_no_cuentan_para_el_de_aeronaves():
    caza = Unidad(tipo="aerea", clase="caza", aeronaves=4, estado="activa", bando="azul")
    dron = Unidad(tipo="aerea", clase="dron_reconocimiento", aeronaves=2, estado="activa", bando="azul")
    assert aeronaves.aeronaves_en_servicio([caza, dron]) == 4
    assert aeronaves.aeronaves_en_servicio([caza, dron], drones=True) == 2
    # quien llama pasa el conteo de la categoria del modelo (drones para un dron, tripuladas para un caza)
    base = Unidad(tipo="base", clase="base_aerea", estado="activa", fuerza=100.0)
    assert aeronaves.error_de_despegue(base, "uav_reco", 2, 0) is None
    motivo = aeronaves.error_de_despegue(base, "uav_reco", 2, catalogo.MAX_DRONES_BANDO - 1)
    assert motivo and "drones" in motivo
    motivo = aeronaves.error_de_despegue(base, "f16", 2, catalogo.MAX_AERONAVES_BANDO - 1)
    assert motivo and "aeronaves" in motivo


# ---------- API ----------
def _ge_api(prof, base):
    r = prof.post(f"{base}/unidades", json=dict(nombre="GE 1", bando="azul", clase="guerra_electronica", lat=0.3, lon=0.3))
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_api_interferir_valida_el_punto_y_la_zona_dura_mientras_se_mantiene_la_orden(api):
    prof, base, a, *_ = _preparar(api)
    ge_id = _ge_api(prof, base)
    alfa = api("alfa")
    orden = lambda uid, wps: alfa.post(f"{base}/ordenes", json={"unidad_id": uid, "tipo": "interferir", "waypoints": wps})  # noqa: E731
    r = orden(ge_id, [[1.5, 0.3]])
    assert r.status_code == 400 and "fuera del alcance" in r.json()["detail"]
    assert orden(ge_id, [[0.3, 0.5], [0.3, 0.6]]).status_code == 400
    r = orden(a["id"], [[0.0, 0.1]])
    assert r.status_code == 400 and "guerra electronica" in r.json()["detail"]
    r = orden(ge_id, [[0.3, 0.5]])
    assert r.status_code == 200 and r.json()["estado"] == "en_ejecucion"
    for nombre in ("alfa", "bravo", "obs"):  # tiempo real: rige desde que se emite
        zonas = api(nombre).get(base).json()["interferencias"]
        assert [(z["bando"], z["radio_km"]) for z in zonas] == [("azul", 25.0)], nombre
    assert prof.post(f"{base}/avanzar_turno?n=2").status_code == 200  # sigue mientras se mantenga la orden
    assert len(api("bravo").get(base).json()["interferencias"]) == 1
    assert alfa.delete(f"{base}/ordenes/{r.json()['id']}").status_code == 200  # el interferidor deja de emitir
    prof.post(f"{base}/avanzar_turno")
    assert api("bravo").get(base).json()["interferencias"] == []


def test_la_guerra_electronica_terrestre_la_conduce_ce(api):
    prof = api("prof")
    for nombre, puesto in (("uce", "ce"), ("ua3", "a3")):
        r = prof.post("/api/usuarios", json={"username": nombre, "password": "clave-segura-1", "rol": "azul", "puesto": puesto})
        assert r.status_code == 200
    prof, base, *_ = _preparar(api)
    orden = {"unidad_id": _ge_api(prof, base), "tipo": "interferir", "waypoints": [[0.3, 0.5]]}
    r = api("ua3").post(f"{base}/ordenes", json=orden)
    assert r.status_code == 403 and "Comunicaciones y Electronica (C-E)" in r.json()["detail"]
    assert api("uce").post(f"{base}/ordenes", json=orden).status_code == 200


def test_el_catalogo_publica_el_tope_de_drones(api):
    cat = api("alfa").get("/api/catalogo").json()
    assert cat["aeronaves"]["max_drones"] == catalogo.MAX_DRONES_BANDO
    assert {"uav_reco", "uav_armado", "merodeadora", "ge_aereo"} <= {m["id"] for m in cat["modelos"]}
