"""Calculo de armamento y BDA (engine/weaponeering.py), anillos de Warden (engine/warden.py), corte de carreteras e
inteligencia de satelites e INTSUM (engine/inteligencia.py)."""

import json
from types import SimpleNamespace

from app.engine import inteligencia, movimiento, warden, weaponeering
from app.engine.clima import ClimaLocal
from app.models.contacto import Contacto
from app.models.evento import Evento
from app.models.obra import Obra
from tests.conftest import TerrenoFalso
from tests.test_aeronaves import _base_aerea
from tests.test_api import _preparar
from tests.test_ciclo_vuelo import _base, _caza, _refrescar
from tests.test_misiones import P, _mision, aterrizaje
from tests.test_orders import _avanzar, _escenario, _unidad


def _u(**kw):
    datos = dict(id=1, nombre="X", bando="rojo", tipo="terrestre", clase="infanteria", lat=0.0, lon=0.0, fuerza=100.0,
                 estado="activa", aeronaves=0, en_tierra=False, arma_elegida=None)
    return SimpleNamespace(**{**datos, **kw})


# ---------- calculo de armamento ----------
def test_reproduce_el_ejemplo_del_documento():
    w = weaponeering.calcular("BMK", "aviones", "despegue", 45, area_m2=200 * 120)
    assert w["mae_m2"] == round(144000 * 0.0929) and w["impactos"] == 6 and w["lanzar"] == 18
    guiada = weaponeering.calcular("BBU", "aviones", "despegue", 45, area_m2=200 * 120)
    assert guiada["impactos"] == 6 and guiada["lanzar"] == 8 and guiada["radio_escombros_m"] == 110
    assert weaponeering.calcular("MAA", "aviones") is None  # un misil aire-aire no es armamento de ataque
    pieza = weaponeering.calcular("BMK", "antiaerea", dmpi=4, aeronaves=2)
    # 4 piezas antiaereas: 2 MK-82 en cada una y x3 por la dispersion = 24; dos F-16 llevan 12
    assert pieza["criterio"] == "neutraliza" and pieza["lanzar"] == 24 and pieza["lleva"] == 12 and not pieza["suficiente"]


def test_tipo_de_blanco_y_dmpi():
    assert weaponeering.tipo_de_blanco(_u(tipo="base", clase="base_aerea")) == "aviones"
    assert weaponeering.tipo_de_blanco(_u(clase="antiaerea")) == "antiaerea"
    assert weaponeering.tipo_de_blanco(_u(clase="radar")) == "radar"
    assert weaponeering.dmpi_de(_u(tipo="aerea", clase="caza", aeronaves=6, en_tierra=True), "aviones") == 3


def test_bda_en_tres_niveles_y_recomendacion():
    atacante = _u(nombre="Halcon", bando="azul", tipo="aerea", clase="caza", aeronaves=2, arma_elegida="BMK")
    radar = _u(nombre="Radar Norte", clase="radar")
    refineria = _u(id=2, nombre="Refineria", tipo="base", clase="refineria", lat=0.001)
    r = weaponeering.bda(atacante, radar, 100.0, 64.0, [radar, refineria])
    assert r["nivel1"] == "daño físico estimado 40 %" and r["nivel2"] == "degradado" and "Anillo 5" in r["nivel3"]
    assert r["recomendacion"].startswith("Re-atacar") and r["colaterales"] == ["Refineria a 111 m"]
    assert weaponeering.bda(atacante, radar, 100.0, 0.0, [radar])["nivel2"] == "destruido"
    assert "No re-atacar" in weaponeering.bda(atacante, radar, 100.0, 20.0, [radar])["recomendacion"]
    assert "BDA de Halcon sobre Radar Norte" in weaponeering.texto_bda(atacante, r)


def test_el_ataque_aereo_deja_un_bda_para_el_atacante(db_session):
    esc = _escenario(db_session)
    caza = _caza(db_session, esc, nombre="Halcon", lat=0.0, municion=100)
    blanco = _unidad(db_session, esc, nombre="Radar Norte", bando="rojo", clase="radar", lat=0.1, deteccion_km=0)
    from tests.test_ciclo_vuelo import _orden

    _orden(db_session, esc, caza, "atacar", objetivo=blanco)
    _avanzar(db_session, esc)
    bda = [e for e in db_session.query(Evento) if e.descripcion.startswith("BDA de Halcon")]
    assert bda and bda[0].bando_destino == "azul" and "nivel 2" in bda[0].descripcion


# ---------- anillos de Warden ----------
def test_anillos_de_warden():
    assert warden.anillo(_u(clase="centro_comunicaciones")) == 1
    assert warden.anillo(_u(clase="refineria")) == 2 and warden.anillo(_u(clase="puente")) == 3
    assert warden.anillo(_u(clase="blindado")) == 5
    filas = {f["anillo"]: f for f in warden.resumen([
        (_u(clase="termoelectrica", fuerza=20.0), True), (_u(clase="refineria"), False),
        (_u(clase="blindado", fuerza=50.0), True), (_u(clase="blindado", bando="azul"), True)], "azul")}
    assert filas[2]["objetivos"] == 2 and filas[2]["neutralizados"] == 1 and filas[2]["sin_noticias"] == 1
    assert filas[5]["objetivos"] == 1 and filas[5]["degradados"] == 1 and 4 not in filas


# ---------- corte de carretera ----------
class _ConCarretera(TerrenoFalso):
    def via(self, lat, lon):
        return 2


def test_el_crater_hace_perder_la_carretera():
    blindado = SimpleNamespace(tipo="terrestre", clase="blindado")
    crater = SimpleNamespace(tipo="crater", lat=0.0, lon=0.0, radio_km=1.0)
    con = movimiento.factor_terreno(blindado, "llano", [], 0.0, 0.0, 2)
    sin = movimiento.factor_terreno(blindado, "llano", [crater], 0.0, 0.0, 2)
    assert sin < con and sin == movimiento.FACTOR_MOVIMIENTO.get("llano", 1.0) * movimiento.FACTOR_CRATER


def test_una_mision_corta_la_carretera(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    caza = _caza(db_session, esc, lat=0.2, municion=100)
    m = _mision(db_session, esc, "INTERDICCION", [P("blanco", 40, corte=True), aterrizaje(base)], unidad=caza)
    from app.engine import clock

    clock.avanzar_turno(db_session, esc, _ConCarretera())
    _refrescar(db_session, m)
    [obra] = db_session.query(Obra).all()
    assert obra.tipo == "crater" and obra.bando == "azul" and "Cortó la carretera" in m.resultado


# ---------- inteligencia ----------
def test_satelites_pasadas_y_fotos():
    esc = SimpleNamespace(semilla=1, inteligencia_json=None)
    inteligencia.configurar(esc, "azul", 2, "optico")
    turnos = [t for t in range(1, 25) if inteligencia.pasadas(esc, "azul", t)]
    assert len(turnos) == 4  # 2 satelites, 2 pasadas por dia cada uno
    enemigo = _u(lat=0.0, lon=0.0)
    propia = _u(id=2, bando="azul", lat=0.0, lon=0.0)
    # una pasada cuya franja cubre la unidad (la traza se corre al azar hasta 300 km del centro del teatro)
    t = next(t for t in range(1, 500) if inteligencia.pasadas(esc, "azul", t)
             and abs(inteligencia.traza(esc, "azul", inteligencia.pasadas(esc, "azul", t)[0], t, [enemigo]) * 111.32) < 100)
    dia, noche = ClimaLocal("despejado", periodo="dia"), ClimaLocal("despejado", periodo="noche")
    vistos = inteligencia.fotografiar(esc, "azul", t, [enemigo, propia], dia)
    assert [x["unidad_id"] for x in vistos] == [1]
    assert inteligencia.fotografiar(esc, "azul", t, [enemigo, propia], noche) == []
    inteligencia.configurar(esc, "azul", tipo="radar")
    assert inteligencia.fotografiar(esc, "azul", t, [enemigo, propia], noche)  # el radar ve de noche


def test_las_imagenes_llegan_procesadas_al_turno_siguiente_y_el_intsum(db_session):
    esc = _escenario(db_session)
    inteligencia.configurar(esc, "azul", 1, "radar")
    enemigo = _unidad(db_session, esc, nombre="Brigada", bando="rojo", lat=0.0, lon=0.0)
    _unidad(db_session, esc, nombre="Base", bando="azul", tipo="base", clase="base_aerea", lat=0.5, lon=0.0)
    t = next(t for t in range(1, 500) if inteligencia.pasadas(esc, "azul", t)
             and abs(inteligencia.traza(esc, "azul", 0, t, [enemigo]) * 111.32) < 100)
    esc.turno_actual = t
    inteligencia.procesar_turno(db_session, esc)
    db_session.flush()
    assert db_session.query(Contacto).filter(Contacto.bando == "azul").count() == 0  # aun en proceso
    esc.turno_actual = t + 1
    inteligencia.procesar_turno(db_session, esc)
    db_session.flush()
    c = db_session.query(Contacto).filter(Contacto.bando == "azul").one()
    assert c.unidad_id == enemigo.id and c.turno_visto == t
    assert any("Inteligencia de imágenes" in e.descripcion for e in db_session.query(Evento))
    esc.turno_actual = ((t + 1) // inteligencia.REPORTE_TURNOS + 1) * inteligencia.REPORTE_TURNOS
    inteligencia.procesar_turno(db_session, esc)
    db_session.flush()
    intsum = [e for e in db_session.query(Evento) if e.descripcion.startswith("INTSUM")]
    assert {e.bando_destino for e in intsum} == {"azul", "rojo"}
    assert any("Base" in e.descripcion for e in intsum if e.bando_destino == "azul")
    assert inteligencia.resumen(esc, "azul")["historial"]


def test_api_satelites_solo_para_el_instructor_y_weaponeering_en_el_plan(api):
    prof, base, a, r1, r2 = _preparar(api)
    r = prof.patch(f"{base}/config", json={"inteligencia": {"azul": {"satelites": 2, "tipo": "radar"}}})
    assert r.status_code == 200, r.text
    assert r.json()["escenario"]["inteligencia"]["azul"] == {"satelites": 2, "tipo": "radar"}
    alfa = api("alfa")
    estado = alfa.get(base).json()
    assert "inteligencia" not in estado["escenario"] and estado["inteligencia"]["azul"]["config"]["satelites"] == 2
    assert {f["anillo"] for f in estado["warden"]["azul"]} == {1, 2, 3, 5}
    ba = _base_aerea(prof, base, lat=0.0, lon=0.3)
    aterr = {"tipo": "aterrizaje", "lat": ba["lat"], "lon": ba["lon"], "base_id": ba["id"]}
    cuerpo = {"rol": "INTERDICCION", "base_id": ba["id"], "modelo": "f16", "aeronaves": 1,
              "puntos": [{"tipo": "blanco", "lat": r1["lat"], "lon": r1["lon"], "objetivo_unidad_id": r1["id"]}, aterr],
              "ota": {"armamento_primario": "BMK"}}
    plan = alfa.post(f"{base}/misiones/previsualizar", json=cuerpo).json()["plan"]
    assert plan["weaponeering"]["lanzar"] > 0 and plan["weaponeering"]["lleva"] == 6
    corte = {**cuerpo, "puntos": [{"tipo": "blanco", "lat": 0.5, "lon": 0.3, "corte": True}, aterr]}
    assert alfa.post(f"{base}/misiones/previsualizar", json=corte).json()["errores"] == []
    malo = {**cuerpo, "puntos": [{"tipo": "paso", "lat": 0.5, "lon": 0.3, "corte": True}, aterr]}
    assert any("corte" in e for e in alfa.post(f"{base}/misiones/previsualizar", json=malo).json()["errores"])
    assert json.loads(json.dumps(plan))  # serializable
