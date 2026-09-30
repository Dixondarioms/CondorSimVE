"""Buques nuevos, portaaviones como base aerea movil y misiles de crucero (orden `lanzar`)."""

import pytest

from app.engine import aeronaves, catalogo, logistica, misiles
from app.models.evento import Evento
from app.models.orden import Orden
from app.models.unidad import Unidad
from app import state as state_mod
from app.engine import orders as orders_mod
from app.routers import ordenes as router_ordenes
from app.routers import unidades as router_unidades
from tests.conftest import TerrenoFalso
from tests.test_ciclo_vuelo import _caza, _orden, _refrescar
from tests.test_orders import _avanzar, _escenario, _unidad

MAR = TerrenoFalso(lambda lat, lon: "agua" if lat < 0.3 else "llano")


def _portaaviones(db, esc, **kw):
    return _unidad(db, esc, **{**dict(nombre="PA", tipo="naval", clase="portaaviones", velocidad_kmh=45, alcance_km=15,
                                       stock_combustible=800, stock_municion=800), **kw})


def _fragata(db, esc, **kw):
    return _unidad(db, esc, **{**dict(nombre="FF", tipo="naval", clase="fragata", velocidad_kmh=40, alcance_km=40,
                                       deteccion_km=30), **kw})


def _eventos(db, texto):
    return [e for e in db.query(Evento).all() if texto in e.descripcion]


# ---------- catalogo ----------
def test_las_clases_nuevas_existen_con_sus_banderas():
    assert catalogo.CLASES["destructor"].defensa_aerea and catalogo.CLASES["destructor"].emisor
    assert catalogo.CLASES["portaaviones"].plazas_aeronaves == 10 and catalogo.CLASES["base_aerea"].plazas_aeronaves == 12
    assert catalogo.CLASES["submarino"].firma < 0.5 and catalogo.CLASES["submarino"].ataque_vs["aerea"] == 0
    assert catalogo.CLASES["misil_crucero"].misil and catalogo.CLASES["misil_crucero"].se_consume
    for lanzador in ("fragata", "destructor", "submarino", "lanzador_misiles"):
        assert catalogo.CLASES[lanzador].lanza_misiles, lanzador
    assert catalogo.es_embarcable("helicoptero") and catalogo.es_embarcable("caza", "caza_embarcado")
    assert not catalogo.es_embarcable("caza", "f16") and not catalogo.es_embarcable("caza")
    for c in catalogo.CLASES.values():
        assert len(catalogo.generar_sidc("azul", c)) == 15


# ---------- portaaviones ----------
def test_el_portaaviones_lanza_helicopteros_y_cazas_embarcados_pero_no_un_f16(db_session):
    esc = _escenario(db_session)
    pa = _portaaviones(db_session, esc)
    assert aeronaves.error_de_despegue(pa, "f16", 2, 0) and "portaaviones" in aeronaves.error_de_despegue(pa, "f16", 2, 0)
    assert aeronaves.error_de_despegue(pa, "caza_embarcado", 2, 0) is None
    assert aeronaves.error_de_despegue(pa, "helo_ataque", 2, 0) is None
    assert "lanzar" in aeronaves.error_de_despegue(pa, "crucero", 1, 0)
    o = _orden(db_session, esc, pa, "despegar", detalle=aeronaves.codificar("caza_embarcado", 2, "Gaviota"))
    _avanzar(db_session, esc)
    _refrescar(db_session, o, pa)
    assert o.estado == "resuelta", o.resultado
    grupo = db_session.query(Unidad).filter(Unidad.nombre == "Gaviota").one()
    assert grupo.modelo == "caza_embarcado" and grupo.tipo == "aerea"
    assert logistica.stock(pa, "combustible") < 800  # el despegue consume existencias del portaaviones


def test_solo_las_embarcables_aterrizan_en_el_portaaviones_y_siguen_su_movimiento(db_session):
    esc = _escenario(db_session)
    pa = _portaaviones(db_session, esc, lat=0.0)
    helo = _caza(db_session, esc, nombre="Helo", clase="helicoptero", modelo="", lat=0.02)
    f16 = _caza(db_session, esc, nombre="Viper", modelo="f16", lat=0.02, lon=0.05)
    assert aeronaves.error_de_aterrizaje(helo, pa, [pa, helo, f16]) is None
    assert "portaaviones" in aeronaves.error_de_aterrizaje(f16, pa, [pa, helo, f16])
    _orden(db_session, esc, helo, "aterrizar", objetivo=pa)
    _avanzar(db_session, esc)
    _refrescar(db_session, helo)
    assert helo.en_tierra and helo.base_id == pa.id
    # el portaaviones navega y el helicoptero embarcado va con el
    _orden(db_session, esc, pa, "mover", waypoints=[[0.3, 0.0]])
    _avanzar(db_session, esc, MAR)
    _refrescar(db_session, pa, helo)
    assert pa.lat > 0.1 and abs(helo.lat - pa.lat) < 0.02 and helo.en_tierra


def test_las_aeronaves_embarcadas_se_hunden_con_el_portaaviones(db_session):
    esc = _escenario(db_session)
    pa = _portaaviones(db_session, esc, lat=0.0, fuerza=3.0)
    helo = _caza(db_session, esc, nombre="Helo", clase="helicoptero", modelo="", lat=0.006, en_tierra=True, base_id=pa.id)
    enemigo = _fragata(db_session, esc, nombre="Enemiga", bando="rojo", lat=0.1, alcance_km=60)
    _orden(db_session, esc, enemigo, "atacar", objetivo=pa)
    _avanzar(db_session, esc)
    _refrescar(db_session, pa, helo)
    assert pa.estado == "destruida" and helo.estado == "destruida"
    assert _eventos(db_session, "se hundio con")


def test_el_portaaviones_repone_existencias_junto_a_un_puerto_propio(db_session):
    esc = _escenario(db_session)
    puerto = _unidad(db_session, esc, nombre="Puerto", tipo="base", clase="puerto", velocidad_kmh=0, alcance_km=25,
                     stock_combustible=1000, stock_municion=1000)
    pa = _portaaviones(db_session, esc, lat=0.05, stock_combustible=100, stock_municion=100)
    _avanzar(db_session, esc)
    _refrescar(db_session, pa, puerto)
    assert logistica.stock(pa, "combustible") == pytest.approx(200) and logistica.stock(puerto, "combustible") == pytest.approx(900)


# ---------- misiles de crucero ----------
def _lanzamiento(db, esc, lanzador, blanco, n=2):
    return _orden(db, esc, lanzador, "lanzar", objetivo=blanco, detalle=misiles.codificar(n))


def _salvas(db):
    return db.query(Unidad).filter(Unidad.clase == "misil_crucero").all()


def test_validacion_del_lanzamiento(db_session):
    esc = _escenario(db_session)
    ff = _fragata(db_session, esc, municion=40)
    blanco = _unidad(db_session, esc, nombre="Deposito", bando="rojo", tipo="base", clase="deposito", lat=2.0)
    avion = _caza(db_session, esc, nombre="Rojo", bando="rojo", lat=0.5)
    patrullero = _unidad(db_session, esc, nombre="PC", tipo="naval", clase="patrullero", municion=100)
    assert misiles.error_de_lanzamiento(ff, blanco, 1) is None
    assert "Municion" in misiles.error_de_lanzamiento(ff, blanco, 2)
    assert "aeronaves" in misiles.error_de_lanzamiento(ff, avion, 1)
    assert "no puede lanzar" in misiles.error_de_lanzamiento(patrullero, blanco, 1)
    assert "1 y 4" in misiles.error_de_lanzamiento(ff, blanco, 5)
    lejos = _unidad(db_session, esc, nombre="Lejos", bando="rojo", lat=12.0)
    assert "fuera del alcance" in misiles.error_de_lanzamiento(ff, lejos, 1)


def test_la_salva_nace_vuela_guiada_e_impacta_y_se_consume(db_session):
    esc = _escenario(db_session)
    ff = _fragata(db_session, esc, municion=100)
    blanco = _unidad(db_session, esc, nombre="Deposito", bando="rojo", tipo="base", clase="deposito", lat=8.3, velocidad_kmh=0)
    o = _lanzamiento(db_session, esc, ff, blanco, 2)
    _avanzar(db_session, esc)
    _refrescar(db_session, o, ff)
    assert o.estado == "resuelta", o.resultado
    assert ff.municion == pytest.approx(50)
    [salva] = _salvas(db_session)
    assert salva.aeronaves == 2 and salva.blanco_id == blanco.id and salva.mision == "impacto"
    assert salva.estado == "activa" and 7.0 < salva.lat < 8.3  # 850 km en el primer turno: el blanco esta a 922 km
    assert aeronaves.aeronaves_en_servicio([salva]) == 0  # no cuenta para el tope
    _avanzar(db_session, esc)
    _refrescar(db_session, salva, blanco)
    assert salva.estado == "destruida" and blanco.fuerza < 100
    impacto = db_session.query(Orden).filter(Orden.unidad_id == salva.id, Orden.detalle == "impacto").one()
    assert impacto.estado == "resuelta"


def test_un_misil_no_admite_ordenes_y_se_pierde_si_el_blanco_desaparece(db_session):
    esc = _escenario(db_session)
    ff = _fragata(db_session, esc, municion=100)
    blanco = _unidad(db_session, esc, nombre="Deposito", bando="rojo", tipo="base", clase="deposito", lat=8.3, velocidad_kmh=0)
    _lanzamiento(db_session, esc, ff, blanco, 1)
    _avanzar(db_session, esc)
    [salva] = _salvas(db_session)
    o = _orden(db_session, esc, salva, "mover", waypoints=[[0.0, 1.0]])
    blanco.estado = "destruida"
    db_session.commit()
    _avanzar(db_session, esc)
    _refrescar(db_session, o, salva)
    assert o.estado == "rechazada" and "misil" in o.resultado
    assert salva.estado == "destruida" and _eventos(db_session, "ultimo punto conocido")


def test_la_antiaerea_derriba_la_salva_antes_del_impacto(db_session):
    esc = _escenario(db_session)
    ff = _fragata(db_session, esc, municion=100)
    blanco = _unidad(db_session, esc, nombre="Deposito", bando="rojo", tipo="base", clase="deposito", lat=2.0, velocidad_kmh=0)
    for k in range(4):  # una defensa densa junto al blanco: la salva de un misil no llega
        _unidad(db_session, esc, nombre=f"AA{k}", bando="rojo", clase="antiaerea", lat=2.0 + 0.01 * k, alcance_km=25, deteccion_km=60, fuerza=100)
    _lanzamiento(db_session, esc, ff, blanco, 1)
    _avanzar(db_session, esc)  # la salva llega al blanco (222 km) en el mismo turno: la antiaerea tira antes del impacto
    [salva] = _salvas(db_session)
    _refrescar(db_session, salva, blanco)
    impacto = db_session.query(Orden).filter(Orden.unidad_id == salva.id, Orden.detalle == "impacto").one()
    assert salva.estado == "destruida"
    if impacto.estado == "rechazada":
        assert "Derribado" in impacto.resultado and blanco.fuerza == 100
        assert _eventos(db_session, "derribado")
    else:  # llego con fuerza reducida: hizo menos daño que una salva intacta
        assert blanco.fuerza < 100


def test_un_misil_sin_alcance_cae_al_terreno(db_session):
    esc = _escenario(db_session)
    ff = _fragata(db_session, esc, municion=100)
    blanco = _unidad(db_session, esc, nombre="Lejano", bando="rojo", tipo="base", clase="deposito", lat=8.5, velocidad_kmh=0)
    _lanzamiento(db_session, esc, ff, blanco, 1)
    _avanzar(db_session, esc)
    [salva] = _salvas(db_session)
    salva.combustible = 5.0  # p. ej. un viento en contra: no le alcanza para los 94 km que faltan
    db_session.commit()
    _avanzar(db_session, esc)
    _refrescar(db_session, salva)
    assert salva.estado == "destruida" and _eventos(db_session, "agoto su alcance")


# ---------- API ----------
def test_api_lanzar_y_despegar_desde_portaaviones(api, monkeypatch):
    for modulo in (orders_mod, state_mod, router_unidades, router_ordenes):
        monkeypatch.setattr(modulo, "get_terreno", lambda: MAR)
    prof = api("prof")
    esc = prof.post("/api/escenarios", json={"nombre": "Mar"}).json()
    base = f"/api/escenarios/{esc['id']}"
    ids = [u["id"] for u in prof.get("/api/usuarios").json() if u["rol"] != "instructor"]
    prof.put(f"{base}/usuarios", json={"usuario_ids": ids})

    def unidad(**kw):
        r = prof.post(f"{base}/unidades", json=kw)
        assert r.status_code == 200, r.text
        return r.json()

    dd = unidad(nombre="DD", bando="azul", tipo="naval", clase="destructor", lat=0.0, lon=0.0)
    pa = unidad(nombre="PA", bando="azul", tipo="naval", clase="portaaviones", lat=0.1, lon=0.0)
    rojo = unidad(nombre="Puerto R", bando="rojo", tipo="base", clase="puerto", lat=0.35, lon=0.0)
    azul = api("alfa")
    r = azul.post(f"{base}/ordenes", json={"unidad_id": dd["id"], "tipo": "lanzar", "objetivo_unidad_id": rojo["id"], "misiles": 2})
    assert r.status_code == 200, r.text
    r = azul.post(f"{base}/ordenes", json={"unidad_id": dd["id"], "tipo": "lanzar", "objetivo_unidad_id": rojo["id"], "misiles": 9})
    assert r.status_code == 422
    r = azul.post(f"{base}/ordenes", json={"unidad_id": pa["id"], "tipo": "despegar", "modelo": "f16", "aeronaves": 2, "indicativo": "X"})
    assert r.status_code == 400 and "portaaviones" in r.json()["detail"]
    r = azul.post(f"{base}/ordenes", json={"unidad_id": pa["id"], "tipo": "despegar", "modelo": "helo_ataque", "aeronaves": 2, "indicativo": "Cobra"})
    assert r.status_code == 200, r.text
