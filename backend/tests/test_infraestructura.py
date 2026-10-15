"""Infraestructura no militar (energia, refinerias, comunicaciones, puentes), personal, cuadro radar, porcentaje de
objetivos y tiempo de recorrido de las ordenes de mover."""

import json
from pathlib import Path
from types import SimpleNamespace

from app.engine import catalogo, clima as clima_mod, contactos, infraestructura as infra, logistica, movimiento, personal, vision
from app.engine import guerra_electronica as ge_mod
from app.engine import orders
from app.engine.clock import avanzar_turno
from app.models.evento import Evento
from app.models.unidad import Unidad
from app.terreno import FACTOR_PUENTE
from tests.conftest import TerrenoFalso
from tests.test_api import _preparar
from tests.test_orders import _escenario, _unidad

DATOS = Path(__file__).resolve().parents[2] / "frontend" / "static" / "geo" / "venezuela" / "infraestructura.json"


def _infra(db, esc, clase, bando="azul", fuerza=100.0, **kw):
    c = catalogo.CLASES[clase]
    return _unidad(db, esc, nombre=kw.pop("nombre", clase), bando=bando, tipo="base", clase=clase, fuerza=fuerza,
                   velocidad_kmh=0, alcance_km=0, deteccion_km=0, **kw) if c else None


# ---------------------------------------------------------------- catalogo y datos reales
def test_las_cinco_clases_de_infraestructura_son_fijas_y_sin_armas():
    for clase, cat in [("termoelectrica", "energia"), ("hidroelectrica", "energia"), ("refineria", "combustible"),
                       ("centro_comunicaciones", "comunicaciones"), ("puente", "puente")]:
        c = catalogo.CLASES[clase]
        assert c.tipo == "base" and c.movilidad == "fija" and c.infraestructura == cat
        assert not any(c.ataque_vs.values()) and not c.suministra and not c.plazas_aeronaves
        assert catalogo.como_dict(c)["infraestructura"] == cat


def test_la_capa_trae_instalaciones_reales_de_venezuela():
    datos = json.loads(DATOS.read_text(encoding="utf-8"))
    inst = datos["instalaciones"]
    clases = {i["clase"] for i in inst}
    assert clases == {"termoelectrica", "hidroelectrica", "refineria", "centro_comunicaciones", "puente"}
    guri = next(i for i in inst if "Guri" in i["nombre"])
    assert abs(guri["lat"] - 7.77) < 0.05 and abs(guri["lon"] + 63.0) < 0.05
    for i in inst:
        assert 0 < i["lat"] < 13 and -74 < i["lon"] < -59, i["nombre"]  # dentro de Venezuela
        assert i["clase"] in catalogo.CLASES
        if i["clase"] == "puente":
            assert 0 < i["radio_km"] <= 20
    assert "OpenStreetMap" in datos["fuente"]


# ---------------------------------------------------------------- efectos
def test_sin_energia_los_radares_fijos_pierden_alcance(db_session):
    esc = _escenario(db_session)
    radar = _unidad(db_session, esc, nombre="Radar", bando="azul", clase="radar", deteccion_km=150)
    avion = _unidad(db_session, esc, nombre="Avion", bando="rojo", tipo="aerea", clase="caza", lat=1.0, lon=0.0)  # 111 km
    central = _infra(db_session, esc, "termoelectrica")
    ge = ge_mod.contexto(db_session, esc)
    assert vision.radio_efectivo(radar, avion, TerrenoFalso(), clima_mod.ClimaLocal(), ge) == 150
    central.fuerza = 0
    db_session.commit()
    ge = ge_mod.contexto(db_session, esc)
    assert ge.factor_energia("azul") == infra.RADAR_CON_RESPALDO
    assert vision.radio_efectivo(radar, avion, TerrenoFalso(), clima_mod.ClimaLocal(), ge) == 75
    assert not vision.detecta(radar, avion, TerrenoFalso(), clima_mod.ClimaLocal(), ge)
    assert ge.factor_energia("rojo") == 1.0  # el rojo no tiene centrales: no le afecta


def test_sin_refineria_los_depositos_reponen_menos_combustible(db_session):
    esc = _escenario(db_session)
    dep = _unidad(db_session, esc, nombre="Deposito", bando="azul", tipo="base", clase="deposito", velocidad_kmh=0,
                  stock_combustible=0, stock_municion=0)
    _infra(db_session, esc, "refineria", fuerza=0)
    avanzar_turno(db_session, esc, TerrenoFalso())
    db_session.refresh(dep)
    repone = catalogo.CLASES["deposito"].reposicion_turno
    assert dep.stock_municion == repone
    assert dep.stock_combustible == repone * infra.COMBUSTIBLE_RESERVA


def test_sin_centros_de_comunicaciones_las_ordenes_se_demoran():
    unidades = [SimpleNamespace(bando="azul", clase="centro_comunicaciones", tipo="base", fuerza=0.0, estado="activa")]
    assert infra.demora_extra_pct(unidades, "azul") == infra.DEMORA_SIN_COMUNICACIONES_PCT
    assert infra.demora_extra_pct(unidades, "rojo") == 0
    esc = SimpleNamespace(com_ordenes_pct=0)
    ge = ge_mod.Contexto()
    u = SimpleNamespace(bando="azul", lat=0, lon=0)
    assert orders.prob_demora(esc, u, ge) == 0
    assert orders.prob_demora(esc, u, ge, infra.demora_extra_pct(unidades, "azul")) == 0.30


def test_un_puente_cortado_no_deja_cruzar_el_rio():
    pesada = SimpleNamespace(tipo="terrestre", clase="blindado")
    sano = SimpleNamespace(bando="azul", clase="puente", tipo="base", fuerza=80.0, estado="activa", lat=0.0, lon=0.0,
                           radio_km=2.0, nombre="Puente", id=1)
    assert infra.cortes([sano]) == []
    assert movimiento.factor_terreno(pesada, "rio", [], 0.0, 0.0, via=1) == FACTOR_PUENTE
    roto = SimpleNamespace(**{**sano.__dict__, "fuerza": 30.0})
    cortes = infra.cortes([roto])
    assert movimiento.factor_terreno(pesada, "rio", cortes, 0.0, 0.0, via=1) == 0  # el blindado ya no cruza
    assert movimiento.factor_terreno(pesada, "rio", cortes, 0.1, 0.0, via=1) == FACTOR_PUENTE  # otro puente, a 11 km
    ligera = SimpleNamespace(tipo="terrestre", clase="infanteria")
    assert 0 < movimiento.factor_terreno(ligera, "rio", cortes, 0.0, 0.0, via=1) < FACTOR_PUENTE  # la infanteria vadea


def test_la_infraestructura_danada_se_avisa_a_su_bando():
    central = SimpleNamespace(id=1, bando="azul", clase="termoelectrica", tipo="base", fuerza=100.0, estado="activa",
                              lat=0, lon=0, radio_km=None, nombre="Planta Centro")
    puente = SimpleNamespace(id=2, bando="rojo", clase="puente", tipo="base", fuerza=100.0, estado="activa", lat=0,
                             lon=0, radio_km=1.0, nombre="Puente Angostura")
    antes = infra.estado([central, puente])
    central.fuerza, puente.fuerza = 40.0, 20.0
    avisos = infra.avisos(antes, infra.estado([central, puente]), [central, puente])
    assert ("azul", "Energía eléctrica: la capacidad cae al 40 %: radares fijos al 70 % de su alcance.") in avisos
    assert ("rojo", "Puente Angostura quedó cortado: ninguna unidad terrestre puede cruzar por él.") in avisos


def test_el_instructor_coloca_un_puente_y_su_estado_llega_al_bando(api):
    prof, base, *_ = _preparar(api)
    r = prof.post(f"{base}/unidades", json={"nombre": "Puente Orinoquia", "bando": "azul", "clase": "puente",
                                            "lat": 0.2, "lon": 0.2, "radio_km": 3.8})
    assert r.status_code == 200, r.text
    assert r.json()["radio_km"] == 3.8 and r.json()["personal_inicial"] == 0
    estado = api("alfa").get(base).json()
    puentes = next(f for f in estado["infraestructura"]["azul"] if f["categoria"] == "puente")
    assert puentes["capacidad_pct"] == 100 and puentes["instalaciones"][0]["nombre"] == "Puente Orinoquia"
    assert "rojo" not in estado["infraestructura"]  # cada bando ve solo la suya
    assert set(prof.get(base).json()["infraestructura"]) == {"azul", "rojo"}


# ---------------------------------------------------------------- personal
def test_dotacion_por_escalon_tripulacion_y_buque():
    cia = SimpleNamespace(tipo="terrestre", clase="infanteria", echelon="compania", personal=None, fuerza=60.0, estado="activa")
    assert personal.inicial(cia) == 120 and personal.actual(cia) == 72
    grupo = SimpleNamespace(tipo="aerea", clase="ataque", modelo="", aeronaves=4, echelon="", personal=None, fuerza=100.0, estado="activa")
    assert personal.inicial(grupo) == 8
    fragata = SimpleNamespace(tipo="naval", clase="fragata", echelon="", personal=None, fuerza=100.0, estado="destruida")
    assert personal.inicial(fragata) == 180 and personal.actual(fragata) == 0
    fijada = SimpleNamespace(tipo="terrestre", clase="infanteria", echelon="batallon", personal=640, fuerza=50.0, estado="activa")
    assert personal.inicial(fijada) == 640 and personal.actual(fijada) == 320
    dron = SimpleNamespace(tipo="aerea", clase="dron_ataque", modelo="", aeronaves=2, echelon="", personal=None, fuerza=100.0, estado="activa")
    assert personal.inicial(dron) == 0
    r = personal.resumen([SimpleNamespace(**{**x.__dict__, "bando": "azul"}) for x in (cia, fragata)], "azul")
    assert r["inicial"] == 300 and r["actual"] == 72 and r["bajas"] == 228


def test_el_personal_del_enemigo_no_se_ve(api):
    prof, base, a, r1, r2 = _preparar(api)
    r = prof.post(f"{base}/unidades", json={"nombre": "Bn", "bando": "azul", "clase": "infanteria", "echelon": "batallon",
                                            "lat": 0.01, "lon": 0.0, "personal": 640})
    assert r.json()["personal_inicial"] == 640
    vista = {u["id"]: u for u in api("bravo").get(base).json()["unidades"]}
    assert vista[a["id"]]["personal_inicial"] is None  # A esta a la vista del rojo, pero no su gente
    assert vista[r1["id"]]["personal_inicial"] == 120
    assert api("alfa").get(base).json()["personal"]["azul"]["inicial"] == 120 + 640


# ---------------------------------------------------------------- objetivos
def test_el_marcador_da_el_porcentaje_de_objetivos_cumplidos(api):
    prof, base, a, r1, r2 = _preparar(api)
    for i, punto in enumerate([(0.0, 0.0), (5.0, 5.0)]):
        prof.post(f"{base}/objetivos", json={"bando": "azul", "tipo": "ocupar", "nombre": f"Zona {i}", "puntos": 10,
                                             "lat": punto[0], "lon": punto[1], "radio_km": 3, "turnos_requeridos": 1})
    prof.post(f"{base}/avanzar_turno")
    m = prof.get(base).json()["marcador"]["azul"]
    assert (m["asignados"], m["cumplidos"], m["cumplidos_pct"]) == (2, 1, 50.0)
    assert prof.get(base).json()["marcador"]["rojo"]["cumplidos_pct"] is None


# ---------------------------------------------------------------- cuadro radar y aviso automatico
def test_el_cuadro_radar_muestra_lo_que_ve_cada_sensor_y_avisa_los_contactos_nuevos(db_session):
    esc = _escenario(db_session)
    _unidad(db_session, esc, nombre="Radar Norte", bando="azul", clase="radar", deteccion_km=150)
    _unidad(db_session, esc, nombre="Infanteria", bando="azul", deteccion_km=8)
    _unidad(db_session, esc, nombre="Caza R", bando="rojo", tipo="aerea", clase="caza", lat=0.5, lon=0.5)
    cuadro = vision.cuadro_sensores(db_session.query(Unidad).all(), "azul", TerrenoFalso())
    assert [s["nombre"] for s in cuadro] == ["Radar Norte"]  # la infanteria no es un sensor
    c = cuadro[0]["contactos"][0]
    assert c["nombre"] == "Caza R" and 75 < c["distancia_km"] < 82 and c["rumbo"] == 45 and c["perfil"] == "medio"
    contactos.actualizar_contactos(db_session, esc, TerrenoFalso())
    db_session.commit()
    avisos = db_session.query(Evento).filter(Evento.tipo == "radar").all()
    assert len(avisos) == 1 and avisos[0].bando_destino == "azul"
    assert avisos[0].descripcion.startswith("Radar Norte informa 1 contacto(s) nuevo(s): caza a cota media a 79 km, rumbo 045°")
    esc.turno_actual += 1
    contactos.actualizar_contactos(db_session, esc, TerrenoFalso())
    db_session.commit()
    assert db_session.query(Evento).filter(Evento.tipo == "radar").count() == 1  # ya lo tenia a la vista: no repite


def test_el_estado_lleva_el_cuadro_radar_de_cada_bando(api):
    prof, base, a, r1, r2 = _preparar(api)
    prof.post(f"{base}/unidades", json={"nombre": "Radar", "bando": "azul", "clase": "radar", "lat": 0.0, "lon": 0.1})
    prof.post(f"{base}/unidades", json={"nombre": "Caza", "bando": "rojo", "clase": "caza", "lat": 0.6, "lon": 0.1})
    azul = api("alfa").get(base).json()["sensores"]
    assert [s["nombre"] for s in azul] == ["Radar"] and azul[0]["contactos"][0]["nombre"] == "Caza"
    assert api("bravo").get(base).json()["sensores"] == []  # el rojo no tiene sensores


# ---------------------------------------------------------------- tiempo de recorrido
def test_tiempo_de_todo_el_recorrido_y_hora_de_llegada(api):
    prof, base, a, r1, r2 = _preparar(api)
    t = movimiento.tiempo_recorrido(SimpleNamespace(tipo="terrestre", clase="infanteria", velocidad_kmh=30.0, lat=0.0, lon=0.0,
                                                    autonomia_km=300.0, combustible=100.0, perfil_vuelo=None),
                                    [[0.539, 0.0]], TerrenoFalso())
    assert 59 < t["km"] < 61 and 1.95 < t["horas"] < 2.05 and t["turnos"] == 2 and not t["bloqueo"]
    r = api("alfa").post(f"{base}/ordenes/previsualizar", json={"unidad_id": a["id"], "waypoints": [[0.539, 0.0]]})
    assert r.status_code == 200, r.text
    tiempo = r.json()["tiempo"]
    assert tiempo["turnos"] == 2 and tiempo["llegada"] == "08:00"  # sale a las 06:00 del turno 1


def test_el_tiempo_avisa_un_rio_sin_puente():
    terreno = TerrenoFalso(lambda lat, lon: "rio" if 0.1 < lat < 0.12 else "llano")
    t = movimiento.tiempo_recorrido(SimpleNamespace(tipo="terrestre", clase="blindado", velocidad_kmh=45.0, lat=0.0, lon=0.0,
                                                    autonomia_km=250.0, combustible=100.0, perfil_vuelo=None),
                                    [[0.3, 0.0]], terreno)
    assert "Río sin puente" in t["bloqueo"] and t["km"] < 13


def test_logistica_reponer_con_factor():
    b = SimpleNamespace(clase="deposito", tipo="base", stock_combustible=0.0, stock_municion=0.0)
    logistica.reponer(b, 0.5)
    r = catalogo.CLASES["deposito"].reposicion_turno
    assert b.stock_combustible == r * 0.5 and b.stock_municion == r


def test_los_ejercicios_contra_la_ia_traen_infraestructura_con_objetivos(db_session):
    from app.engine import plantillas
    from app.models.objetivo import Objetivo

    esc = plantillas.crear_desde_plantilla(db_session, "defensa_aerea_central")
    infra_u = {u.nombre: u for u in db_session.query(Unidad).filter(Unidad.escenario_id == esc.id) if infra.es_infraestructura(u)}
    assert set(infra_u) == {"Planta Centro (Morón)", "Refinería El Palito"}
    objetivos = db_session.query(Objetivo).filter(Objetivo.escenario_id == esc.id).all()
    assert any(o.bando == "rojo" and o.tipo == "destruir" and o.unidad_id == infra_u["Planta Centro (Morón)"].id for o in objetivos)
    esc2 = plantillas.crear_desde_plantilla(db_session, "defensa_costa_oriental")
    assert any(u.clase == "refineria" for u in db_session.query(Unidad).filter(Unidad.escenario_id == esc2.id))
