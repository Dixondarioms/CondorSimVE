"""Apresto Operacional y PCAO (engine/apresto.py), segun el Manual de Apresto Operacional de la FANB (CEO-MC-159)."""

import json
from types import SimpleNamespace

from app.engine import aeronaves, apresto, toe
from app.models.documento_tiem import DocumentoTiem
from app.models.evento import Evento
from app.models.orden import Orden
from app.models.unidad import Unidad
from tests.test_api import _preparar
from tests.test_ciclo_vuelo import _base, _refrescar
from tests.test_orders import _avanzar, _escenario


class _Esc:
    def __init__(self, **apresto_cfg):
        self.apresto_json = json.dumps(apresto_cfg) if apresto_cfg else None
        self.turno_actual, self.personal_json, self.transmisiones_json, self.fallas = 1, None, None, False


def _u(**kw):
    datos = dict(id=1, nombre="U", bando="azul", tipo="terrestre", clase="infanteria", modelo="", fuerza=100.0,
                 municion=100.0, estado="activa", aeronaves=0, personal=None, lat=0.0, lon=0.0, en_tierra=False)
    return SimpleNamespace(**{**datos, **kw})


# ---------- calificacion (tabla A-E y Anexo A) ----------
def test_la_unidad_tiene_apresto_si_alcanza_cada_minimo_de_la_tabla():
    esc = _Esc()
    u = _u()
    fila = toe.partes([u], esc, "azul")["unidades"][0]
    r = apresto.calificar(u, fila, esc, [u], 1)
    assert r["tiene"] and r["aspectos"]["personal"] == 100
    r = apresto.calificar(_u(municion=85.0), fila, esc, [u], 1)  # B armamento y municion: minimo 90 %
    assert not r["tiene"] and any("B. Armamento" in m for m in r["motivos"])
    r = apresto.calificar(_u(fuerza=70.0), fila, esc, [u], 1)
    assert not r["tiene"] and any("C. Equipamiento" in m for m in r["motivos"])
    bajo = _Esc(azul={"adiestramiento": 80})  # D adiestramiento: minimo 85 %
    assert any("D. Adiestramiento" in m for m in apresto.calificar(u, fila, bajo, [u], 1)["motivos"])


def test_escuadron_con_menos_del_80_por_ciento_de_aeronaves_no_tiene_apresto():
    caza = _u(id=2, tipo="aerea", clase="caza", modelo="f16", aeronaves=4)
    esc = _Esc(azul={"grado": "paz"})  # en tiempo de paz el 40 % esta preservado
    fila = toe.partes([caza], esc, "azul")["unidades"][0]
    r = apresto.calificar(caza, fila, esc, [caza], 1)
    assert r["tipo"] == "aviacion" and not r["tiene"]
    assert any("Aeronaves disponibles" in m for m in r["motivos"])
    assert apresto.calificar(caza, fila, _Esc(), [caza], 1)["tiene"]
    sin_pilotos = _Esc(azul={"grado": "completo"})
    sin_pilotos.personal_json = json.dumps({"azul": {"cobertura": 60}})
    fila = toe.partes([caza], sin_pilotos, "azul")["unidades"][0]
    r = apresto.calificar(caza, fila, sin_pilotos, [caza], 1)
    assert any("Personal de vuelo" in m for m in r["motivos"])


def test_exigencias_de_defensa_aerea_y_radar():
    esc = _Esc()
    zu = _u(id=3, clase="artilleria_antiaerea", modelo="zu23_2", fuerza=70.0)
    fila = toe.partes([zu], esc, "azul")["unidades"][0]
    r = apresto.calificar(zu, fila, esc, [zu], 1)
    assert r["tipo"] == "gadaa" and any("Equipo de combate operativo" in m for m in r["motivos"])
    radar = _u(id=4, clase="radar", fuerza=78.0)
    fila = toe.partes([radar], esc, "azul")["unidades"][0]
    assert any("Radares operativos" in m for m in apresto.calificar(radar, fila, esc, [radar], 1)["motivos"])


# ---------- grados y PCAO ----------
def test_la_pcao_corre_sus_5_eventos_y_lleva_a_completo_apresto():
    esc = _Esc(azul={"grado": "paz", "plazos": {"aviso": 1, "incorporacion": 2, "organizacion": 1, "material": 2,
                                                "adiestramiento": 2}, "adiestramiento": 70, "adiestramiento_meta": 90})
    assert not apresto.reservas_incorporadas(esc, "azul", 1) and apresto.fraccion_aeronaves_listas(esc, "azul", 1) == 0.6
    apresto.iniciar_pcao(esc, "azul", 10)
    p = apresto.progreso(esc, "azul", 12)
    assert p["activa"] and p["total"] == 8 and p["eventos"][1]["estado"] == "en curso"
    assert not apresto.reservas_incorporadas(esc, "azul", 12) and apresto.reservas_incorporadas(esc, "azul", 13)
    assert apresto.fraccion_aeronaves_listas(esc, "azul", 15) == 0.6 and apresto.fraccion_aeronaves_listas(esc, "azul", 16) == 1.0
    assert apresto.adiestramiento(esc, "azul", 16) == 70 and apresto.adiestramiento(esc, "azul", 17) == 80
    assert apresto.adiestramiento(esc, "azul", 18) == 90
    textos = [t for turno in range(10, 18) for _, t in apresto.avanzar(esc, turno)]
    assert len([t for t in textos if t.startswith("PCAO: se cumplió")]) == 5 and "Completo Apresto" in textos[-1]
    assert apresto.config(esc, "azul")["grado"] == "completo"


def test_sin_configurar_no_cambia_nada():
    esc = _Esc()
    assert apresto.reservas_incorporadas(esc, "azul") and apresto.fraccion_aeronaves_listas(esc, "azul") == 1.0
    assert apresto.factor_adiestramiento(esc, "azul") == 1.0
    bajo = _Esc(azul={"adiestramiento": 0})
    assert apresto.factor_adiestramiento(bajo, "azul") == apresto.FACTOR_ADIESTRAMIENTO_MIN


def test_las_reservas_no_cubren_hasta_el_evento_2():
    u = _u(id=5, tipo="aerea", clase="caza", modelo="f16", aeronaves=4)
    esc = _Esc(azul={"grado": "paz"})
    esc.personal_json = json.dumps({"azul": {"cobertura": 50, "reserva": 100}})
    assert toe.partes([u], esc, "azul")["unidades"][0]["categorias"]["pilotos"]["reserva"] == 0
    esc.apresto_json = json.dumps({"azul": {"grado": "completo"}})
    assert toe.partes([u], esc, "azul")["unidades"][0]["categorias"]["pilotos"]["reserva"] > 0


def test_plazos_del_plan_de_pcao():
    filas = [{"evento": e, "plazo": str(p)} for e, p in zip("12345", (2, 12, 6, 24, 48))]
    assert apresto.plazos_del_plan({"eventos": filas}) == {"aviso": 2, "incorporacion": 12, "organizacion": 6,
                                                            "material": 24, "adiestramiento": 48}
    assert apresto.plazos_del_plan({"eventos": filas[:3]}) is None
    assert apresto.plazos_del_plan({"eventos": [{"plazo": "x"}] * 5}) is None


# ---------- motor y API ----------
def test_en_tiempo_de_paz_despegan_solo_las_aeronaves_no_preservadas(db_session):
    esc = _escenario(db_session)
    esc.apresto_json = json.dumps({"azul": {"grado": "paz"}})
    base = _base(db_session, esc)
    o = Orden(escenario_id=esc.id, unidad_id=base.id, tipo="despegar", detalle=aeronaves.codificar("f16", 5, "Halcon"),
              turno_emitida=esc.turno_actual)
    db_session.add(o)
    db_session.commit()
    _avanzar(db_session, esc)
    _refrescar(db_session, o)
    grupo = db_session.query(Unidad).filter(Unidad.nombre == "Halcon").one()
    assert grupo.aeronaves == 3  # el 60 % de 5


def test_api_grado_pcao_y_estado(api, db_engine):
    prof, base, *_ = _preparar(api)
    r = prof.patch(f"{base}/config", json={"apresto": {"azul": {"grado": "elevado", "fase": 2,
                                                                 "plazos": {"aviso": 1, "incorporacion": 1, "organizacion": 1,
                                                                            "material": 1, "adiestramiento": 1}}}})
    assert r.status_code == 200, r.text
    assert r.json()["escenario"]["apresto"]["azul"]["grado"] == "elevado"
    alfa = api("alfa")
    e = alfa.get(base).json()
    assert "apresto" not in e["escenario"] and e["apresto"]["azul"]["aeronaves_listas_pct"] == 80
    assert e["apresto"]["azul"]["unidades"] and set(e["apresto"]) == {"azul"}
    assert alfa.post(f"{base}/pcao", json={}).status_code == 200
    assert alfa.post(f"{base}/pcao", json={}).status_code == 400  # ya en marcha
    for _ in range(6):
        prof.post(f"{base}/avanzar_turno")
    assert alfa.get(base).json()["apresto"]["azul"]["config"]["grado"] == "completo"
    from sqlalchemy.orm import sessionmaker
    with sessionmaker(bind=db_engine)() as db:
        assert any("Completo Apresto" in x.descripcion for x in db.query(Evento))
    # el alumno rojo no puede ordenarla para el azul: se toma su propio bando, que ya esta en completo apresto
    assert api("bravo").post(f"{base}/pcao", json={"bando": "azul"}).status_code == 400


def test_api_la_pcao_toma_los_plazos_del_plan(api, db_engine):
    prof, base, *_ = _preparar(api)
    prof.patch(f"{base}/config", json={"apresto": {"azul": {"grado": "paz"}}})
    from sqlalchemy.orm import sessionmaker
    esc_id = int(base.rsplit("/", 1)[1])
    filas = [{"evento": e, "medidas": "", "responsable": "", "plazo": str(p)} for e, p in zip("12345", (1, 2, 3, 4, 5))]
    with sessionmaker(bind=db_engine)() as db:
        db.add(DocumentoTiem(escenario_id=esc_id, bando="azul", tipo="plan_pcao", contenido_json=json.dumps({"eventos": filas})))
        db.commit()
    r = api("alfa").post(f"{base}/pcao", json={})
    assert r.status_code == 200 and r.json()["pcao"]["total"] == 15
