"""Misiones aereas: validacion del rol y la ruta, estimacion, ejecucion por turnos (CAP, interdiccion, despegue
programado, guerra electronica, regreso por combustible) y API con puestos."""

import json

import pytest

from app.engine import catalogo
from app.engine import misiones as misiones_mod
from app.models.evento import Evento
from app.models.interferencia import Interferencia
from app.models.mision import Mision
from app.models.orden import Orden
from app.models.unidad import Unidad
from tests.test_aeronaves import _base_aerea
from tests.test_api import _preparar
from tests.test_ciclo_vuelo import _base, _caza, _refrescar
from tests.test_orders import _avanzar, _escenario, _unidad

KM = 1 / 111.195  # grados de latitud por km


def P(tipo, km_norte, **kw):
    return {"tipo": tipo, "lat": km_norte * KM, "lon": 0.0, **kw}


def aterrizaje(base):
    return {"tipo": "aterrizaje", "lat": base.lat, "lon": base.lon, "base_id": base.id}


def _mision(db, esc, rol, puntos, unidad=None, base=None, modelo="", aeronaves=0, turno=1, nombre=""):
    m = Mision(escenario_id=esc.id, bando="azul", rol=rol, nombre=nombre, estado="programada",
               unidad_id=unidad.id if unidad else None, base_id=base.id if base else None, modelo=modelo,
               aeronaves=aeronaves, turno_despegue=turno, creada_turno=1, puntos_json=json.dumps(puntos))
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


# ---------- planificacion ----------
def test_validacion_del_rol_y_de_la_ruta():
    caza, reco = catalogo.CLASES["caza"], catalogo.CLASES["dron_reconocimiento"]
    kami = catalogo.CLASES["municion_merodeadora"]
    aterr = {"tipo": "aterrizaje", "lat": 0, "lon": 0, "base_id": 1}
    orb, blanco = {"tipo": "orbita", "lat": 1, "lon": 0, "turnos": 2}, {"tipo": "blanco", "lat": 1, "lon": 0}
    assert misiones_mod.validar("CAP", [orb, aterr], caza) == []
    assert any("orbita" in e for e in misiones_mod.validar("CAP", [aterr], caza))
    assert any("interceptar" in e for e in misiones_mod.validar("CAP", [orb, aterr], reco))
    assert misiones_mod.validar("RECO", [orb, aterr], reco) == []
    assert any("terminar" in e for e in misiones_mod.validar("RECO", [orb], reco))
    assert any("ultimo" in e for e in misiones_mod.validar("TRASLADO", [aterr, aterr], caza))
    assert any("no admite" in e for e in misiones_mod.validar("TRASLADO", [orb, aterr], caza))
    assert misiones_mod.validar("INTERDICCION", [blanco], kami) == []
    assert any("merodeadora" in e for e in misiones_mod.validar("INTERDICCION", [blanco, aterr], kami))
    assert any("interferir" in e for e in misiones_mod.validar("GE", [orb, aterr], caza))
    assert misiones_mod.validar("XX", [aterr], caza) == ["Rol de mision desconocido."]


def test_la_estimacion_da_hora_y_combustible_en_cada_punto():
    pts = [P("orbita", 90, turnos=2), {"tipo": "aterrizaje", "lat": 0.0, "lon": 0.0, "base_id": 1}]
    plan = misiones_mod.estimar(0.0, 0.0, 900, 1800, 100, pts)
    orbita, final = plan["puntos"]
    assert orbita["llegada_h"] == pytest.approx(0.1, abs=0.01) and orbita["salida_h"] == 3
    assert orbita["combustible_llegada"] == pytest.approx(95, abs=0.2)
    assert orbita["combustible_salida"] == pytest.approx(79, abs=0.2)
    assert final["llegada_h"] == pytest.approx(3.1, abs=0.01) and plan["combustible_final"] == pytest.approx(74, abs=0.3)
    assert plan["advertencias"] == []
    corto = misiones_mod.estimar(0.0, 0.0, 900, 200, 100, pts)  # poca autonomia
    assert any(a.startswith("No alcanza") for a in corto["advertencias"])


# ---------- ejecucion por turnos ----------
def test_cap_vuela_a_la_orbita_intercepta_y_regresa_a_su_base(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    caza = _caza(db_session, esc, nombre="Halcon", lat=0.0)
    m = _mision(db_session, esc, "CAP", [P("orbita", 45, turnos=1), aterrizaje(base)], unidad=caza)

    _avanzar(db_session, esc)  # turno 1: llega a la orbita
    _refrescar(db_session, m, caza)
    assert m.estado == "en_curso" and m.espera == 1 and caza.mision == "patrulla"
    assert abs(caza.lat - 45 * KM) < 0.01

    enemigo = _caza(db_session, esc, nombre="Intruso", bando="rojo", lat=60 * KM)
    _avanzar(db_session, esc)  # turno 2: mantiene la orbita e intercepta
    _refrescar(db_session, m, caza)
    intercepcion = db_session.query(Orden).filter(Orden.unidad_id == caza.id, Orden.detalle == "intercepcion").first()
    assert intercepcion is not None and intercepcion.objetivo_unidad_id == enemigo.id
    assert m.indice == 1  # termino la orbita: el proximo turno reanuda el vuelo

    _avanzar(db_session, esc)  # turno 3: regresa y aterriza
    _refrescar(db_session, m, caza)
    assert m.estado == "cumplida" and caza.en_tierra and caza.base_id == base.id


def test_interdiccion_ataca_el_blanco_y_regresa(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    avion = _unidad(db_session, esc, nombre="Ataque 1", tipo="aerea", clase="ataque", velocidad_kmh=700, alcance_km=100,
                    deteccion_km=30, autonomia_km=2000)
    blindado = _unidad(db_session, esc, nombre="Blindado rojo", bando="rojo", clase="blindado", lat=150 * KM)
    m = _mision(db_session, esc, "INTERDICCION",
                [P("blanco", 150, objetivo_unidad_id=blindado.id), aterrizaje(base)], unidad=avion)
    _avanzar(db_session, esc)
    _refrescar(db_session, m, blindado)
    ataque = db_session.query(Orden).filter(Orden.unidad_id == avion.id, Orden.detalle == "mision").one()
    assert ataque.estado == "resuelta" and ataque.objetivo_unidad_id == blindado.id and blindado.fuerza < 100
    assert m.indice == 1 and m.estado == "en_curso"
    _avanzar(db_session, esc)
    _refrescar(db_session, m, avion)
    assert m.estado == "cumplida" and avion.en_tierra


def test_una_mision_programada_despega_de_la_base_en_su_turno(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    m = _mision(db_session, esc, "RECO", [P("paso", 100), aterrizaje(base)], base=base, modelo="uav_reco",
                aeronaves=1, turno=2, nombre="Vigia 7")
    _avanzar(db_session, esc)  # turno 1: aun no despega
    _refrescar(db_session, m)
    assert m.estado == "programada" and db_session.query(Unidad).filter(Unidad.tipo == "aerea").count() == 0
    _avanzar(db_session, esc)  # turno 2: despega, pasa el punto (100 km) y ya vuelve (150 km/h)
    _refrescar(db_session, m)
    grupo = db_session.get(Unidad, m.unidad_id)
    assert m.estado == "en_curso" and grupo.nombre == "Vigia 7" and grupo.modelo == "uav_reco"
    assert m.indice == 1 and abs(grupo.lat - 50 * KM) < 0.02
    _avanzar(db_session, esc)  # turno 3: aterriza
    _refrescar(db_session, m, grupo)
    assert m.estado == "cumplida" and grupo.en_tierra


def test_una_mision_de_guerra_electronica_interfiere_desde_su_orbita(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    avion = _unidad(db_session, esc, nombre="GE", tipo="aerea", clase="avion_ge", velocidad_kmh=750, alcance_km=60,
                    deteccion_km=60, autonomia_km=2500)
    _mision(db_session, esc, "GE", [P("orbita", 30, turnos=2), aterrizaje(base)], unidad=avion)
    _avanzar(db_session, esc)  # llega a la orbita
    assert db_session.query(Interferencia).count() == 0
    _avanzar(db_session, esc)  # orbita e interfiere
    zonas = db_session.query(Interferencia).all()
    assert [(z.unidad_id, z.radio_km) for z in zonas] == [(avion.id, 40.0)]


def test_con_combustible_critico_abandona_la_ruta_y_regresa(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    caza = _caza(db_session, esc, lat=0.0, combustible=20.0)
    m = _mision(db_session, esc, "CAP", [P("orbita", 45, turnos=3), aterrizaje(base)], unidad=caza)
    _avanzar(db_session, esc)
    _refrescar(db_session, m, caza)
    assert m.estado == "cumplida" and caza.en_tierra
    assert any("Combustible critico" in e.descripcion for e in db_session.query(Evento).all())


def test_el_grupo_derribado_da_la_mision_por_fallida(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    caza = _caza(db_session, esc, lat=0.0)
    m = _mision(db_session, esc, "CAP", [P("orbita", 45, turnos=2), aterrizaje(base)], unidad=caza)
    _avanzar(db_session, esc)
    caza.estado, caza.fuerza = "destruida", 0.0
    db_session.commit()
    _avanzar(db_session, esc)
    _refrescar(db_session, m)
    assert m.estado == "fallida"


# ---------- API ----------
def _aterrizaje_api(ba):
    return {"tipo": "aterrizaje", "lat": ba["lat"], "lon": ba["lon"], "base_id": ba["id"]}


def test_api_planificar_validar_y_ver_solo_el_propio_bando(api):
    prof, base, a, *_ = _preparar(api)
    ba = _base_aerea(prof, base, lat=0.0, lon=0.3)
    alfa = api("alfa")
    orbita = {"tipo": "orbita", "lat": 0.5, "lon": 0.3, "turnos": 2}
    cuerpo = {"rol": "CAP", "base_id": ba["id"], "modelo": "f16", "aeronaves": 2, "nombre": "Aguila",
              "puntos": [orbita, _aterrizaje_api(ba)]}
    r = alfa.post(f"{base}/misiones/previsualizar", json=cuerpo)
    assert r.status_code == 200, r.text
    assert r.json()["errores"] == [] and len(r.json()["plan"]["puntos"]) == 2
    r = alfa.post(f"{base}/misiones", json={**cuerpo, "puntos": [_aterrizaje_api(ba)]})
    assert r.status_code == 400 and "orbita" in r.json()["detail"]
    r = alfa.post(f"{base}/misiones", json={**cuerpo, "puntos": [orbita, {**_aterrizaje_api(ba), "base_id": a["id"]}]})
    assert r.status_code == 400 and "base aerea propia" in r.json()["detail"]
    r = alfa.post(f"{base}/misiones", json={**cuerpo, "turno_despegue": 99})
    assert r.status_code == 400
    r = alfa.post(f"{base}/misiones", json={**cuerpo, "turno_despegue": 2})
    assert r.status_code == 200, r.text
    creada = r.json()
    assert creada["estado"] == "programada" and creada["turno_despegue"] == 2 and creada["plan"]["puntos"]
    assert [m["id"] for m in alfa.get(base).json()["misiones"]] == [creada["id"]]
    assert api("bravo").get(base).json()["misiones"] == []
    assert len(prof.get(base).json()["misiones"]) == 1
    assert alfa.delete(f"{base}/misiones/{creada['id']}").json()["estado"] == "cancelada"


def test_api_puestos_y_la_orden_directa_reemplaza_la_mision(api):
    prof = api("prof")
    for nombre, puesto in (("ua3", "a3"), ("ua4", "a4")):
        assert prof.post("/api/usuarios", json={"username": nombre, "password": "clave-segura-1", "rol": "azul",
                                                "puesto": puesto}).status_code == 200
    prof, base, *_ = _preparar(api)
    ba = _base_aerea(prof, base, lat=0.0, lon=0.3)
    caza = prof.post(f"{base}/unidades", json=dict(nombre="Halcon", bando="azul", tipo="aerea", clase="caza",
                                                    modelo="f16", aeronaves=2, lat=0.1, lon=0.3)).json()
    ruta = [{"tipo": "orbita", "lat": 0.5, "lon": 0.3, "turnos": 1}, _aterrizaje_api(ba)]
    desde_base = {"rol": "CAP", "base_id": ba["id"], "modelo": "f16", "aeronaves": 2, "puntos": ruta}
    al_grupo = {"rol": "CAP", "unidad_id": caza["id"], "puntos": ruta}
    a3, a4 = api("ua3"), api("ua4")
    r = a4.post(f"{base}/misiones", json=desde_base)
    assert r.status_code == 403 and "Operaciones (A-3) o Defensa Aerea (A-3 D/A)" in r.json()["detail"]
    assert a3.post(f"{base}/misiones", json=desde_base).status_code == 200
    r = a4.post(f"{base}/misiones", json=al_grupo)
    assert r.status_code == 403 and "Operaciones (A-3)" in r.json()["detail"]
    mid = a3.post(f"{base}/misiones", json=al_grupo).json()["id"]
    assert a3.post(f"{base}/ordenes", json={"unidad_id": caza["id"], "tipo": "mover",
                                              "waypoints": [[0.2, 0.3]]}).status_code == 200
    estados = {m["id"]: m["estado"] for m in a3.get(base).json()["misiones"]}
    assert estados[mid] == "cancelada"


def test_el_catalogo_publica_los_roles_de_mision(api):
    cat = api("alfa").get("/api/catalogo").json()
    assert {r["id"] for r in cat["misiones"]["roles"]} == set(misiones_mod.ROLES)
    assert cat["misiones"]["tipos_punto"] == ["paso", "orbita", "blanco", "aterrizaje"]
