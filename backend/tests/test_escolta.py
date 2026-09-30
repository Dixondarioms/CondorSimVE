"""Rol ESCOLTA y paquetes de ataque (mision + escolta creadas juntas)."""

import json

from app.engine import misiones as misiones_mod
from app.models.mision import Mision
from tests.test_aeronaves import _base_aerea
from tests.test_api import _preparar
from tests.test_ciclo_vuelo import _base, _caza, _refrescar
from tests.test_misiones import _aterrizaje_api, _mision
from tests.test_orders import _avanzar, _escenario, _unidad


def _escolta(db, esc, unidad, escoltada, base):
    m = Mision(escenario_id=esc.id, bando="azul", rol="ESCOLTA", nombre="Escolta", estado="programada", unidad_id=unidad.id,
               turno_despegue=1, creada_turno=1, plan_json=json.dumps({"escolta_de": escoltada.id}),
               puntos_json=json.dumps([{"tipo": "aterrizaje", "lat": base.lat, "lon": base.lon, "base_id": base.id}]))
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def test_el_rol_escolta_existe_y_solo_admite_el_aterrizaje():
    from app.engine import catalogo
    caza = catalogo.CLASES["caza"]
    assert misiones_mod.validar("ESCOLTA", [{"tipo": "aterrizaje"}], caza) == []
    assert any("orbita" in e for e in misiones_mod.validar("ESCOLTA", [{"tipo": "orbita", "turnos": 1}, {"tipo": "aterrizaje"}], caza))
    assert misiones_mod.validar("ESCOLTA", [{"tipo": "aterrizaje"}], catalogo.CLASES["dron_reconocimiento"])


def test_la_escolta_sigue_al_grupo_escoltado_lo_protege_y_regresa_cuando_termina(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    ataque = _caza(db_session, esc, nombre="Ataque", lat=0.0, lon=0.1, velocidad_kmh=300, autonomia_km=3000)
    escolta = _caza(db_session, esc, nombre="Escolta", lat=0.0, lon=-0.3, velocidad_kmh=900, autonomia_km=3000)
    blanco = _unidad(db_session, esc, nombre="Blanco", bando="rojo", lat=5.0, lon=0.1, deteccion_km=0)
    principal = _mision(db_session, esc, "INTERDICCION",
                        [{"tipo": "blanco", "lat": blanco.lat, "lon": blanco.lon, "objetivo_unidad_id": blanco.id},
                         {"tipo": "aterrizaje", "lat": base.lat, "lon": base.lon, "base_id": base.id}], unidad=ataque, nombre="Rayo")
    esco = _escolta(db_session, esc, escolta, principal, base)
    _avanzar(db_session, esc)
    _refrescar(db_session, ataque, escolta, esco, principal)
    assert principal.estado == "en_curso" and esco.estado == "en_curso"
    assert misiones_mod.escolta_de(esco) == principal.id
    # la escolta alcanzo al grupo (menos de 8 km) y patrulla junto a el
    from app.engine import geo
    assert geo.distancia_km(escolta.lat, escolta.lon, ataque.lat, ataque.lon) <= misiones_mod.RADIO_ESCOLTA_KM + 1
    assert escolta.mision == "patrulla" and "Escolta a Ataque" in esco.resultado
    # cuando la mision escoltada termina, la escolta vuelve a la base
    principal.estado = "cumplida"
    db_session.commit()
    _avanzar(db_session, esc)
    _refrescar(db_session, esco, escolta)
    # a 900 km/h llega a la base (a ~300 km) en el mismo turno y aterriza: mision cumplida
    from app.models.evento import Evento
    assert escolta.mision == "" and esco.estado == "cumplida" and escolta.en_tierra
    assert any("escoltada termino" in e.descripcion for e in db_session.query(Evento).all())


def test_api_crea_el_paquete_mision_mas_escolta(api):
    prof, base, a, r1, r2 = _preparar(api)
    ba = _base_aerea(prof, base, lat=0.0, lon=0.3)
    alfa = api("alfa")
    cuerpo = {"rol": "INTERDICCION", "base_id": ba["id"], "modelo": "f16", "aeronaves": 2, "nombre": "Rayo",
              "puntos": [{"tipo": "blanco", "lat": r1["lat"], "lon": r1["lon"], "objetivo_unidad_id": r1["id"]}, _aterrizaje_api(ba)],
              "escolta": {"base_id": ba["id"], "modelo": "f16", "aeronaves": 2}}
    r = alfa.post(f"{base}/misiones", json=cuerpo)
    assert r.status_code == 200, r.text
    misiones = sorted(alfa.get(base).json()["misiones"], key=lambda m: m["id"])
    assert [m["rol"] for m in misiones] == ["INTERDICCION", "ESCOLTA"]
    escolta = misiones[1]
    assert escolta["escolta_de"] == misiones[0]["id"] and escolta["turno_despegue"] == misiones[0]["turno_despegue"]
    assert escolta["puntos"][-1]["base_id"] == ba["id"]
    # una escolta necesita indicar a quien escolta, y no puede escoltar a otra escolta
    r = alfa.post(f"{base}/misiones", json={"rol": "ESCOLTA", "base_id": ba["id"], "modelo": "f16", "aeronaves": 2, "puntos": [_aterrizaje_api(ba)]})
    assert r.status_code == 400 and "escoltar" in r.json()["detail"]
    r = alfa.post(f"{base}/misiones", json={"rol": "ESCOLTA", "base_id": ba["id"], "modelo": "f16", "aeronaves": 2, "puntos": [_aterrizaje_api(ba)], "escolta_de": escolta["id"]})
    assert r.status_code == 400
    r = alfa.post(f"{base}/misiones", json={"rol": "ESCOLTA", "base_id": ba["id"], "modelo": "f16", "aeronaves": 2, "puntos": [_aterrizaje_api(ba)], "escolta_de": misiones[0]["id"]})
    assert r.status_code == 200, r.text
