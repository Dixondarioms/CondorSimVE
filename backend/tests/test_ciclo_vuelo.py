"""Ciclo de vuelo: aterrizar en una base propia, esperar el reabastecimiento, despegar, patrullar, interceptar,
regresar por combustible critico y sufrir en tierra los ataques a la base."""

import json

import pytest

from app.engine import aeronaves, orders
from app.models.aar import Combate, RegistroLogistico
from app.models.evento import Evento
from app.models.orden import Orden
from app.models.unidad import Unidad
from tests.test_aeronaves import _base_aerea
from tests.test_api import _preparar
from tests.test_orders import _avanzar, _escenario, _unidad

CAZA = dict(tipo="aerea", clase="caza", velocidad_kmh=900, alcance_km=80, deteccion_km=60, autonomia_km=1800)


def _caza(db, esc, **kw):
    return _unidad(db, esc, **{**CAZA, **kw})


def _base(db, esc, **kw):
    return _unidad(db, esc, **{**dict(nombre="BA", tipo="base", clase="base_aerea", velocidad_kmh=0, alcance_km=25), **kw})


def _orden(db, esc, unidad, tipo, objetivo=None, waypoints=None, detalle=""):
    o = Orden(escenario_id=esc.id, unidad_id=unidad.id, tipo=tipo, objetivo_unidad_id=objetivo.id if objetivo else None,
              waypoints_json=json.dumps(waypoints or []), detalle=detalle, turno_emitida=esc.turno_actual)
    db.add(o)
    db.commit()
    return o


def _refrescar(db, *objs):
    for o in objs:
        db.refresh(o)


# ---------- aterrizaje ----------
def test_una_aeronave_aterriza_en_su_base_y_empieza_a_reabastecerse(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    caza = _caza(db_session, esc, lat=0.2, combustible=40, municion=30)
    o = _orden(db_session, esc, caza, "aterrizar", objetivo=base)
    _avanzar(db_session, esc)
    _refrescar(db_session, caza, o)
    assert o.estado == "resuelta" and "Aterrizo en BA" in o.resultado
    assert caza.en_tierra and caza.base_id == base.id
    assert caza.espera_restante == aeronaves.TIEMPO_REARME_TURNOS - 1  # ya paso el primer turno en tierra
    assert (caza.lat, caza.lon) != (base.lat, base.lon)  # estacionada junto a la base, no encima
    assert caza.combustible > 40 and caza.municion == 80  # +50 de municion; combustible: -vuelo +50
    assert aeronaves.estacionadas(base, [caza, base]) == [caza]


def test_si_no_llega_este_turno_sigue_volando_hacia_la_base(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    caza = _caza(db_session, esc, lat=3.0, velocidad_kmh=100)  # 333 km
    o = _orden(db_session, esc, caza, "aterrizar", objetivo=base)
    _avanzar(db_session, esc)
    _refrescar(db_session, caza, o)
    assert not caza.en_tierra and o.estado == "resuelta" and "Vuela hacia BA" in o.resultado
    assert caza.lat == pytest.approx(3.0 - 100 / 111.19, abs=0.02)


@pytest.mark.parametrize("caso", ["ajena", "no_es_base_aerea", "danada", "llena", "terrestre"])
def test_aterrizajes_imposibles_se_rechazan(db_session, caso):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0, bando="rojo" if caso == "ajena" else "azul",
                 clase="deposito" if caso == "no_es_base_aerea" else "base_aerea",
                 fuerza=10.0 if caso == "danada" else 100.0)
    if caso == "llena":
        for i in range(3):
            _caza(db_session, esc, nombre=f"E{i}", lat=0.0, aeronaves=4, en_tierra=True, base_id=base.id)
    u = _unidad(db_session, esc, nombre="T", lat=0.05) if caso == "terrestre" else _caza(db_session, esc, lat=0.05)
    o = _orden(db_session, esc, u, "aterrizar", objetivo=base)
    _avanzar(db_session, esc)
    _refrescar(db_session, u, o)
    assert o.estado == "rechazada" and not u.en_tierra, o.resultado


# ---------- espera, despegue y ciclo completo ----------
def test_no_se_puede_despegar_hasta_terminar_el_reabastecimiento(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    caza = _caza(db_session, esc, lat=0.0, en_tierra=True, base_id=base.id, espera_restante=1, combustible=50)
    o = _orden(db_session, esc, caza, "mover", waypoints=[[1.0, 0.0]])
    _avanzar(db_session, esc)
    _refrescar(db_session, caza, o)
    assert o.estado == "rechazada" and "faltan 1 turno" in o.resultado and caza.en_tierra
    assert caza.espera_restante == 0  # el turno cuenta para la espera

    o2 = _orden(db_session, esc, caza, "mover", waypoints=[[1.0, 0.0]])
    _avanzar(db_session, esc)
    _refrescar(db_session, caza, o2)
    assert o2.estado == "resuelta" and not caza.en_tierra and caza.base_id is None and caza.lat > 0.5


def test_ciclo_completo_aterrizar_esperar_reabastecer_y_despegar(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    caza = _caza(db_session, esc, lat=0.1, combustible=30, municion=20)
    _orden(db_session, esc, caza, "aterrizar", objetivo=base)
    _avanzar(db_session, esc)  # turno 1: aterriza
    _refrescar(db_session, caza)
    assert caza.en_tierra and caza.espera_restante == 1

    _orden(db_session, esc, caza, "mover", waypoints=[[2.0, 0.0]])
    _avanzar(db_session, esc)  # turno 2: aun no puede
    _refrescar(db_session, caza)
    assert caza.en_tierra and caza.espera_restante == 0
    assert (caza.combustible, caza.municion) == (100.0, 100.0)  # +50 por turno en tierra

    o = _orden(db_session, esc, caza, "mover", waypoints=[[2.0, 0.0]])
    _avanzar(db_session, esc)  # turno 3: despega con todo lleno
    _refrescar(db_session, caza, o)
    assert o.estado == "resuelta" and not caza.en_tierra and caza.lat > 0.5 and caza.municion == 100


def test_un_avion_en_vuelo_junto_a_la_base_ya_no_se_reabastece(db_session):
    esc = _escenario(db_session)
    _base(db_session, esc, lat=0.0)
    caza = _caza(db_session, esc, lat=0.05, combustible=30, municion=30)
    _avanzar(db_session, esc)
    _refrescar(db_session, caza)
    assert (caza.combustible, caza.municion) == (30.0, 30.0) and not caza.en_tierra


def test_sin_combustible_junto_a_la_base_hay_aterrizaje_de_emergencia(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    caza = _caza(db_session, esc, lat=0.05, combustible=0.0)
    _avanzar(db_session, esc)
    _refrescar(db_session, caza)
    assert caza.estado == "activa" and caza.en_tierra and caza.base_id == base.id and caza.combustible == 50.0
    assert db_session.query(Evento).filter(Evento.descripcion.like("%aterrizo de emergencia%")).count() == 1


def test_sin_combustible_y_sin_base_cerca_se_pierde(db_session):
    esc = _escenario(db_session)
    _base(db_session, esc, lat=5.0)
    caza = _caza(db_session, esc, lat=0.0, combustible=0.0)
    _avanzar(db_session, esc)
    _refrescar(db_session, caza)
    assert caza.estado == "destruida" and not caza.en_tierra


# ---------- efectos de estar en tierra ----------
def test_los_aviones_estacionados_no_dan_cobertura_aerea_y_cuentan_como_blancos_terrestres():
    volando = Unidad(bando="azul", tipo="aerea", estado="activa", en_tierra=False, lat=0.0, lon=0.0)
    parado = Unidad(bando="azul", tipo="aerea", estado="activa", en_tierra=True, lat=0.0, lon=0.0)
    assert orders._tiene_cobertura_aerea("azul", 0.0, 0.0, [volando]) is True
    assert orders._tiene_cobertura_aerea("azul", 0.0, 0.0, [parado]) is False
    assert orders.tipo_efectivo(parado) == "terrestre" and orders.tipo_efectivo(volando) == "aerea"


def test_atacar_la_base_danha_a_los_aviones_estacionados(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    parado = _caza(db_session, esc, lat=0.006, en_tierra=True, base_id=base.id, espera_restante=1, nombre="Parado")
    volando = _caza(db_session, esc, lat=0.05, nombre="Volando")
    art = _unidad(db_session, esc, nombre="Art", bando="rojo", clase="artilleria", lat=0.1, alcance_km=30, fuerza=100)
    _orden(db_session, esc, art, "atacar", objetivo=base)
    _avanzar(db_session, esc)
    _refrescar(db_session, base, parado, volando)
    perdida_base = 100 - base.fuerza
    assert perdida_base > 5
    assert 100 - parado.fuerza == pytest.approx(perdida_base * aeronaves.PERDIDA_EN_TIERRA, abs=0.01)
    assert volando.fuerza == 100  # los que estan en el aire no se ven afectados


def test_un_avion_estacionado_puede_ser_atacado_como_blanco_terrestre(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    parado = _caza(db_session, esc, lat=0.006, en_tierra=True, base_id=base.id, nombre="Parado", deteccion_km=1)
    art = _unidad(db_session, esc, nombre="Art", bando="rojo", clase="artilleria", lat=0.1, alcance_km=30, fuerza=100)
    o = _orden(db_session, esc, art, "atacar", objetivo=parado)
    _avanzar(db_session, esc)
    _refrescar(db_session, parado, o)
    assert o.estado == "resuelta" and parado.fuerza < 100  # la artilleria no puede atacar aviones en vuelo


# ---------- patrulla e interceptacion ----------
def test_patrullar_lleva_a_la_zona_y_se_mantiene_gastando_combustible(db_session):
    esc = _escenario(db_session)
    caza = _caza(db_session, esc, lat=0.0, combustible=90)
    o = _orden(db_session, esc, caza, "patrullar", waypoints=[[0.5, 0.0]])
    _avanzar(db_session, esc)
    _refrescar(db_session, caza, o)
    assert o.estado == "resuelta" and "Patrulla sobre" in o.resultado
    assert caza.mision == "patrulla" and (caza.mision_lat, caza.mision_lon) == (0.5, 0.0)
    assert caza.lat == pytest.approx(0.5, abs=0.01)
    combustible = caza.combustible
    _avanzar(db_session, esc)  # sin ordenes: sigue en la zona
    _refrescar(db_session, caza)
    assert caza.mision == "patrulla" and caza.lat == pytest.approx(0.5, abs=0.01)
    assert caza.combustible == pytest.approx(combustible - aeronaves.COMBUSTIBLE_LOITER)
    causa = db_session.query(RegistroLogistico).filter_by(unidad_id=caza.id, causa="patrulla").count()
    assert causa == 1


def test_una_patrulla_lejana_sigue_sola_hacia_su_zona(db_session):
    esc = _escenario(db_session)
    caza = _caza(db_session, esc, lat=0.0, velocidad_kmh=100)
    _orden(db_session, esc, caza, "patrullar", waypoints=[[2.0, 0.0]])
    _avanzar(db_session, esc)
    _refrescar(db_session, caza)
    primero = caza.lat
    _avanzar(db_session, esc)
    _refrescar(db_session, caza)
    assert caza.lat == pytest.approx(primero + 100 / 111.19, abs=0.02) and caza.mision == "patrulla"


def test_otra_orden_de_movimiento_cancela_la_patrulla(db_session):
    esc = _escenario(db_session)
    caza = _caza(db_session, esc, lat=0.0)
    _orden(db_session, esc, caza, "patrullar", waypoints=[[0.3, 0.0]])
    _avanzar(db_session, esc)
    _orden(db_session, esc, caza, "mover", waypoints=[[0.6, 0.0]])
    _avanzar(db_session, esc)
    _refrescar(db_session, caza)
    assert caza.mision == "" and caza.mision_lat is None


def test_la_patrulla_intercepta_al_avion_enemigo_detectado_al_alcance(db_session):
    esc = _escenario(db_session)
    patrulla = _caza(db_session, esc, nombre="CAP", lat=0.0, mision="patrulla", mision_lat=0.0, mision_lon=0.0)
    enemigo = _caza(db_session, esc, nombre="Enemigo", bando="rojo", lat=0.3)  # 33 km: dentro del alcance de 80
    lejano = _caza(db_session, esc, nombre="Lejano", bando="rojo", lat=3.0)
    _avanzar(db_session, esc)
    _refrescar(db_session, patrulla, enemigo, lejano)
    (orden,) = db_session.query(Orden).filter(Orden.detalle == "intercepcion").all()
    assert orden.unidad_id == patrulla.id and orden.objetivo_unidad_id == enemigo.id and orden.estado == "resuelta"
    assert db_session.query(Combate).filter_by(orden_id=orden.id).count() == 1
    assert enemigo.fuerza < 100 and lejano.fuerza == 100
    assert patrulla.mision == "patrulla"  # sigue en la zona


@pytest.mark.parametrize("caso", ["sin_municion", "con_orden_propia", "objetivo_terrestre", "objetivo_estacionado", "sin_patrulla"])
def test_no_hay_interceptacion_en_estos_casos(db_session, caso):
    esc = _escenario(db_session)
    patrulla = _caza(db_session, esc, nombre="CAP", lat=0.0, mision="" if caso == "sin_patrulla" else "patrulla",
                     mision_lat=0.0, mision_lon=0.0, municion=0 if caso == "sin_municion" else 100)
    if caso == "objetivo_terrestre":
        _unidad(db_session, esc, nombre="Tierra", bando="rojo", lat=0.1)
    elif caso == "objetivo_estacionado":
        base = _base(db_session, esc, bando="rojo", lat=0.3)
        _caza(db_session, esc, nombre="Parado", bando="rojo", lat=0.3, en_tierra=True, base_id=base.id)
    else:
        enemigo = _caza(db_session, esc, nombre="Enemigo", bando="rojo", lat=0.3)
        if caso == "con_orden_propia":
            _orden(db_session, esc, patrulla, "atacar", objetivo=enemigo)
    _avanzar(db_session, esc)
    assert db_session.query(Orden).filter(Orden.detalle == "intercepcion").count() == 0


def test_combustible_critico_saca_de_la_patrulla_y_ordena_regresar(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    caza = _caza(db_session, esc, lat=0.3, combustible=30, mision="patrulla", mision_lat=0.3, mision_lon=0.0)
    _avanzar(db_session, esc)  # 30 - 8 = 22 <= 25
    _refrescar(db_session, caza)
    assert caza.mision == "" and caza.combustible == pytest.approx(22.0)
    (orden,) = db_session.query(Orden).filter(Orden.detalle == "combustible critico").all()
    assert (orden.tipo, orden.unidad_id, orden.objetivo_unidad_id, orden.estado, orden.turno_emitida) == (
        "aterrizar", caza.id, base.id, "pendiente", esc.turno_actual)
    assert db_session.query(Evento).filter(Evento.descripcion.like("%combustible critico%")).count() == 1
    _avanzar(db_session, esc)  # el regreso automatico se resuelve el turno siguiente
    _refrescar(db_session, caza, orden)
    assert orden.estado == "resuelta" and caza.en_tierra and caza.base_id == base.id


def test_combustible_critico_sin_base_disponible_solo_avisa(db_session):
    esc = _escenario(db_session)
    caza = _caza(db_session, esc, lat=0.3, combustible=30, mision="patrulla", mision_lat=0.3, mision_lon=0.0)
    _avanzar(db_session, esc)
    _refrescar(db_session, caza)
    assert caza.mision == "" and db_session.query(Orden).filter(Orden.detalle == "combustible critico").count() == 0
    assert db_session.query(Evento).filter(Evento.descripcion.like("%no hay base disponible%")).count() == 1


# ---------- API ----------
def _api_base_y_caza(api, en_tierra=False, espera=0):
    prof, base, a, r1, r2 = _preparar(api)
    ba = _base_aerea(prof, base, lat=0.0, lon=0.3)
    caza = prof.post(f"{base}/unidades", json=dict(nombre="C", bando="azul", modelo="f16", aeronaves=2, lat=0.05, lon=0.3)).json()
    if en_tierra:
        with api.engine.begin() as con:
            from sqlalchemy import text
            con.execute(text("UPDATE unidades SET en_tierra=:t, base_id=:b, espera_restante=:e WHERE id=:i"),
                        dict(t=True, b=ba["id"], e=espera, i=caza["id"]))
    return prof, base, ba, caza


def test_la_api_valida_aterrizar_y_patrullar(api):
    prof, base, ba, caza = _api_base_y_caza(api)
    azul = api("alfa")
    ok = azul.post(f"{base}/ordenes", json={"unidad_id": caza["id"], "tipo": "aterrizar", "objetivo_unidad_id": ba["id"]})
    assert ok.status_code == 200, ok.text
    assert ok.json()["objetivo_unidad_id"] == ba["id"]
    # una base ajena o inexistente no se revela
    rojo_base = _base_aerea(prof, base, nombre="BR", bando="rojo", lat=0.5)
    r = azul.post(f"{base}/ordenes", json={"unidad_id": caza["id"], "tipo": "aterrizar", "objetivo_unidad_id": rojo_base["id"]})
    assert r.status_code == 404
    assert azul.post(f"{base}/ordenes", json={"unidad_id": caza["id"], "tipo": "aterrizar"}).status_code == 404
    # una unidad terrestre no puede aterrizar ni patrullar
    a = [u for u in prof.get(base).json()["unidades"] if u["nombre"] == "A"][0]
    assert "aeronaves" in azul.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "patrullar", "waypoints": [[0.1, 0.1]]}).json()["detail"]
    # patrulla: un solo punto
    assert azul.post(f"{base}/ordenes", json={"unidad_id": caza["id"], "tipo": "patrullar", "waypoints": [[0.1, 0.1], [0.2, 0.2]]}).status_code == 400
    assert azul.post(f"{base}/ordenes", json={"unidad_id": caza["id"], "tipo": "patrullar", "waypoints": [[0.1, 0.1]]}).status_code == 200
    prof.patch(f"{base}/unidades/{caza['id']}", json={"combustible": 20})
    assert "Combustible insuficiente" in azul.post(f"{base}/ordenes", json={"unidad_id": caza["id"], "tipo": "patrullar", "waypoints": [[0.1, 0.1]]}).json()["detail"]


def test_la_api_no_deja_despegar_ni_apoyar_en_tierra(api):
    prof, base, ba, caza = _api_base_y_caza(api, en_tierra=True, espera=1)
    azul = api("alfa")
    r = azul.post(f"{base}/ordenes", json={"unidad_id": caza["id"], "tipo": "mover", "waypoints": [[0.5, 0.3]]})
    assert r.status_code == 400 and "faltan 1 turno" in r.json()["detail"]
    assert azul.post(f"{base}/ordenes", json={"unidad_id": caza["id"], "tipo": "patrullar", "waypoints": [[0.5, 0.3]]}).status_code == 400
    assert "en tierra" in azul.post(f"{base}/ordenes", json={"unidad_id": caza["id"], "tipo": "apoyar", "objetivo_unidad_id": 1}).json()["detail"].lower()
    assert azul.post(f"{base}/ordenes", json={"unidad_id": caza["id"], "tipo": "aterrizar", "objetivo_unidad_id": ba["id"]}).json()["detail"] == "La aeronave ya esta en tierra."


def test_lista_para_despegar_acepta_ordenes_de_vuelo(api):
    prof, base, ba, caza = _api_base_y_caza(api, en_tierra=True, espera=0)
    r = api("alfa").post(f"{base}/ordenes", json={"unidad_id": caza["id"], "tipo": "mover", "waypoints": [[0.5, 0.3]]})
    assert r.status_code == 200, r.text


def test_el_enemigo_no_ve_la_mision_ni_la_espera_de_una_aeronave(api):
    prof, base, a, r1, r2 = _preparar(api)
    prof.post(f"{base}/unidades", json=dict(nombre="CAP rojo", bando="rojo", modelo="f16", aeronaves=2, lat=0.02, lon=0.0))
    with api.engine.begin() as con:
        from sqlalchemy import text
        con.execute(text("UPDATE unidades SET mision='patrulla', mision_lat=0.5, mision_lon=0.5, espera_restante=1, "
                         "en_tierra=:t WHERE nombre='CAP rojo'"), dict(t=False))
    visto = {u["nombre"]: u for u in api("alfa").get(base).json()["unidades"]}["CAP rojo"]
    assert visto["mision"] is None and visto["mision_lat"] is None and visto["espera_restante"] is None and visto["base_id"] is None
    propio = {u["nombre"]: u for u in api("bravo").get(base).json()["unidades"]}["CAP rojo"]
    assert propio["mision"] == "patrulla" and propio["mision_lat"] == 0.5
    assert {u["nombre"]: u for u in prof.get(base).json()["unidades"]}["CAP rojo"]["mision"] == "patrulla"
