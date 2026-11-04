"""Adversario automatico: conduce un bando con las mismas reglas que un alumno y solo con lo que ese bando sabe."""

from app import adversario
from app.models.objetivo import Objetivo
from app.models.orden import Orden
from app.models.unidad import Unidad
from tests.conftest import TerrenoFalso
from tests.test_api import _preparar
from tests.test_orders import _avanzar, _escenario, _unidad


def _ordenes(db, esc, bando=None):
    """Ordenes que las unidades estan cumpliendo (tiempo real: se aplican al emitirse)."""
    q = db.query(Orden).filter(Orden.escenario_id == esc.id, Orden.estado.in_(("pendiente", "en_ejecucion"))).all()
    return {o.unidad_id: o for o in q if bando is None or db.get(Unidad, o.unidad_id).bando == bando}


def _jugar(db, esc, **kw):
    r = adversario.jugar_turno(db, esc, TerrenoFalso(), **kw)
    db.commit()
    return r


def test_solo_juega_el_bando_que_conduce(db_session):
    esc = _escenario(db_session)
    esc.ia_rojo = True
    db_session.commit()
    azul = _unidad(db_session, esc, nombre="A", bando="azul", lat=0.0, lon=0.0, alcance_km=10, deteccion_km=15)
    rojo = _unidad(db_session, esc, nombre="R", bando="rojo", lat=0.05, lon=0.0, alcance_km=10, deteccion_km=15)
    _jugar(db_session, esc)
    ordenes = _ordenes(db_session, esc)
    assert rojo.id in ordenes and azul.id not in ordenes
    assert ordenes[rojo.id].tipo == "atacar" and ordenes[rojo.id].objetivo_unidad_id == azul.id
    assert ordenes[rojo.id].estado == "en_ejecucion" and rojo.orden_id == ordenes[rojo.id].id


def test_no_ataca_lo_que_su_bando_no_ve(db_session):
    esc = _escenario(db_session)
    esc.ia_rojo = True
    db_session.commit()
    _unidad(db_session, esc, nombre="A", bando="azul", lat=0.0, lon=0.0, alcance_km=10, deteccion_km=5)
    rojo = _unidad(db_session, esc, nombre="R", bando="rojo", lat=0.08, lon=0.0, alcance_km=50, deteccion_km=5)  # 9 km
    _jugar(db_session, esc)
    assert rojo.id not in _ordenes(db_session, esc)  # A esta a su alcance de fuego, pero fuera de su deteccion


def test_va_a_ocupar_su_objetivo(db_session):
    esc = _escenario(db_session)
    esc.ia_azul = True
    db_session.commit()
    u = _unidad(db_session, esc, nombre="A", bando="azul", lat=0.0, lon=0.0)
    db_session.add(Objetivo(escenario_id=esc.id, bando="azul", tipo="ocupar", nombre="Cerro", puntos=10,
                            lat=0.5, lon=0.0, radio_km=3, turnos_requeridos=1))
    db_session.commit()
    _jugar(db_session, esc)
    o = _ordenes(db_session, esc)[u.id]
    assert o.tipo == "mover" and o.waypoints[-1] == [0.5, 0.0]


def test_la_aeronave_con_poco_combustible_vuelve_a_su_base(db_session):
    esc = _escenario(db_session)
    esc.ia_azul = True
    db_session.commit()
    base = _unidad(db_session, esc, nombre="Base", bando="azul", tipo="base", clase="base_aerea", lat=0.0, lon=0.0,
                   velocidad_kmh=0, alcance_km=25)
    caza = _unidad(db_session, esc, nombre="Caza", bando="azul", tipo="aerea", clase="caza", lat=0.5, lon=0.0,
                   velocidad_kmh=900, alcance_km=80, autonomia_km=1800, combustible=30)
    _jugar(db_session, esc)
    o = _ordenes(db_session, esc)[caza.id]
    assert o.tipo == "aterrizar" and o.objetivo_unidad_id == base.id


def test_el_avion_sin_armas_se_aleja_de_la_antiaerea_enemiga(db_session):
    esc = _escenario(db_session)
    esc.ia_rojo = True
    db_session.commit()
    _unidad(db_session, esc, nombre="AA", bando="azul", clase="antiaerea", lat=0.0, lon=0.0, alcance_km=20, deteccion_km=20)
    # a 6,7 km: su radar ve lo que esta en tierra solo de cerca
    awacs = _unidad(db_session, esc, nombre="AWACS", bando="rojo", tipo="aerea", clase="alerta_temprana", lat=0.06,
                    lon=0.0, velocidad_kmh=600, alcance_km=0, deteccion_km=300, autonomia_km=4000)
    _jugar(db_session, esc)
    o = _ordenes(db_session, esc)[awacs.id]
    assert o.tipo == "mover" and o.waypoints[-1][0] > 0.3  # se va al norte, a mas del doble del alcance de la AA


def test_con_el_reloj_en_marcha_piensa_cada_cinco_minutos_sin_repetir_ordenes(db_session):
    from app.engine import tiempo_real

    tiempo_real.MUNDOS.clear()
    esc = _escenario(db_session)
    esc.ia_rojo = True
    db_session.commit()
    azul = _unidad(db_session, esc, nombre="A", bando="azul", lat=0.0, lon=0.0, alcance_km=10, deteccion_km=15)
    rojo = _unidad(db_session, esc, nombre="R", bando="rojo", lat=0.05, lon=0.0, alcance_km=10, deteccion_km=15)
    tiempo_real.paso(db_session, esc, 60, TerrenoFalso())  # piensa en el primer paso: ataca y ya combate
    db_session.commit()
    o = _ordenes(db_session, esc)[rojo.id]
    assert o.tipo == "atacar" and azul.fuerza < 100
    tiempo_real.paso(db_session, esc, 600, TerrenoFalso())  # vuelve a pensar dos veces: sigue con la misma orden
    db_session.commit()
    assert _ordenes(db_session, esc)[rojo.id].id == o.id
    assert db_session.query(Orden).filter(Orden.unidad_id == rojo.id).count() == 1
    # el blanco se aleja y sale de su vista: la IA cambia de orden en la decision siguiente
    azul.lat = 2.0
    db_session.commit()
    tiempo_real.paso(db_session, esc, 900, TerrenoFalso())
    db_session.commit()
    db_session.refresh(o)
    assert o.estado != "en_ejecucion"
    tiempo_real.MUNDOS.clear()


def test_el_instructor_la_enciende_desde_la_consola_y_juega_el_turno_en_curso(api):
    prof, base, a, r1, r2 = _preparar(api)
    r = prof.patch(f"{base}/config", json={"ia_rojo": True})
    assert r.status_code == 200, r.text
    esc = r.json()["escenario"]
    assert esc["ia_rojo"] is True
    datos = prof.get(base).json()
    assert any(o["unidad_id"] == r1["id"] and o["tipo"] == "atacar" for o in datos["ordenes"])
    assert any("adversario automatico del bando Rojo activado" in ev["descripcion"] for ev in datos["eventos"])
    r = prof.patch(f"{base}/config", json={"ia_rojo": False})
    assert r.json()["escenario"]["ia_rojo"] is False


def test_las_plantillas_contra_la_ia_crean_el_escenario_con_el_rojo_ya_jugando(db_session):
    from app.engine import plantillas
    for pid in ("defensa_aerea_central", "interdiccion_llanos", "defensa_costa_oriental"):
        assert plantillas.PLANTILLAS[pid].ia_rojo
        esc = plantillas.crear_desde_plantilla(db_session, pid)
        assert esc.ia_rojo and not esc.ia_azul
        assert _ordenes(db_session, esc, "rojo"), pid  # el rojo ya dio ordenes en el primer turno


def test_la_ia_conoce_la_ubicacion_de_las_bases_enemigas_y_va_a_su_objetivo(db_session):
    esc = _escenario(db_session)
    esc.ia_rojo = True
    db_session.commit()
    base = _unidad(db_session, esc, nombre="Base azul", bando="azul", tipo="base", clase="base_aerea", lat=0.0, lon=0.0,
                   velocidad_kmh=0, alcance_km=25)
    _unidad(db_session, esc, nombre="Base roja", bando="rojo", tipo="base", clase="base_aerea", lat=3.0, lon=0.0,
            velocidad_kmh=0, alcance_km=25)
    caza = _unidad(db_session, esc, nombre="Caza rojo", bando="rojo", tipo="aerea", clase="ataque", lat=2.0, lon=0.0,
                   velocidad_kmh=700, alcance_km=100, deteccion_km=30, autonomia_km=2000)
    db_session.add(Objetivo(escenario_id=esc.id, bando="rojo", tipo="destruir", nombre="Base", puntos=10, unidad_id=base.id))
    db_session.commit()
    _jugar(db_session, esc)
    o = _ordenes(db_session, esc)[caza.id]
    assert o.tipo == "mover" and o.waypoints[-1][0] < 1.0  # se acerca a la base azul (a distancia de deteccion)


def test_guardar_como_plantilla_conserva_el_adversario(db_session, tmp_path, monkeypatch):
    from app.engine import plantillas
    monkeypatch.setattr(plantillas, "RUTA_PLANTILLAS_USUARIO", tmp_path)
    esc = plantillas.crear_desde_plantilla(db_session, "interdiccion_llanos")
    p = plantillas.guardar_desde_escenario(db_session, esc, "Llanos con IA")
    assert p.ia_rojo and not p.ia_azul


def _balistico(db, esc, **kw):
    datos = dict(nombre="Lanzador rojo", bando="rojo", tipo="terrestre", clase="lanzador_balistico", lat=0.0, lon=0.0,
                 velocidad_kmh=40, alcance_km=500, deteccion_km=10, municion=100.0)
    datos.update(kw)
    return _unidad(db, esc, **datos)


def test_el_lanzador_balistico_tira_primero_a_la_instalacion_fija_que_ve(db_session):
    esc = _escenario(db_session)
    esc.ia_rojo = True
    db_session.commit()
    lanzador = _balistico(db_session, esc)
    _unidad(db_session, esc, nombre="Observador", bando="rojo", clase="reconocimiento", lat=1.95, lon=0.0, deteccion_km=20)
    base = _unidad(db_session, esc, nombre="Base azul", bando="azul", tipo="base", clase="base_aerea", lat=2.0, lon=0.0,
                   velocidad_kmh=0)
    _unidad(db_session, esc, nombre="Infantería azul", bando="azul", clase="infanteria", lat=1.97, lon=0.0)
    _jugar(db_session, esc)
    o = db_session.query(Orden).filter(Orden.unidad_id == lanzador.id, Orden.tipo == "lanzar").one()
    assert o.objetivo_unidad_id == base.id and o.estado == "resuelta"
    misiles = db_session.query(Unidad).filter(Unidad.escenario_id == esc.id, Unidad.clase == "misil_balistico").all()
    assert len(misiles) == 2 and all(m.bando == "rojo" for m in misiles)
    _jugar(db_session, esc)  # recargando: no vuelve a tirar enseguida
    assert db_session.query(Orden).filter(Orden.unidad_id == lanzador.id, Orden.tipo == "lanzar").count() == 1


def test_el_lanzador_balistico_no_tira_a_lo_que_no_ve_ni_fuera_de_alcance(db_session):
    esc = _escenario(db_session)
    esc.ia_rojo = True
    db_session.commit()
    lanzador = _balistico(db_session, esc)
    _unidad(db_session, esc, nombre="Base oculta", bando="azul", tipo="base", clase="base_aerea", lat=2.0, lon=0.0, velocidad_kmh=0)
    _unidad(db_session, esc, nombre="Observador", bando="rojo", clase="reconocimiento", lat=5.95, lon=0.0, deteccion_km=20)
    _unidad(db_session, esc, nombre="Base lejana", bando="azul", tipo="base", clase="base_aerea", lat=6.0, lon=0.0, velocidad_kmh=0)
    _jugar(db_session, esc)
    assert db_session.query(Orden).filter(Orden.unidad_id == lanzador.id).count() == 0
