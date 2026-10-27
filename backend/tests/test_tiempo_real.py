"""SIETE en tiempo real: reloj, movimiento continuo, ordenes en vivo, orbitas, combustible, combate y defensa aerea."""

import asyncio
import json

import pytest

from app import reloj
from app.engine import aeronaves, catalogo, geo, orders, tiempo_real
from app.models.aar import Combate
from app.models.evento import Evento
from app.models.orden import Orden
from app.models.unidad import Unidad
from tests.conftest import TerrenoFalso
from tests.test_api import _preparar
from tests.test_orders import _escenario, _unidad

CAZA = dict(tipo="aerea", clase="caza", velocidad_kmh=900, alcance_km=80, deteccion_km=60, autonomia_km=1800)
PASO = tiempo_real.PASO_MAX_S


@pytest.fixture(autouse=True)
def mundo_limpio():
    tiempo_real.MUNDOS.clear()
    reloj._pendiente.clear()
    reloj._ultimo_estado.clear()
    yield
    tiempo_real.MUNDOS.clear()


def _orden(db, esc, u, tipo, objetivo=None, waypoints=None, detalle=""):
    o = Orden(escenario_id=esc.id, unidad_id=u.id, tipo=tipo, objetivo_unidad_id=objetivo.id if objetivo else None,
              waypoints_json=json.dumps(waypoints or []), detalle=detalle, turno_emitida=esc.turno_actual)
    db.add(o)
    db.flush()
    tiempo_real.aplicar_orden(db, esc, o, u)
    db.commit()
    return o


def _correr(db, esc, segundos):
    tiempo_real.paso(db, esc, segundos, TerrenoFalso())
    db.commit()


# ---------------------------------------------------------------------------------------------- reloj y movimiento
def test_la_unidad_avanza_de_a_poco_y_la_hora_pasa(db_session):
    esc = _escenario(db_session)
    u = _unidad(db_session, esc, velocidad_kmh=30.0)
    o = _orden(db_session, esc, u, "mover", waypoints=[[1.0, 0.0]])
    assert o.estado == "en_ejecucion" and u.orden_id == o.id
    _correr(db_session, esc, 600)  # 10 minutos: 5 km
    assert geo.distancia_km(0, 0, u.lat, u.lon) == pytest.approx(5.0, abs=0.3)
    assert u.rumbo == pytest.approx(0.0, abs=1.0) and esc.turno_actual == 1
    _correr(db_session, esc, 3000)  # se cumple la hora: 30 km y empieza la hora 2
    assert geo.distancia_km(0, 0, u.lat, u.lon) == pytest.approx(30.0, abs=0.5)
    assert esc.turno_actual == 2 and o.estado == "en_ejecucion"
    _correr(db_session, esc, 3 * 3600)  # 111 km en total: llega
    assert (u.lat, u.lon) == pytest.approx((1.0, 0.0)) and o.estado == "resuelta" and "Llegó" in o.resultado
    assert u.orden_id is None and u.ruta_json is None


def test_la_ruta_pasa_por_cada_punto_y_guarda_lo_que_falta(db_session):
    esc = _escenario(db_session)
    u = _unidad(db_session, esc, velocidad_kmh=60.0)
    _orden(db_session, esc, u, "mover", waypoints=[[0.1, 0.0], [0.1, 0.5]])
    _correr(db_session, esc, 900)  # 15 km: paso el primer punto (11 km) y gira al este
    assert u.ruta == [[0.1, 0.5]] and u.lat == pytest.approx(0.1) and u.lon > 0.0
    assert u.rumbo == pytest.approx(90.0, abs=1.0)


def test_una_orden_nueva_reemplaza_al_instante_y_detener_la_para(db_session, api):
    prof, base, a, r1, r2 = _preparar(api)
    alfa = api("alfa")
    r = alfa.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "mover", "waypoints": [[0.5, 0.0]]})
    assert r.status_code == 200 and r.json()["estado"] == "en_ejecucion"
    r = alfa.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "mover", "waypoints": [[0.0, 0.5]]})
    nueva = r.json()
    ordenes = {o["id"]: o for o in alfa.get(f"{base}/ordenes").json()}
    assert [o["estado"] for o in ordenes.values()] == ["cancelada", "en_ejecucion"]
    assert "Reemplazada" in next(iter(ordenes.values()))["resultado"]
    u = next(x for x in alfa.get(base).json()["unidades"] if x["id"] == a["id"])
    assert u["ruta"] == [[0.0, 0.5]] and u["orden_id"] == nueva["id"]
    assert alfa.delete(f"{base}/ordenes/{nueva['id']}").status_code == 200
    u = next(x for x in alfa.get(base).json()["unidades"] if x["id"] == a["id"])
    assert u["ruta"] == [] and u["orden_id"] is None
    assert alfa.delete(f"{base}/ordenes/{nueva['id']}").status_code == 400  # ya termino


def test_el_director_maneja_el_reloj_y_sin_turnos(api):
    prof, base, a, *_ = _preparar(api)
    e = prof.get(base).json()["escenario"]
    assert e["estado"] == "pausado" and e["velocidad"] == 60 and e["sim_segundos"] == 0
    assert prof.post(f"{base}/reloj", json={"velocidad": 7}).status_code == 400
    r = prof.post(f"{base}/reloj", json={"velocidad": 10, "estado": "activo"})
    assert r.status_code == 200 and r.json()["escenario"]["estado"] == "activo" and r.json()["escenario"]["velocidad"] == 10
    assert api("alfa").post(f"{base}/reloj", json={"estado": "pausado"}).status_code == 403
    assert api("alfa").post(f"{base}/listo", json={"listo": True}).status_code == 400
    # adelantar el reloj: dos horas de una vez
    r = prof.post(f"{base}/avanzar_turno?n=2")
    assert r.status_code == 200 and r.json()["escenario"]["turno_actual"] == 3
    assert r.json()["escenario"]["sim_segundos"] == pytest.approx(7200.0)


def test_el_reloj_avanza_solo_los_escenarios_activos_y_abiertos(db_session, monkeypatch):
    esc = _escenario(db_session)
    u = _unidad(db_session, esc, velocidad_kmh=36.0)
    _orden(db_session, esc, u, "mover", waypoints=[[1.0, 0.0]])
    enviados = []

    async def difundir(db, e):
        enviados.append(("posiciones", e.id))

    async def estado(db, e):
        enviados.append(("estado", e.id))

    monkeypatch.setattr(reloj.manager, "escenarios_con_conexiones", lambda: [esc.id])
    monkeypatch.setattr(reloj.manager, "difundir_posiciones", difundir)
    monkeypatch.setattr(reloj.manager, "difundir_estado", estado)
    monkeypatch.setattr(tiempo_real, "get_terreno", lambda: TerrenoFalso())
    esc.estado = "pausado"
    db_session.commit()
    assert asyncio.run(reloj.vuelta(db_session, 1.0)) == []
    assert esc.sim_segundos == 0 and enviados == [("posiciones", esc.id)]
    esc.estado, esc.velocidad = "activo", 10
    db_session.commit()
    assert asyncio.run(reloj.vuelta(db_session, 1.0)) == [esc.id]
    assert esc.sim_segundos == pytest.approx(10.0) and geo.distancia_km(0, 0, u.lat, u.lon) == pytest.approx(0.1, abs=0.01)


def test_las_posiciones_respetan_la_niebla(db_session):
    esc = _escenario(db_session)
    a = _unidad(db_session, esc, nombre="A", deteccion_km=10)
    cerca = _unidad(db_session, esc, nombre="R1", bando="rojo", lat=0.045, deteccion_km=10)
    lejos = _unidad(db_session, esc, nombre="R2", bando="rojo", lat=1.8, deteccion_km=10)
    _correr(db_session, esc, 1)
    azul = {f[0]: f for f in tiempo_real.posiciones_para(db_session, esc, "azul")["unidades"]}
    assert set(azul) == {a.id, cerca.id}
    assert azul[a.id][5] == 100 and azul[cerca.id][5] is None  # del enemigo no se ve la fuerza
    todas = tiempo_real.posiciones_para(db_session, esc, "instructor")
    assert {f[0] for f in todas["unidades"]} == {a.id, cerca.id, lejos.id} and todas["reloj"]["hora"] == "06:00"


# ---------------------------------------------------------------------------------------------- aeronaves
def test_la_patrulla_vuela_orbita_y_gasta_combustible(db_session):
    esc = _escenario(db_session)
    c = _unidad(db_session, esc, nombre="Caza", **CAZA)
    _orden(db_session, esc, c, "patrullar", waypoints=[[0.5, 0.0]])
    _correr(db_session, esc, 600)  # 150 km: llega (55 km) y se queda orbitando
    centro = geo.distancia_km(c.lat, c.lon, 0.5, 0.0)
    assert centro == pytest.approx(tiempo_real.RADIO_ORBITA_KM, abs=0.5) and c.mision == "patrulla"
    antes = c.combustible
    _correr(db_session, esc, 1800)
    assert geo.distancia_km(c.lat, c.lon, 0.5, 0.0) == pytest.approx(tiempo_real.RADIO_ORBITA_KM, abs=0.5)
    assert antes - c.combustible == pytest.approx(aeronaves.COMBUSTIBLE_LOITER / 2, rel=0.05)


def test_la_aeronave_en_vuelo_se_desvia_al_recibir_otra_orden(db_session):
    esc = _escenario(db_session)
    c = _unidad(db_session, esc, nombre="Caza", **CAZA)
    _orden(db_session, esc, c, "mover", waypoints=[[2.0, 0.0]])
    _correr(db_session, esc, 120)
    norte = c.lat
    assert norte > 0.2 and c.rumbo == pytest.approx(0.0, abs=1)
    _orden(db_session, esc, c, "mover", waypoints=[[c.lat, 1.0]])  # se desvia al este en el acto
    _correr(db_session, esc, 120)
    assert c.lat == pytest.approx(norte, abs=0.01) and c.lon > 0.2 and c.rumbo == pytest.approx(90.0, abs=1)


def test_al_llegar_queda_en_espera_y_detenida_orbita_donde_esta(db_session):
    esc = _escenario(db_session)
    c = _unidad(db_session, esc, nombre="Caza", **CAZA)
    o = _orden(db_session, esc, c, "mover", waypoints=[[0.3, 0.0]])
    _correr(db_session, esc, 300)
    assert o.estado == "resuelta" and c.mision == "espera"
    _correr(db_session, esc, 600)
    assert geo.distancia_km(c.lat, c.lon, c.mision_lat, c.mision_lon) == pytest.approx(tiempo_real.RADIO_ORBITA_KM, abs=0.5)


def test_combustible_critico_regresa_aterriza_y_rearma(db_session):
    esc = _escenario(db_session)
    base = _unidad(db_session, esc, nombre="BA", tipo="base", clase="base_aerea", velocidad_kmh=0, alcance_km=25)
    c = _unidad(db_session, esc, nombre="Caza", lat=0.5, combustible=27.0, **CAZA)
    _orden(db_session, esc, c, "patrullar", waypoints=[[0.5, 0.0]])
    _correr(db_session, esc, 1800)  # en orbita baja de 25 %: regresa solo
    rtb = db_session.query(Orden).filter(Orden.detalle == "combustible critico").one()
    assert rtb.estado in ("en_ejecucion", "resuelta")
    _correr(db_session, esc, 900)
    db_session.refresh(rtb)
    assert c.en_tierra and c.base_id == base.id and rtb.estado == "resuelta" and "Aterrizó" in rtb.resultado
    assert c.espera_restante == aeronaves.TIEMPO_REARME_TURNOS and c.espera_hasta is not None
    _correr(db_session, esc, 2 * 3600)
    assert c.espera_restante == 0 and c.espera_hasta is None and c.combustible > 27.0  # reabastecio en la base


def test_el_despegue_crea_el_grupo_en_el_acto(db_session):
    esc = _escenario(db_session)
    base = _unidad(db_session, esc, nombre="BA", tipo="base", clase="base_aerea", velocidad_kmh=0, alcance_km=25)
    o = _orden(db_session, esc, base, "despegar", detalle=aeronaves.codificar("f16", 2, "Halcon"))
    assert o.estado == "resuelta"
    g = db_session.query(Unidad).filter(Unidad.nombre == "Halcon").one()
    assert g.mision == "espera" and (g.mision_lat, g.mision_lon) == (base.lat, base.lon) and not g.en_tierra
    _correr(db_session, esc, 600)
    assert geo.distancia_km(g.lat, g.lon, base.lat, base.lon) == pytest.approx(tiempo_real.RADIO_ORBITA_KM, abs=0.5)


def test_la_patrulla_intercepta_sola(db_session):
    esc = _escenario(db_session)
    c = _unidad(db_session, esc, nombre="Caza", **CAZA)
    _orden(db_session, esc, c, "patrullar", waypoints=[[0.0, 0.0]])
    intruso = _unidad(db_session, esc, nombre="Intruso", bando="rojo", lat=0.5, lon=0.0, **CAZA)
    _correr(db_session, esc, 30)
    assert intruso.fuerza < 100 and c.recarga_hasta is not None
    assert db_session.query(Combate).filter(Combate.defensor_id == intruso.id).count() == 1
    fuerza = intruso.fuerza
    _correr(db_session, esc, 60)  # todavia recargando: no vuelve a tirar
    assert intruso.fuerza == fuerza


# ---------------------------------------------------------------------------------------------- combate
def test_el_ataque_terrestre_se_acerca_y_el_fuego_es_continuo(db_session):
    esc = _escenario(db_session)
    a = _unidad(db_session, esc, nombre="A", alcance_km=5, deteccion_km=30, velocidad_kmh=30)
    r = _unidad(db_session, esc, nombre="R", bando="rojo", lat=0.15, alcance_km=5, deteccion_km=30, velocidad_kmh=0)
    o = _orden(db_session, esc, a, "atacar", objetivo=r)
    _correr(db_session, esc, 900)  # 17 km a 30 km/h: todavia se acerca, sin tirar
    assert 0 < a.lat < 0.1 and r.fuerza == 100
    _correr(db_session, esc, 1200)  # quedo al alcance (4 km) y empezo a tirar
    assert geo.distancia_km(a.lat, a.lon, r.lat, r.lon) <= 5.0
    perdida_1 = 100 - r.fuerza
    _correr(db_session, esc, 1800)
    perdida_2 = 100 - r.fuerza
    assert 0 < perdida_1 < perdida_2 and o.estado == "en_ejecucion" and a.municion < 100
    _correr(db_session, esc, 1)
    combates = db_session.query(Combate).filter(Combate.defensor_id == r.id).all()
    assert combates and "fuego continuo" in combates[0].efectos


def test_el_ataque_aereo_es_una_pasada_y_queda_en_espera(db_session):
    esc = _escenario(db_session)
    c = _unidad(db_session, esc, nombre="Caza", **CAZA)
    r = _unidad(db_session, esc, nombre="R", bando="rojo", lat=1.2, deteccion_km=5)
    _unidad(db_session, esc, nombre="Reco", lat=1.1, deteccion_km=20)  # alguien propio ve al blanco
    o = _orden(db_session, esc, c, "atacar", objetivo=r)
    _correr(db_session, esc, 600)
    assert r.fuerza < 100 and o.estado == "resuelta" and "Pasada" in o.resultado and c.mision == "espera"
    assert c.municion < 100


def test_el_misil_persigue_e_impacta(db_session):
    esc = _escenario(db_session)
    lanzador = _unidad(db_session, esc, nombre="Lanzador", clase="lanzador_misiles", deteccion_km=5)
    r = _unidad(db_session, esc, nombre="R", bando="rojo", lat=0.5, deteccion_km=5)
    _unidad(db_session, esc, nombre="Reco", lat=0.45, deteccion_km=20)
    o = _orden(db_session, esc, lanzador, "lanzar", objetivo=r, detalle=json.dumps({"misiles": 2}))
    assert o.estado == "resuelta"
    misil = db_session.query(Unidad).filter(Unidad.blanco_id == r.id).one()
    _correr(db_session, esc, 600)
    assert misil.estado == "destruida" and r.fuerza < 100


def test_el_lanzador_recarga_entre_salvas_y_la_ia_no_tira_sin_parar(db_session):
    esc = _escenario(db_session)
    esc.ia_rojo = True
    db_session.commit()
    _unidad(db_session, esc, nombre="Blanco", bando="azul", lat=0.5, deteccion_km=5)
    lanzador = _unidad(db_session, esc, nombre="Lanzador", bando="rojo", clase="lanzador_misiles", deteccion_km=80)
    _correr(db_session, esc, 900)  # tres decisiones de la IA en 15 minutos: una sola salva
    salvas = db_session.query(Unidad).filter(Unidad.escenario_id == esc.id, Unidad.blanco_id.isnot(None)).count()
    assert salvas == 1 and lanzador.recarga_hasta == pytest.approx(tiempo_real.RECARGA_LANZADOR_S, abs=PASO)


def test_la_defensa_aerea_reacciona_lanza_y_evalua(db_session):
    esc = _escenario(db_session)
    modelo = "pechora_2m"
    bat = _unidad(db_session, esc, nombre="Bateria", clase=catalogo.MODELOS[modelo].clase, modelo=modelo,
                  deteccion_km=160, alcance_km=32, velocidad_kmh=0)
    avion = _unidad(db_session, esc, nombre="Bandido", bando="rojo", lat=0.4, lon=0.0, perfil_vuelo="medio", **CAZA)
    _orden(db_session, esc, avion, "mover", waypoints=[[-1.0, 0.0]])  # viene de frente hacia la bateria
    _correr(db_session, esc, 45)  # 44 km -> 33 km: todavia fuera de alcance
    assert not tiempo_real.mundo_de(esc.id).da.get(bat.id)
    _correr(db_session, esc, 15)  # entra al alcance: empieza la reaccion, todavia no lanza
    enf = tiempo_real.mundo_de(esc.id).da[bat.id]
    assert enf and enf[0]["fase"] == "reaccion" and enf[0]["aspecto"] == "de frente" and avion.fuerza == 100
    _correr(db_session, esc, 60)  # termina de reaccionar, lanza y el misil llega
    textos = [e.descripcion for e in db_session.query(Evento).filter(Evento.bando_destino == "azul")]
    assert any("lanzó" in t for t in textos)
    assert avion.fuerza < 100
    assert db_session.query(Combate).filter(Combate.atacante_id == bat.id).count() >= 1


def test_la_unidad_varada_busca_otro_camino(db_session):
    # un rio de este a oeste en lat 0.1, con un puente de carretera solo en lon 0.3
    def clase(lat, lon):
        return "rio" if abs(lat - 0.1) < 0.004 else "llano"

    class ConPuente(TerrenoFalso):
        def via(self, lat, lon):
            return 2 if abs(lon - 0.3) < 0.01 else 0

    terreno = ConPuente(clase)
    esc = _escenario(db_session)
    u = _unidad(db_session, esc, nombre="Blindados", clase="blindado", velocidad_kmh=40.0)
    o = _orden(db_session, esc, u, "mover", waypoints=[[0.2, 0.0]])  # en linea recta: el rio la detiene
    for _ in range(40):
        tiempo_real.paso(db_session, esc, 900, terreno)
    db_session.commit()
    assert o.estado == "resuelta" and "Llegó" in o.resultado, o.resultado
    textos = [e.descripcion for e in db_session.query(Evento).filter(Evento.escenario_id == esc.id)]
    assert any("otro camino" in t for t in textos)


def test_el_informe_a_mitad_de_hora_agrupa_el_fuego_continuo(db_session):
    from app.engine import aar

    esc = _escenario(db_session)
    a = _unidad(db_session, esc, nombre="A", alcance_km=10, deteccion_km=30)
    r = _unidad(db_session, esc, nombre="R", bando="rojo", lat=0.05, deteccion_km=30, velocidad_kmh=0)
    _orden(db_session, esc, a, "atacar", objetivo=r)
    _correr(db_session, esc, 1800)  # media hora de fuego: seis registros de 5 minutos, la hora sigue abierta
    assert db_session.query(Combate).count() == 6
    inf = aar.construir_informe(db_session, esc)
    hora = next(t for t in inf["turnos"] if t["turno"] == 1)
    (c,) = hora["combates"]
    assert c["efectos"].startswith("fuego continuo durante 30 min") and hora["en_curso"] is True
    assert c["perdida_defensor"] == pytest.approx(100 - r.fuerza, abs=0.3)
    assert inf["resumen"]["azul"]["combates_iniciados"] == 1


# ---------------------------------------------------------------------------------------------- logistica continua
def test_el_deposito_reabastece_de_a_poco_y_repone_existencias(db_session):
    esc = _escenario(db_session)
    dep = _unidad(db_session, esc, nombre="Deposito", tipo="base", clase="deposito", velocidad_kmh=0, alcance_km=20)
    u = _unidad(db_session, esc, nombre="Infanteria", lat=0.05, combustible=50.0, municion=50.0)
    _correr(db_session, esc, 1800)  # media hora: la mitad de lo que da en una hora (+50 por hora)
    assert u.combustible == pytest.approx(75.0, abs=1.0) and u.municion == pytest.approx(75.0, abs=1.0)
    # el deposito dio 25 de cada uno y repuso la mitad de su reposicion horaria (150)
    assert dep.stock_combustible == pytest.approx(1000.0 - 25.0 + 75.0, abs=2.0)


def test_el_registro_logistico_se_escribe_por_hora_y_por_causa(db_session):
    from app.models.aar import RegistroLogistico

    esc = _escenario(db_session)
    u = _unidad(db_session, esc, nombre="Blindados", velocidad_kmh=40.0, autonomia_km=400.0)
    _orden(db_session, esc, u, "mover", waypoints=[[2.0, 0.0]])
    _correr(db_session, esc, 1800)
    assert db_session.query(RegistroLogistico).count() == 0  # se acumula durante la hora
    _correr(db_session, esc, 1800)
    (fila,) = db_session.query(RegistroLogistico).all()
    assert (fila.turno, fila.variable, fila.causa, fila.antes) == (1, "combustible", "movimiento", 100.0)
    assert fila.despues == pytest.approx(100.0 - 40.0 / 400.0 * 100.0, abs=0.5) == pytest.approx(u.combustible, abs=0.01)


def test_el_avion_cisterna_reabastece_en_vuelo_por_tandas(db_session):
    esc = _escenario(db_session)
    kc = _unidad(db_session, esc, nombre="Cisterna", tipo="aerea", clase="cisterna", modelo="kc135", velocidad_kmh=800,
                 autonomia_km=9000, deteccion_km=30, carga=100.0, mision="espera", mision_lat=0.0, mision_lon=0.0)
    caza = _unidad(db_session, esc, nombre="Caza", combustible=40.0, mision="espera", mision_lat=0.0, mision_lon=0.0, **CAZA)
    _correr(db_session, esc, 600)  # todavia no se cumple la primera tanda de 15 minutos
    assert caza.combustible < 40.0
    _correr(db_session, esc, 600)
    assert caza.combustible > 60.0 and kc.carga < 100.0
    assert any("reabasteció en vuelo" in e.descripcion for e in db_session.query(Evento))


# ---------------------------------------------------------------------------------------------- guerra electronica
def test_la_interferencia_degrada_al_enemigo_mientras_dura_y_termina_si_el_emisor_cae(db_session):
    from app.engine import guerra_electronica as ge_mod
    from app.models.interferencia import Interferencia

    esc = _escenario(db_session)
    ge = _unidad(db_session, esc, nombre="GE", clase="guerra_electronica", alcance_km=60, deteccion_km=10)
    radar = _unidad(db_session, esc, nombre="Radar rojo", bando="rojo", clase="radar", lat=0.3, deteccion_km=150)
    o = _orden(db_session, esc, ge, "interferir", waypoints=[[0.3, 0.0]])
    assert o.estado == "en_ejecucion"
    contexto = ge_mod.contexto(db_session, esc)
    assert contexto.interferido(radar) and contexto.emite(ge)
    _correr(db_session, esc, 3 * 3600)
    assert ge_mod.contexto(db_session, esc).interferido(radar)  # sin "turnos": dura lo que dure la orden
    ge.estado, ge.fuerza = "destruida", 0.0
    db_session.commit()
    _correr(db_session, esc, 30)
    assert not ge_mod.contexto(db_session, esc).interferido(radar)
    z = db_session.query(Interferencia).one()
    assert z.inicio_seg == 0.0 and z.fin_seg == pytest.approx(3 * 3600 + 15, abs=16)


def test_la_mision_de_guerra_electronica_interfiere_mientras_orbita(db_session):
    from app.engine import guerra_electronica as ge_mod
    from app.models.mision import Mision

    esc = _escenario(db_session)
    base = _unidad(db_session, esc, nombre="BA", tipo="base", clase="base_aerea", velocidad_kmh=0, alcance_km=25)
    avion = _unidad(db_session, esc, nombre="GE aereo", tipo="aerea", clase="avion_ge", velocidad_kmh=700,
                    alcance_km=150, deteccion_km=60, autonomia_km=3000)
    radar = _unidad(db_session, esc, nombre="Radar rojo", bando="rojo", clase="radar", lat=1.0, deteccion_km=150)
    db_session.add(Mision(escenario_id=esc.id, bando="azul", rol="GE", estado="programada", unidad_id=avion.id,
                          turno_despegue=1, creada_turno=1, puntos_json=json.dumps([
                              {"tipo": "orbita", "lat": 0.5, "lon": 0.0, "turnos": 1, "centro": [1.0, 0.0]},
                              {"tipo": "aterrizaje", "lat": 0.0, "lon": 0.0, "base_id": base.id}])))
    db_session.commit()
    _correr(db_session, esc, 600)  # 55 km a 700 km/h: ya orbita e interfiere sobre el radar
    assert ge_mod.contexto(db_session, esc).interferido(radar)
    _correr(db_session, esc, 3600)  # termina la orbita: deja de interferir
    assert not ge_mod.contexto(db_session, esc).interferido(radar)


def test_las_ordenes_pueden_llegar_demoradas_y_la_unidad_sigue_con_la_anterior(db_session):
    esc = _escenario(db_session)
    esc.com_ordenes_pct = 100  # todas las ordenes se demoran
    db_session.commit()
    u = _unidad(db_session, esc, nombre="A", velocidad_kmh=30.0)
    primera = Orden(escenario_id=esc.id, unidad_id=u.id, tipo="mover", waypoints_json="[[0.5, 0.0]]",
                    turno_emitida=1)
    db_session.add(primera)
    db_session.flush()
    tiempo_real.aplicar_orden(db_session, esc, primera, u)
    db_session.commit()
    demora = tiempo_real.demora_de_orden(db_session, esc, u, "mover")
    assert tiempo_real.DEMORA_MIN_S <= demora <= tiempo_real.DEMORA_MAX_S
    assert tiempo_real.demora_de_orden(db_session, esc, u, "despegar") == 0.0
    nueva = Orden(escenario_id=esc.id, unidad_id=u.id, tipo="mover", waypoints_json="[[0.0, 0.5]]", turno_emitida=1,
                  estado="pendiente", emitida_seg=0.0, llega_seg=demora)
    db_session.add(nueva)
    db_session.commit()
    _correr(db_session, esc, demora - 60)
    assert primera.estado == "en_ejecucion" and u.lat > 0 and u.lon == 0.0  # sigue al norte, con la orden anterior
    _correr(db_session, esc, 120)
    assert primera.estado == "cancelada" and nueva.estado == "en_ejecucion" and u.ruta == [[0.0, 0.5]]


def test_api_la_orden_demorada_queda_pendiente_y_avisa_cuando_llega(api):
    prof, base, a, r1, r2 = _preparar(api)
    alfa = api("alfa")
    assert alfa.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "mover", "waypoints": [[0.5, 0.0]]}).json()["estado"] == "en_ejecucion"
    assert prof.patch(f"{base}/config", json={"com_ordenes_pct": 100}).status_code == 200
    r = alfa.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "mover", "waypoints": [[0.0, 0.5]]})
    o = r.json()
    assert r.status_code == 200 and o["estado"] == "pendiente" and o["llega_seg"] > 0 and "llegará" in o["resultado"]
    estados = [x["estado"] for x in alfa.get(f"{base}/ordenes").json()]
    assert estados == ["en_ejecucion", "pendiente"]  # la unidad sigue con la anterior
    prof.post(f"{base}/avanzar_turno")
    estados = [x["estado"] for x in alfa.get(f"{base}/ordenes").json()]
    assert estados == ["cancelada", "en_ejecucion"]
    assert any("estaba demorada" in e["descripcion"] for e in alfa.get(base).json()["eventos"])


# ---------------------------------------------------------------------------------------------- obras, transporte, apoyo
def test_los_ingenieros_tienden_el_vado_al_cumplirse_el_tiempo_de_obra(db_session):
    from app.models.obra import Obra

    esc = _escenario(db_session)
    ing = _unidad(db_session, esc, nombre="Ing", clase="ingenieros", lat=0.098, alcance_km=3)
    o = _orden(db_session, esc, ing, "construir", waypoints=[[0.105, 0.0]], detalle="vado")
    _correr(db_session, esc, 1500)
    assert o.estado == "en_ejecucion" and db_session.query(Obra).count() == 0  # 25 de 30 minutos
    _correr(db_session, esc, 600)
    (obra,) = db_session.query(Obra).all()
    assert o.estado == "resuelta" and obra.tipo == "vado" and obra.expira_turno == 1 + 4 and ing.municion == 70.0


def test_si_los_ingenieros_se_van_la_obra_queda_sin_terminar(db_session):
    from app.models.obra import Obra

    esc = _escenario(db_session)
    ing = _unidad(db_session, esc, nombre="Ing", clase="ingenieros", lat=0.098, alcance_km=3)
    o = _orden(db_session, esc, ing, "construir", waypoints=[[0.105, 0.0]], detalle="puente")
    _correr(db_session, esc, 600)
    ing.lat = 0.2  # el instructor la movio lejos
    db_session.commit()
    _correr(db_session, esc, 3600)
    assert o.estado == "cancelada" and db_session.query(Obra).count() == 0


def test_embarca_navega_y_desembarca_en_la_costa(db_session):
    from tests.test_transporte import MAR_SUR

    esc = _escenario(db_session)
    lst = _unidad(db_session, esc, nombre="LST", tipo="naval", clase="buque_desembarco", velocidad_kmh=35, lat=-0.01)
    inf = _unidad(db_session, esc, nombre="Infanteria", lat=0.0)
    o = Orden(escenario_id=esc.id, unidad_id=inf.id, tipo="embarcar", objetivo_unidad_id=lst.id, turno_emitida=1)
    db_session.add(o)
    db_session.flush()
    tiempo_real.aplicar_orden(db_session, esc, o, inf)
    db_session.commit()
    tiempo_real.paso(db_session, esc, 660, MAR_SUR)
    db_session.commit()
    assert o.estado == "resuelta" and inf.transporte_id == lst.id
    d = Orden(escenario_id=esc.id, unidad_id=lst.id, tipo="desembarcar", turno_emitida=1,
              waypoints_json=json.dumps([[-0.01, 0.5], [0.0, 0.5]]))  # navega al este y baja en la costa
    db_session.add(d)
    db_session.flush()
    tiempo_real.aplicar_orden(db_session, esc, d, lst)
    db_session.commit()
    for _ in range(8):
        tiempo_real.paso(db_session, esc, 900, MAR_SUR)
    db_session.commit()
    assert d.estado == "resuelta" and inf.transporte_id is None and inf.lon == pytest.approx(0.5, abs=0.01)


def test_el_apoyo_refuerza_el_combate_y_gasta_municion(db_session):
    def combate(con_apoyo: bool):
        tiempo_real.MUNDOS.clear()
        esc = _escenario(db_session)
        a = _unidad(db_session, esc, nombre="A", alcance_km=10, deteccion_km=30)
        r = _unidad(db_session, esc, nombre="R", bando="rojo", lat=0.05, deteccion_km=30, velocidad_kmh=0)
        art = _unidad(db_session, esc, nombre="Artilleria", clase="artilleria", lat=-0.1, alcance_km=30)
        if con_apoyo:
            _orden(db_session, esc, art, "apoyar", objetivo=a)
        _orden(db_session, esc, a, "atacar", objetivo=r)
        _correr(db_session, esc, 1800)
        return 100 - r.fuerza, art.municion

    sin, _ = combate(False)
    con, municion = combate(True)
    assert con > sin and municion == pytest.approx(100 - orders.MUNICION_POR_APOYO / 2, abs=0.5)
