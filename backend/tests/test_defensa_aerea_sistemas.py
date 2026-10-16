"""Sistemas de defensa aerea con sus armas (engine/defensa_aerea.py): ZU-23-2, S-125 Pechora-2M y Buk-M2E.

Geometria (de frente, de traves, alejandose), exposicion, eleccion del arma, probabilidad de derribo, recarga con
inoperatividad, y su lugar en el turno: fuego automatico, orden del operador, radar apagado e interferencia."""

import json

import pytest

from app.engine import catalogo
from app.engine import defensa_aerea as da
from app.models.aar import Combate
from app.models.evento import Evento
from app.models.orden import Orden
from tests.test_ciclo_vuelo import _caza, _orden, _refrescar
from tests.test_guerra_electronica import KM
from tests.test_orders import _avanzar, _escenario, _unidad

BUK, PECHORA, ZU = da.SISTEMAS["buk_m2e"], da.SISTEMAS["pechora_2m"], da.SISTEMAS["zu23_2"]


class _P:
    """Punto o bateria suelta."""

    def __init__(self, lat=0.0, lon=0.0, **kw):
        self.lat, self.lon, self.nombre = lat, lon, kw.pop("nombre", "B")
        for k, v in kw.items():
            setattr(self, k, v)


# ---------- datos ----------
def test_los_tres_sistemas_estan_en_el_catalogo_con_su_alcance():
    for s in da.SISTEMAS.values():
        m = catalogo.MODELOS[s.modelo]
        assert m.alcance_km == max(a.alcance_max_km for a in s.armas)
        assert catalogo.CLASES[m.clase].defensa_aerea
    assert catalogo.MODELOS["zu23_2"].clase == "artilleria_antiaerea"  # no emite
    assert not catalogo.CLASES["artilleria_antiaerea"].emisor
    assert BUK.total_vehiculos == sum(n for n, _ in BUK.vehiculos) >= 7
    assert {a.categoria for a in BUK.armas} == {"largo", "corto"}  # el operador elige


# ---------- geometria ----------
def test_el_alcance_util_depende_de_hacia_donde_vuela_la_aeronave():
    b = _P()
    de_frente, t1 = da.factor_aspecto(b, (60 * KM, 0.0), (40 * KM, 0.0))
    alejandose, t2 = da.factor_aspecto(b, (40 * KM, 0.0), (60 * KM, 0.0))
    de_traves, t3 = da.factor_aspecto(b, (40 * KM, -0.3), (40 * KM, 0.0))  # justo al pasar de traves
    assert de_frente == pytest.approx(1.0) and t1 == "de frente"
    assert alejandose == pytest.approx(0.55) and t2 == "alejándose"
    assert 0.7 < de_traves < 0.85 and t3 == "de través"
    assert da.factor_aspecto(b, None, (10 * KM, 0.0)) == (1.0, "en órbita")


def test_la_exposicion_es_la_cuerda_de_la_trayectoria_dentro_del_alcance():
    b = _P()
    # cruza de lado a lado por el centro: 200 km en la hora, 90 km dentro del circulo de 45 km -> 0,45 h
    s = da.exposicion_s(b, (0.0, -100 * KM / 1.0), (0.0, 100 * KM / 1.0), 45.0)
    assert s == pytest.approx(0.45 * 3600, rel=0.05)
    assert da.exposicion_s(b, None, (10 * KM, 0.0), 45.0) == 3600  # orbitando dentro
    assert da.exposicion_s(b, None, (60 * KM, 0.0), 45.0) == 0
    # el alcance minimo se descuenta
    assert da.exposicion_s(b, (0.0, -100 * KM), (0.0, 100 * KM), 45.0, 3.0) < s


# ---------- eleccion del arma ----------
def test_automatica_elige_el_misil_que_alcanza_y_el_operador_puede_fijar_uno():
    listos = {a.id: a.cargados for a in BUK.armas}
    reserva = {a.id: a.reserva for a in BUK.armas}
    largo, _ = da.elegir_arma(BUK, None, 30.0, 1500, True, 45, listos, reserva)
    assert largo.id == "9m317e"
    cerca, _ = da.elegir_arma(BUK, None, 2.0, 60, True, 45, listos, reserva)
    assert cerca.id == "igla_s"  # el 9M317E no tira a menos de 3 km
    igla = BUK.arma("igla_s")
    sin, motivo = da.elegir_arma(BUK, igla, 30.0, 1500, True, 45, listos, reserva)
    assert sin is None and "fuera de alcance" in motivo
    apagado, motivo = da.elegir_arma(BUK, None, 30.0, 1500, False, 45, listos, reserva)
    assert apagado is None and "radar de tiro apagado" in motivo
    techo, _ = da.elegir_arma(BUK, None, 4.0, 6000, False, 45, listos, reserva)
    assert techo is None  # la Igla-S no llega a 6 000 m y el 9M317E necesita el radar


def test_la_probabilidad_baja_con_interferencia_evasion_firma_y_de_noche_para_los_canones():
    misil, canon = BUK.armas[0], ZU.armas[0]
    base, _, _ = da.pk_efectivo(misil, _P(clase="caza"), interferida=False, noche=False, tripulada=False, firma=1.0, altura_m=1500)
    assert base == pytest.approx(misil.pk)
    interf, ef, _ = da.pk_efectivo(misil, _P(clase="caza"), interferida=True, noche=False, tripulada=False, firma=1.0, altura_m=1500)
    assert interf == pytest.approx(misil.pk * da.FACTOR_INTERFERENCIA_PK) and "interferido" in ef[0]
    evade, _, evasion = da.pk_efectivo(misil, _P(clase="caza"), interferida=False, noche=False, tripulada=True, firma=1.0, altura_m=1500)
    assert evasion and evade < base
    furtivo, _, _ = da.pk_efectivo(misil, _P(clase="caza"), interferida=False, noche=False, tripulada=False, firma=0.3, altura_m=1500)
    assert furtivo < base
    dia, _, _ = da.pk_efectivo(canon, _P(clase="helicoptero"), interferida=False, noche=False, tripulada=False, firma=1.0, altura_m=60)
    noche, _, _ = da.pk_efectivo(canon, _P(clase="helicoptero"), interferida=False, noche=True, tripulada=False, firma=1.0, altura_m=60)
    assert noche == pytest.approx(dia * da.FACTOR_NOCHE_CANON)
    assert dia > canon.pk  # los helicopteros son blanco facil para los canones


# ---------- enfrentamiento ----------
def _blanco(unidad_id, km, desde_km=None, n=4, tripulada=False, altura=1500.0):
    u = _P(km * KM, 0.0, id=unidad_id, clase="caza", nombre=f"C{unidad_id}")
    return {"unidad": u, "desde": (desde_km * KM, 0.0) if desde_km is not None else None, "hasta": (u.lat, u.lon),
            "altura_m": altura, "firma": 1.0, "tripulada": tripulada, "aeronaves": n, "traza_propia": True}


def _bateria(modelo, **kw):
    return _P(nombre=f"Bat {modelo}", modelo=modelo, municion=100.0, cargas_json=None, arma_elegida=None, **kw)


def test_una_bateria_buk_derriba_aviones_que_pasan_por_su_alcance_y_gasta_misiles():
    b = _bateria("buk_m2e")
    res = da.enfrentar(b, [_blanco(1, 20)], se_movio=False, radar_ok=True, interferida=False, noche=False)
    [d] = res.disparos
    assert d.arma.id == "9m317e" and d.salvas >= 2 and 0 < d.derribos <= 4
    guardado = json.loads(b.cargas_json)
    assert guardado["listos"]["9m317e"] + guardado["reserva"]["9m317e"] < 12 + 8  # gasto misiles


def test_al_vaciar_los_lanzadores_recarga_desde_la_reserva_y_queda_inoperativa_ese_tiempo():
    b = _bateria("buk_m2e")
    blancos = [_blanco(i, 15 + i, n=4) for i in range(1, 9)]  # muchos blancos orbitando dentro
    res = da.enfrentar(b, blancos, se_movio=False, radar_ok=True, interferida=False, noche=False)
    assert any("recargó" in r and "13 min" in r for r in res.recargas)
    assert b.municion < 100.0  # la reserva baja con la municion de la unidad


def test_si_se_movio_tiene_menos_tiempo_de_fuego_y_el_pechora_tarda_en_desplegar():
    quieta, movida = _bateria("buk_m2e"), _bateria("buk_m2e")
    r1 = da.enfrentar(quieta, [_blanco(1, 20, n=8)], se_movio=False, radar_ok=True, interferida=False, noche=False)
    r2 = da.enfrentar(movida, [_blanco(1, 20, n=8)], se_movio=True, radar_ok=True, interferida=False, noche=False)
    assert r2.disparos and r2.disparos[0].salvas <= r1.disparos[0].salvas
    pechora = _bateria("pechora_2m")
    r3 = da.enfrentar(pechora, [_blanco(1, 20)], se_movio=True, radar_ok=True, interferida=False, noche=False)
    assert r3.disparos == [] and "Desplegando" in r3.sin_fuego


def test_una_pasada_rapida_alejandose_puede_quedar_fuera_de_su_alcance():
    b = _bateria("pechora_2m")
    # se aleja de 25 a 120 km: con el misil persiguiendola el alcance util cae a ~17 km
    res = da.enfrentar(b, [_blanco(1, 120, desde_km=25)], se_movio=False, radar_ok=True, interferida=False, noche=False)
    assert res.disparos == [] and 1 in res.motivos


# ---------- en el turno ----------
def _buk(db, esc, **kw):
    return _unidad(db, esc, **{**dict(nombre="Buk", clase="antiaerea", modelo="buk_m2e", alcance_km=45, deteccion_km=160,
                                      velocidad_kmh=45), **kw})


def test_en_el_turno_la_bateria_tira_sola_y_registra_el_combate_con_su_probabilidad(db_session):
    esc = _escenario(db_session)
    buk = _buk(db_session, esc)
    intruso = _caza(db_session, esc, nombre="Su-30", bando="rojo", lat=25 * KM, aeronaves=4)
    _avanzar(db_session, esc)
    _refrescar(db_session, intruso, buk)
    [orden] = db_session.query(Orden).filter(Orden.unidad_id == buk.id, Orden.detalle == "defensa aerea").all()
    assert orden.estado == "resuelta" and "9M317E" in orden.resultado and "salva" in orden.resultado
    assert intruso.fuerza < 100
    combate = db_session.query(Combate).filter(Combate.orden_id == orden.id).one()
    assert 0 < combate.ratio < 1 and combate.perdida_atacante == 0
    assert "maniobras evasivas" in " ".join(e.descripcion for e in db_session.query(Evento).filter(Evento.bando_destino == "rojo"))
    assert buk.sistema_da["armas"][0]["listos"] < 12 or buk.municion < 100


def test_con_el_radar_apagado_solo_tira_la_igla_de_cerca(db_session):
    esc = _escenario(db_session)
    buk = _buk(db_session, esc, emitiendo=False)
    lejos = _caza(db_session, esc, nombre="Lejos", bando="rojo", lat=25 * KM)
    cerca = _caza(db_session, esc, nombre="Cerca", bando="rojo", lat=3 * KM, perfil_vuelo="rasante")
    _avanzar(db_session, esc)
    _refrescar(db_session, lejos, cerca)
    ordenes = db_session.query(Orden).filter(Orden.unidad_id == buk.id, Orden.detalle == "defensa aerea").all()
    assert [o.objetivo_unidad_id for o in ordenes] == [cerca.id]
    assert "Igla-S" in ordenes[0].resultado and lejos.fuerza == 100


def test_el_operador_fija_el_arma_y_la_orden_manual_se_rechaza_si_no_alcanza(db_session):
    esc = _escenario(db_session)
    buk = _buk(db_session, esc, arma_elegida="igla_s", fuego_libre=False)
    lejos = _caza(db_session, esc, nombre="Lejos", bando="rojo", lat=25 * KM)
    o = _orden(db_session, esc, buk, "atacar", objetivo=lejos)
    _avanzar(db_session, esc)
    _refrescar(db_session, o, lejos)
    assert o.estado == "rechazada" and "Igla-S" in o.resultado and "fuera de alcance" in o.resultado
    assert lejos.fuerza == 100


def test_api_permite_elegir_el_arma_y_la_ficha_muestra_el_sistema(api):
    prof = api("prof")
    esc = prof.post("/api/escenarios", json={"nombre": "DA"}).json()
    base = f"/api/escenarios/{esc['id']}"
    r = prof.post(f"{base}/unidades", json=dict(nombre="Buk", bando="azul", tipo="terrestre", clase="antiaerea",
                                                modelo="buk_m2e", lat=10.0, lon=-66.0))
    assert r.status_code == 200, r.text
    u = r.json()
    assert u["alcance_km"] == 45 and u["sistema_da"]["armas"][0]["listos"] == 12
    r = prof.post(f"{base}/unidades/{u['id']}/defensa", json={"arma": "igla_s"})
    assert r.status_code == 200 and r.json()["sistema_da"]["arma_elegida"] == "igla_s"
    assert prof.post(f"{base}/unidades/{u['id']}/defensa", json={"arma": "x"}).status_code == 400
    assert prof.post(f"{base}/unidades/{u['id']}/defensa", json={"arma": ""}).json()["sistema_da"]["arma_elegida"] is None
    cat = prof.get("/api/catalogo").json()
    assert {"zu23_2", "pechora_2m", "buk_m2e"} <= set(cat["sistemas_da"])


def test_cada_arma_tiene_su_reserva_y_lo_repuesto_va_a_la_que_le_falta():
    b = _bateria("buk_m2e")
    blancos = [_blanco(i, 15 + i, n=4) for i in range(1, 9)]
    da.enfrentar(b, blancos, se_movio=False, radar_ok=True, interferida=False, noche=False)
    res = da.reservas(b)
    assert res["9m317e"] < 8 and res["igla_s"] == 8  # la Igla-S no se toco
    assert b.municion == pytest.approx(100 * sum(res.values()) / da.reserva_total(BUK))
    b.municion = 100.0  # el deposito repone todo
    assert da.reservas(b) == {"9m317e": 8, "igla_s": 8}
