"""Ingenieros y obras, convoyes, emboscadas, fidelidad de plataformas y registro logistico."""

import json

import pytest

from app.engine import catalogo, movimiento
from app.engine.combat import resolver_combate
from app.models.aar import RegistroLogistico
from app.models.obra import Obra
from app.models.orden import Orden
from tests.conftest import TerrenoFalso
from tests.test_orders import _avanzar, _escenario, _orden, _unidad

# rio de ~1,1 km de ancho entre lat 0.10 y 0.11
RIO = TerrenoFalso(lambda lat, lon: "rio" if 0.10 <= lat <= 0.11 else "llano")


def _construir(db, esc, ing, tipo, sitio):
    o = Orden(escenario_id=esc.id, unidad_id=ing.id, tipo="construir", detalle=tipo,
              waypoints_json=json.dumps([sitio]), turno_emitida=esc.turno_actual)
    db.add(o)
    db.commit()
    return o


# ---------- catalogo ----------
def test_las_clases_nuevas_existen_y_tienen_sus_atributos():
    c = catalogo.CLASES
    assert c["ingenieros"].construye and c["ingenieros"].movilidad == "ligera"
    t = c["transporte"]
    assert t.nodo_movil_km == 3.0 and t.carga_max == 100 and t.vulnerable_emboscada and set(t.ataque_vs.values()) == {0.0}
    h = c["helicoptero_artillado"]
    assert h.tipo == "aerea" and h.penalizacion_movilidad == 0.15 and h.cadencia_fuego == 1.6
    a = c["antiaerea_portatil"]
    assert (a.despliegue_turnos, a.recarga_turnos, a.alcance_km) == (1, 1, 5)
    assert a.ataque_vs["terrestre"] == 0 and a.ataque_vs["aerea"] > 2
    assert {x.movilidad for x in c.values()} <= set(catalogo.MOVILIDADES)


# ---------- rios, vados y puentes ----------
def test_un_vehiculo_pesado_no_cruza_un_rio_sin_obra_pero_la_infanteria_lo_vadea():
    pesado = type("U", (), dict(tipo="terrestre", clase="blindado", lat=0.0, lon=0.0, velocidad_kmh=60,
                                autonomia_km=300, combustible=100))()
    ligero = type("U", (), dict(tipo="terrestre", clase="infanteria", lat=0.0, lon=0.0, velocidad_kmh=60,
                                autonomia_km=300, combustible=100))()
    m = movimiento.simular(pesado, [[1.0, 0.0]], RIO)
    assert m.lat < 0.10 and "rio sin puente ni vado" in m.nota
    m = movimiento.simular(ligero, [[1.0, 0.0]], RIO)
    assert m.lat > 0.11 and m.km_reales == pytest.approx(60 / 1.0, abs=6)  # el vadeo cuesta 1,1 km extra


def test_vado_y_puente_permiten_pasar_a_los_pesados_con_distinta_velocidad():
    def fin(tipo_obra):
        pesado = type("U", (), dict(tipo="terrestre", clase="blindado", lat=0.0, lon=0.0, velocidad_kmh=60,
                                    autonomia_km=300, combustible=100))()
        obra = Obra(tipo=tipo_obra, lat=0.105, lon=0.0, radio_km=1.5)
        return movimiento.simular(pesado, [[1.0, 0.0]], RIO, obras=[obra])

    vado, puente = fin("vado"), fin("puente")
    assert vado.lat > 0.11 and puente.lat > 0.11  # ambos cruzan
    assert puente.lat > vado.lat  # el puente frena menos que el vado
    assert "sin puente" not in vado.nota


def test_una_obra_fuera_del_paso_no_ayuda():
    pesado = type("U", (), dict(tipo="terrestre", clase="blindado", lat=0.0, lon=0.0, velocidad_kmh=60,
                                autonomia_km=300, combustible=100))()
    lejos = Obra(tipo="puente", lat=0.105, lon=1.0, radio_km=0.8)
    assert movimiento.simular(pesado, [[1.0, 0.0]], RIO, obras=[lejos]).lat < 0.10


def test_los_ingenieros_tienden_un_puente_que_luego_caduca(db_session):
    esc = _escenario(db_session)
    ing = _unidad(db_session, esc, clase="ingenieros", lat=0.098, alcance_km=5)
    o = _construir(db_session, esc, ing, "puente", [0.105, 0.0])
    _avanzar(db_session, esc, RIO)
    db_session.refresh(o)
    db_session.refresh(ing)
    assert o.estado == "resuelta" and "transitable hasta el turno 13" in o.resultado
    assert ing.municion == pytest.approx(40.0)  # el puente cuesta 60 % de material
    (obra,) = db_session.query(Obra).all()
    assert (obra.tipo, obra.bando, obra.creada_turno, obra.expira_turno) == ("puente", "azul", 1, 13)

    # en el turno siguiente ya lo usa un blindado, aun sin ingenieros cerca
    blin = _unidad(db_session, esc, clase="blindado", lat=0.0, velocidad_kmh=60, nombre="blin")
    _orden(db_session, esc, blin, "mover", waypoints=[[1.0, 0.0]])
    _avanzar(db_session, esc, RIO)
    db_session.refresh(blin)
    assert blin.lat > 0.11

    esc.turno_actual = 13  # ultimo turno de la obra: se usa y despues desaparece
    db_session.commit()
    _avanzar(db_session, esc, RIO)
    assert db_session.query(Obra).count() == 0


def test_el_vado_dura_menos_que_el_puente(db_session):
    esc = _escenario(db_session)
    ing = _unidad(db_session, esc, clase="ingenieros", lat=0.098)
    _construir(db_session, esc, ing, "vado", [0.105, 0.0])
    _avanzar(db_session, esc, RIO)
    (obra,) = db_session.query(Obra).all()
    assert obra.expira_turno == 5
    assert ing.municion == pytest.approx(70.0)


@pytest.mark.parametrize("caso,esperado", [
    ("no_ingeniero", "Solo los ingenieros"),
    ("lejos", "fuera del alcance de trabajo"),
    ("sin_rio", "no esta sobre un rio"),
    ("sin_material", "Material insuficiente"),
    ("tipo_malo", "puente o un vado"),
])
def test_construir_se_rechaza_si_no_se_cumplen_las_condiciones(db_session, caso, esperado):
    esc = _escenario(db_session)
    kw = dict(clase="ingenieros", lat=0.098)
    sitio, tipo = [0.105, 0.0], "puente"
    if caso == "no_ingeniero":
        kw["clase"] = "infanteria"
    if caso == "lejos":
        kw["lat"] = 0.0
        sitio = [0.105, 0.5]
    if caso == "sin_rio":
        sitio = [0.13, 0.0]  # al alcance (3,6 km) pero a mas de 1 km de cualquier rio
    if caso == "sin_material":
        kw["municion"] = 10
    if caso == "tipo_malo":
        tipo = "balsa"
    ing = _unidad(db_session, esc, **kw)
    o = _construir(db_session, esc, ing, tipo, sitio)
    _avanzar(db_session, esc, RIO)
    db_session.refresh(o)
    assert o.estado == "rechazada" and esperado in o.resultado
    assert db_session.query(Obra).count() == 0


def test_no_se_duplica_una_obra_en_el_mismo_punto(db_session):
    esc = _escenario(db_session)
    ing = _unidad(db_session, esc, clase="ingenieros", lat=0.098)
    ing2 = _unidad(db_session, esc, clase="ingenieros", lat=0.099, nombre="ing2")
    _construir(db_session, esc, ing, "vado", [0.105, 0.0])
    o2 = _construir(db_session, esc, ing2, "vado", [0.1052, 0.0])
    _avanzar(db_session, esc, RIO)
    db_session.refresh(o2)
    assert db_session.query(Obra).count() == 1 and o2.estado == "rechazada" and "Ya hay una obra" in o2.resultado


# ---------- convoyes ----------
def test_un_convoy_reabastece_en_marcha_y_gasta_su_carga(db_session):
    esc = _escenario(db_session)
    conv = _unidad(db_session, esc, clase="transporte", nombre="convoy", carga=100, alcance_km=0)
    cerca = _unidad(db_session, esc, nombre="cerca", lat=0.01, combustible=30, municion=30)   # 1,1 km
    lejos = _unidad(db_session, esc, nombre="lejos", lat=0.1, combustible=30, municion=30)    # 11 km
    _avanzar(db_session, esc)
    for u in (conv, cerca, lejos):
        db_session.refresh(u)
    assert (cerca.combustible, cerca.municion) == (70.0, 70.0)  # convoy: +40 %
    assert (lejos.combustible, lejos.municion) == (30.0, 30.0)
    assert conv.carga == pytest.approx(85.0)


def test_un_convoy_sin_carga_no_reabastece_y_se_rellena_en_un_deposito(db_session):
    esc = _escenario(db_session)
    conv = _unidad(db_session, esc, clase="transporte", nombre="convoy", carga=10, alcance_km=0)
    u = _unidad(db_session, esc, nombre="u", lat=0.01, combustible=30)
    _avanzar(db_session, esc)
    db_session.refresh(u)
    assert u.combustible == 30.0

    u.combustible = 100.0  # ya no necesita nada: el convoy no gasta carga en ella
    _unidad(db_session, esc, tipo="base", clase="deposito", velocidad_kmh=0, alcance_km=20, nombre="dep", lat=0.02)
    _avanzar(db_session, esc)
    db_session.refresh(conv)
    assert conv.carga == pytest.approx(60.0)  # +50 % en el deposito


def test_el_convoy_no_ataca_y_las_ordenes_de_ataque_se_rechazan(db_session):
    esc = _escenario(db_session)
    conv = _unidad(db_session, esc, clase="transporte", alcance_km=50)
    enemigo = _unidad(db_session, esc, bando="rojo", lat=0.01)
    o = _orden(db_session, esc, conv, "atacar", enemigo)
    _avanzar(db_session, esc)
    db_session.refresh(o)
    assert o.estado == "rechazada" and "no puede atacar" in o.resultado


# ---------- emboscada / sorpresa ----------
def test_sorpresa_solo_si_el_defensor_no_detecta_al_atacante():
    base = resolver_combate(100, "terrestre", 100, "terrestre")
    assert resolver_combate(100, "terrestre", 100, "terrestre", sorpresa=1.5).ratio == pytest.approx(base.ratio * 1.5)
    assert any("sorpresa" in e for e in resolver_combate(100, "terrestre", 100, "terrestre", sorpresa=1.2).efectos)


def _defensa(db_session, clase_def, det_def):
    esc = _escenario(db_session)
    a = _unidad(db_session, esc, alcance_km=50)
    d = _unidad(db_session, esc, bando="rojo", lat=0.09, clase=clase_def, deteccion_km=det_def)  # a 10 km
    _orden(db_session, esc, a, "atacar", d)
    _avanzar(db_session, esc)
    db_session.refresh(d)
    return d


def test_emboscada_a_un_convoy_es_mucho_mas_dura_que_un_ataque_detectado(db_session):
    detectado = _defensa(db_session, "transporte", 20)  # ve al atacante (10 km < 20 km)
    emboscado = _defensa(db_session, "transporte", 5)   # no lo ve
    infanteria_sorprendida = _defensa(db_session, "infanteria", 5)
    assert emboscado.fuerza < detectado.fuerza
    assert emboscado.fuerza < infanteria_sorprendida.fuerza  # el convoy sufre mas que otras unidades
    assert infanteria_sorprendida.fuerza < _defensa(db_session, "infanteria", 20).fuerza


def test_el_combate_informa_de_la_sorpresa(db_session):
    from app.models.aar import Combate

    _defensa(db_session, "transporte", 5)
    assert "sorpresa" in db_session.query(Combate).one().efectos


# ---------- helicoptero artillado ----------
def test_el_helicoptero_artillado_pierde_velocidad_por_peso(db_session):
    fin = {}
    for clase in ("helicoptero", "helicoptero_artillado"):
        esc = _escenario(db_session)
        h = _unidad(db_session, esc, tipo="aerea", clase=clase, velocidad_kmh=200, autonomia_km=450)
        _orden(db_session, esc, h, "mover", waypoints=[[5.0, 0.0]])
        _avanzar(db_session, esc)
        db_session.refresh(h)
        fin[clase] = h.lat
    assert fin["helicoptero_artillado"] == pytest.approx(fin["helicoptero"] * 0.85, rel=0.02)


def test_alta_cadencia_gasta_mas_municion_y_aporta_algo_de_potencia(db_session):
    consumo = {}
    for clase in ("helicoptero", "helicoptero_artillado"):
        esc = _escenario(db_session)
        h = _unidad(db_session, esc, tipo="aerea", clase=clase, alcance_km=50)
        d = _unidad(db_session, esc, bando="rojo", lat=0.02)
        _orden(db_session, esc, h, "atacar", d)
        _avanzar(db_session, esc)
        db_session.refresh(h)
        consumo[clase] = 100 - h.municion
    assert consumo["helicoptero"] == pytest.approx(34.0)
    assert consumo["helicoptero_artillado"] == pytest.approx(34.0 * 1.6)
    r = resolver_combate(100, "aerea", 100, "terrestre", cadencia=1.6)
    assert r.ratio == pytest.approx(resolver_combate(100, "aerea", 100, "terrestre").ratio * 1.6 ** 0.5)
    assert any("cadencia" in e for e in r.efectos)


# ---------- antiaerea portatil: despliegue, alcance y recarga ----------
def _aa_y_avion(db_session, **kw_aa):
    esc = _escenario(db_session)
    aa = _unidad(db_session, esc, clase="antiaerea_portatil", alcance_km=5, nombre="aa", **kw_aa)
    avion = _unidad(db_session, esc, bando="rojo", tipo="aerea", clase="caza", lat=0.02, nombre="avion")
    return esc, aa, avion


def test_la_antiaerea_portatil_solo_ataca_aeronaves(db_session):
    esc, aa, avion = _aa_y_avion(db_session)
    tierra = _unidad(db_session, esc, bando="rojo", lat=0.02, nombre="tierra")
    o = _orden(db_session, esc, aa, "atacar", tierra)
    _avanzar(db_session, esc)
    db_session.refresh(o)
    assert o.estado == "rechazada" and "no puede atacar" in o.resultado


def test_la_antiaerea_portatil_respeta_su_alcance_maximo(db_session):
    esc, aa, avion = _aa_y_avion(db_session)
    avion.lat = 0.06  # 6,7 km > 5 km
    db_session.commit()
    o = _orden(db_session, esc, aa, "atacar", avion)
    _avanzar(db_session, esc)
    db_session.refresh(o)
    assert o.estado == "rechazada" and "fuera de alcance" in o.resultado


def test_recarga_y_despliegue_de_la_antiaerea_portatil(db_session):
    esc, aa, avion = _aa_y_avion(db_session)

    # turno 1: dispara (50 % de municion) y queda recargando
    o1 = _orden(db_session, esc, aa, "atacar", avion)
    _avanzar(db_session, esc)
    db_session.refresh(o1)
    db_session.refresh(aa)
    assert o1.estado == "resuelta" and aa.municion == pytest.approx(50.0) and aa.recarga_restante == 1

    # turno 2: sigue recargando -> rechazado
    o2 = _orden(db_session, esc, aa, "atacar", avion)
    _avanzar(db_session, esc)
    db_session.refresh(o2)
    db_session.refresh(aa)
    assert o2.estado == "rechazada" and "Recargando" in o2.resultado and aa.recarga_restante == 0

    # turno 3: puede volver a disparar
    o3 = _orden(db_session, esc, aa, "atacar", avion)
    _avanzar(db_session, esc)
    db_session.refresh(o3)
    assert o3.estado == "resuelta"


def test_moverse_obliga_a_desplegar_de_nuevo_antes_de_disparar(db_session):
    esc, aa, avion = _aa_y_avion(db_session)
    _orden(db_session, esc, aa, "mover", waypoints=[[0.005, 0.0]])
    _avanzar(db_session, esc)
    db_session.refresh(aa)
    assert aa.despliegue_restante == 1

    o = _orden(db_session, esc, aa, "atacar", avion)  # turno 2: aun desplegando
    _avanzar(db_session, esc)
    db_session.refresh(o)
    assert o.estado == "rechazada" and "Desplegando" in o.resultado

    o = _orden(db_session, esc, aa, "atacar", avion)  # turno 3: ya desplegada
    _avanzar(db_session, esc)
    db_session.refresh(o)
    assert o.estado == "resuelta"


def test_mover_y_disparar_en_el_mismo_turno_no_esta_permitido_para_sistemas_que_se_despliegan(db_session):
    esc, aa, avion = _aa_y_avion(db_session)
    _orden(db_session, esc, aa, "mover", waypoints=[[0.005, 0.0]])
    # una unidad solo tiene una orden por turno en la API; aqui se fuerzan las dos para probar el motor
    o = _orden(db_session, esc, aa, "atacar", avion)
    _avanzar(db_session, esc)
    db_session.refresh(o)
    assert o.estado == "rechazada" and "Desplegando" in o.resultado


# ---------- registro logistico ----------
def test_el_registro_logistico_guarda_cada_cambio_con_su_causa(db_session):
    esc = _escenario(db_session)
    a = _unidad(db_session, esc, alcance_km=50, velocidad_kmh=30)
    d = _unidad(db_session, esc, bando="rojo", lat=0.01)
    _unidad(db_session, esc, tipo="base", clase="deposito", velocidad_kmh=0, alcance_km=30, nombre="dep", lat=0.02)
    o_mov = _orden(db_session, esc, a, "mover", waypoints=[[0.05, 0.0]])
    _avanzar(db_session, esc)
    filas = db_session.query(RegistroLogistico).filter_by(unidad_id=a.id).order_by(RegistroLogistico.id).all()
    por_causa = {(f.variable, f.causa): f for f in filas}
    assert ("combustible", "movimiento") in por_causa and por_causa[("combustible", "movimiento")].orden_id == o_mov.id
    assert por_causa[("combustible", "movimiento")].despues < por_causa[("combustible", "movimiento")].antes
    assert ("combustible", "reabastecimiento") in por_causa  # el deposito la recarga al final del turno
    assert all(f.turno == 1 and f.bando == "azul" and f.unidad_nombre == a.nombre for f in filas)

    o_atk = _orden(db_session, esc, a, "atacar", d)
    _avanzar(db_session, esc)
    combate = db_session.query(RegistroLogistico).filter_by(unidad_id=a.id, causa="combate").one()
    assert (combate.variable, combate.turno, combate.orden_id) == ("municion", 2, o_atk.id)
    assert combate.antes - combate.despues == pytest.approx(25.0)


def test_no_se_registran_cambios_nulos(db_session):
    esc = _escenario(db_session)
    _unidad(db_session, esc)
    _avanzar(db_session, esc)
    assert db_session.query(RegistroLogistico).count() == 0
