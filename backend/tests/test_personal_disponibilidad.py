"""Plantilla de personal (engine/toe.py) y disponibilidad, fallas y esfuerzo aereo (engine/disponibilidad.py)."""

import json

import pytest

from app.engine import aeronaves, disponibilidad, toe
from app.models.evento import Evento
from app.models.orden import Orden
from app.models.unidad import Unidad
from tests.test_ciclo_vuelo import _base, _caza, _refrescar
from tests.test_orders import _avanzar, _escenario, _unidad


def _grupo(modelo, n, bando="azul", **kw):
    return Unidad(id=kw.pop("id", 1), nombre=f"{modelo}", bando=bando, tipo="aerea", clase="caza", modelo=modelo, aeronaves=n,
                  fuerza=kw.pop("fuerza", 100.0), estado="activa", lat=0, lon=0, **kw)


class _Esc:
    def __init__(self, **personal):
        self.personal_json = json.dumps(personal)
        self.semilla, self.turno_actual, self.fallas, self.esfuerzo_json = 7, 1, True, None


# ---------- plantilla ----------
def test_por_aeronave_tres_o_cuatro_tripulaciones_y_siete_tecnicos_por_especialidad():
    f16 = toe.plantilla(_grupo("f16", 4))
    assert f16["pilotos"] == 12 and f16["tecnicos"] == 28 and f16["tropa"] == 12
    assert f16["especialidades"]["motores"] == 8 and sum(f16["especialidades"].values()) == 28
    assert toe.plantilla(_grupo("su30", 2))["pilotos"] == 12  # 2 tripulantes x 2 aeronaves x 3 tripulaciones
    assert toe.plantilla(_grupo("f16", 4), tripulaciones=4)["pilotos"] == 16
    buk = Unidad(nombre="Buk", bando="azul", tipo="terrestre", clase="antiaerea", modelo="buk_m2e", fuerza=100.0, estado="activa")
    p = toe.plantilla(buk)
    assert p["oficiales"] + p["tecnicos"] + p["tropa"] == 30 and p["pilotos"] == 0


def test_el_deficit_lo_cubren_las_reservas_y_la_milicia_solo_la_tropa():
    esc = _Esc(azul={"cobertura": 50, "reserva": 5, "milicia": 100})
    partes = toe.partes([_grupo("f16", 4)], esc, "azul")
    [fila] = partes["unidades"]
    pil, tec, tropa = (fila["categorias"][c] for c in ("pilotos", "tecnicos", "tropa"))
    assert pil["existente"] == 6 and pil["reserva"] == 5 and pil["milicia"] == 0 and pil["deficit"] == 1
    assert tec["reserva"] == 0 and tec["deficit"] == 14  # las reservas se agotaron con los pilotos
    assert tropa["milicia"] == 6 and tropa["deficit"] == 0
    assert partes["reserva_restante"] == 0 and partes["milicia_restante"] == 94
    assert fila["cobertura_pilotos"] == pytest.approx(11 / 12, abs=0.001)


def test_las_bajas_reducen_lo_existente():
    [fila] = toe.partes([_grupo("f16", 4, fuerza=50.0)], _Esc(), "azul")["unidades"]
    assert fila["categorias"]["pilotos"]["existente"] == 6 and fila["categorias"]["pilotos"]["deficit"] == 6


# ---------- disponibilidad ----------
def test_salen_las_aeronaves_listas_y_no_mas_que_las_tripulaciones():
    esc, base = _Esc(), Unidad(id=3, nombre="BA")
    listas, motivo = disponibilidad.listas_para_despegar(esc, base, "f16", 8, 1.0, 1.0, 3, "a")
    assert 0 <= listas <= 8 and (listas == 8 or "mantenimiento" in motivo)
    pocas, motivo = disponibilidad.listas_para_despegar(esc, base, "f16", 8, 1.0, 0.05, 3, "a")
    assert pocas <= 1 and "tripulaciones" in motivo
    # sin tecnicos la disponibilidad cae a la mitad: en promedio salen menos
    con = sum(disponibilidad.listas_para_despegar(esc, base, "f16", 8, 1.0, 1.0, 3, i)[0] for i in range(200))
    sin = sum(disponibilidad.listas_para_despegar(esc, base, "f16", 8, 0.0, 1.0, 3, i)[0] for i in range(200))
    assert sin < con * 0.7


def test_con_fallas_el_despegue_lanza_solo_las_listas_y_cuenta_el_esfuerzo(db_session):
    esc = _escenario(db_session)
    esc.fallas = True
    base = _base(db_session, esc)
    o = Orden(escenario_id=esc.id, unidad_id=base.id, tipo="despegar", detalle=aeronaves.codificar("f16", 8, "Halcón"),
              turno_emitida=esc.turno_actual)
    db_session.add(o)
    db_session.commit()
    _avanzar(db_session, esc)
    _refrescar(db_session, o, esc)
    e = disponibilidad.esfuerzo(esc)["azul"]
    assert o.estado == "resuelta" and e["salidas"] + e["no_disponibles"] == 8
    grupo = db_session.query(Unidad).filter(Unidad.nombre == "Halcón").one()
    assert grupo.aeronaves == e["salidas"]


def test_fallas_en_vuelo_hacen_volver_al_grupo(db_session, monkeypatch):
    monkeypatch.setitem(disponibilidad.FALLA_HORA_CLASE, "caza", 1.0)  # todas fallan
    esc = _escenario(db_session)
    esc.fallas = True
    _base(db_session, esc)
    caza = _caza(db_session, esc, modelo="f16", aeronaves=2, lat=0.2)
    _avanzar(db_session, esc)
    _refrescar(db_session, esc)
    assert disponibilidad.esfuerzo(esc)["azul"]["abortos"] == 2
    assert db_session.query(Orden).filter(Orden.unidad_id == caza.id, Orden.detalle == "falla tecnica").count() == 1
    assert any("falla técnica" in e.descripcion for e in db_session.query(Evento))


def test_sin_fallas_igual_se_cuentan_las_horas_de_vuelo(db_session):
    esc = _escenario(db_session)
    _caza(db_session, esc, modelo="f16", aeronaves=4, lat=0.2)
    _avanzar(db_session, esc)
    _refrescar(db_session, esc)
    r = disponibilidad.resumen(esc, "azul", db_session.query(Unidad).all())
    assert r["horas"] == pytest.approx(4.0) and r["abortos"] == 0 and r["atricion_pct"] == 0


def test_api_configura_el_personal_y_el_estado_trae_partes_y_esfuerzo(api):
    prof = api("prof")
    esc = prof.post("/api/escenarios", json={"nombre": "TOE"}).json()
    base = f"/api/escenarios/{esc['id']}"
    r = prof.patch(f"{base}/config", json={"fallas": True, "personal": {"azul": {"cobertura": 80, "reserva": 20,
                                                                                    "milicia": 50, "tripulaciones": 4}}})
    assert r.status_code == 200, r.text
    e = r.json()["escenario"]
    assert e["fallas"] is True and e["personal"]["azul"]["cobertura"] == 80 and e["personal"]["azul"]["tripulaciones"] == 4
    assert e["personal"]["rojo"]["cobertura"] == 100
    prof.post(f"{base}/unidades", json=dict(nombre="F-16", bando="azul", tipo="aerea", clase="caza", modelo="f16",
                                            aeronaves=4, lat=10.0, lon=-66.0))
    estado = prof.get(base).json()
    [fila] = estado["personal_toe"]["azul"]["unidades"]
    assert fila["categorias"]["pilotos"]["autorizado"] == 16
    assert estado["esfuerzo"]["azul"]["fallas"] is True
    assert prof.patch(f"{base}/config", json={"personal": {"azul": {"cobertura": 150}}}).status_code == 422
