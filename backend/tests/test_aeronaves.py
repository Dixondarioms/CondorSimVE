"""Modelos de aeronave (F-16, Su-30) con foto, grupos aereos y despegue desde bases aereas."""

import json
from pathlib import Path

import pytest

from app.engine import aeronaves, catalogo, orders
from app.models.orden import Orden
from app.models.unidad import Unidad
from tests.test_api import _preparar
from tests.test_orders import _avanzar, _escenario, _orden, _unidad

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


def _base_aerea(prof, base, nombre="Base Azul", bando="azul", lat=0.0, lon=0.3, **kw):
    r = prof.post(f"{base}/unidades", json=dict(nombre=nombre, bando=bando, clase="base_aerea", lat=lat, lon=lon, **kw))
    assert r.status_code == 200, r.text
    return r.json()


def _despegar(cliente, base, base_aerea, modelo="f16", aeronaves_=4, indicativo="Halcon 1"):
    return cliente.post(f"{base}/ordenes", json={
        "unidad_id": base_aerea["id"], "tipo": "despegar", "modelo": modelo, "aeronaves": aeronaves_,
        "indicativo": indicativo})


# ---------- catalogo ----------
def test_cada_modelo_tiene_clase_valida_foto_en_disco_y_credito():
    assert {"f16", "su30"} <= set(catalogo.MODELOS)
    for m in catalogo.MODELOS.values():
        clase = catalogo.CLASES[m.clase]
        assert clase.id == m.clase  # aeronaves, sistemas terrestres y buques (catalogo ampliado)
        assert (FRONTEND / m.foto.lstrip("/")).is_file(), m.foto
        assert m.credito["autor"]
        if m.foto.endswith(".svg"):  # ilustracion propia: dominio publico, creditos en fotos/CREDITOS.md
            assert m.credito["licencia"] == "CC0" and m.credito["pagina"] == "/static/fotos/CREDITOS.md"
        else:  # foto de terceros (catalogo o tools/fotos): licencia libre y enlace a su origen
            licencia = m.credito["licencia"].lower()
            assert licencia.startswith(("cc by", "cc0", "public domain", "pd", "attribution")), m.credito["licencia"]
            assert m.credito["pagina"].startswith("https://")
        assert m.ataque_vs.keys() == {"terrestre", "aerea", "naval"}


def test_el_sukhoi_tiene_mas_alcance_y_autonomia_que_el_f16():
    f16, su30 = catalogo.MODELOS["f16"], catalogo.MODELOS["su30"]
    assert su30.autonomia_km > f16.autonomia_km and su30.deteccion_km > f16.deteccion_km
    assert su30.ataque_vs["naval"] > f16.ataque_vs["naval"] and f16.ataque_vs["terrestre"] < 1.0


def test_el_catalogo_de_la_api_incluye_modelos_y_topes(api):
    cat = api("alfa").get("/api/catalogo").json()
    assert {m["id"] for m in cat["modelos"]} >= {"f16", "su30"}
    assert cat["aeronaves"] == {"max_grupo": catalogo.MAX_AERONAVES_GRUPO, "max_bando": catalogo.MAX_AERONAVES_BANDO,
                                "max_drones": catalogo.MAX_DRONES_BANDO}
    assert api("alfa").get("/static/fotos/f16.jpg").status_code == 200


def test_perfil_aplica_el_modelo_solo_si_corresponde_a_la_clase():
    su30 = Unidad(clase="caza", tipo="aerea", modelo="su30", aeronaves=4)
    assert catalogo.perfil(su30).ataque_vs["naval"] == catalogo.MODELOS["su30"].ataque_vs["naval"]
    assert catalogo.perfil(su30).nombre == "Su-30MK2 Flanker-G"
    sin_modelo = Unidad(clase="caza", tipo="aerea", modelo="", aeronaves=1)
    assert catalogo.perfil(sin_modelo) == catalogo.CLASES["caza"]
    # un modelo de caza en una unidad de otra clase se ignora
    raro = Unidad(clase="ataque", tipo="aerea", modelo="f16", aeronaves=2)
    assert catalogo.perfil(raro) == catalogo.CLASES["ataque"]


def test_factor_grupo_crece_con_la_raiz_del_tamano_y_tiene_tope():
    assert catalogo.factor_grupo(Unidad(tipo="aerea", aeronaves=4)) == pytest.approx(1.0)
    assert catalogo.factor_grupo(Unidad(tipo="aerea", aeronaves=8)) == pytest.approx(2 ** 0.5)
    assert catalogo.factor_grupo(Unidad(tipo="aerea", aeronaves=1)) == pytest.approx(0.5)
    assert catalogo.factor_grupo(Unidad(tipo="aerea", aeronaves=12)) == pytest.approx(3 ** 0.5)
    assert catalogo.factor_grupo(Unidad(tipo="terrestre", aeronaves=8)) == 1.0
    assert [catalogo.escalon_grupo(n) for n in (1, 2, 3, 4, 5, 8)] == ["equipo", "equipo", "escuadra", "escuadra", "seccion", "seccion"]


# ---------- el instructor ubica grupos con modelo ----------
def test_el_instructor_ubica_un_grupo_con_modelo_y_toma_sus_valores(api):
    prof, base, a, r1, r2 = _preparar(api)
    r = prof.post(f"{base}/unidades", json=dict(nombre="Alfa", bando="azul", modelo="su30", aeronaves=2, lat=0.2, lon=0.2))
    assert r.status_code == 200, r.text
    u = r.json()
    m = catalogo.MODELOS["su30"]
    assert (u["clase"], u["tipo"], u["modelo"], u["aeronaves"]) == ("caza", "aerea", "su30", 2)
    assert (u["velocidad_kmh"], u["alcance_km"], u["deteccion_km"], u["autonomia_km"]) == (
        m.velocidad_kmh, m.alcance_km, m.deteccion_km, m.autonomia_km)
    assert u["echelon"] == "equipo" and u["sidc"].startswith("SFAPMFF")
    # los valores indicados a mano tienen prioridad sobre los del modelo
    r = prof.post(f"{base}/unidades", json=dict(nombre="Beta", bando="rojo", modelo="f16", aeronaves=6, velocidad_kmh=500, lat=0.3, lon=0.2))
    assert r.json()["velocidad_kmh"] == 500 and r.json()["echelon"] == "seccion" and r.json()["sidc"].startswith("SHAPMFF")


def test_modelo_invalido_o_incompatible_se_rechaza(api):
    prof, base, *_ = _preparar(api)
    datos = dict(nombre="X", bando="azul", lat=0.2, lon=0.2)
    assert "desconocido" in prof.post(f"{base}/unidades", json={**datos, "modelo": "mig99"}).json()["detail"]
    assert "no corresponde" in prof.post(f"{base}/unidades", json={**datos, "modelo": "f16", "clase": "ataque"}).json()["detail"]
    assert "maximo" in prof.post(f"{base}/unidades", json={**datos, "modelo": "f16", "aeronaves": 9}).json()["detail"]
    assert prof.post(f"{base}/unidades", json={**datos, "modelo": "f16", "aeronaves": 13}).status_code == 422
    # sin modelo, una unidad terrestre ignora el tamano de grupo
    r = prof.post(f"{base}/unidades", json={**datos, "clase": "infanteria", "aeronaves": 5})
    assert r.json()["aeronaves"] == 1 and r.json()["modelo"] == ""


def test_el_enemigo_detectado_no_revela_modelo_ni_tamano(api):
    prof, base, a, r1, r2 = _preparar(api)
    prof.post(f"{base}/unidades", json=dict(nombre="Caza rojo", bando="rojo", modelo="f16", aeronaves=4, lat=0.02, lon=0.0))
    visto = {u["nombre"]: u for u in api("alfa").get(base).json()["unidades"]}
    assert visto["Caza rojo"]["modelo"] is None and visto["Caza rojo"]["aeronaves"] is None
    propio = {u["nombre"]: u for u in api("bravo").get(base).json()["unidades"]}
    assert propio["Caza rojo"]["modelo"] == "f16" and propio["Caza rojo"]["aeronaves"] == 4
    completo = {u["nombre"]: u for u in prof.get(base).json()["unidades"]}
    assert completo["Caza rojo"]["modelo"] == "f16"


# ---------- orden de despegue ----------
def test_un_alumno_envia_un_grupo_desde_su_base_y_nace_al_resolver_el_turno(api):
    prof, base, a, r1, r2 = _preparar(api)
    ba = _base_aerea(prof, base, nombre="BA Libertador")
    azul = api("alfa")
    r = _despegar(azul, base, ba, modelo="su30", aeronaves_=4, indicativo="Flecha 1")
    assert r.status_code == 200, r.text
    assert json.loads(r.json()["detalle"]) == {"modelo": "su30", "aeronaves": 4, "indicativo": "Flecha 1"}
    assert prof.post(f"{base}/avanzar_turno").status_code == 200

    estado = azul.get(base).json()
    (grupo,) = [u for u in estado["unidades"] if u["nombre"] == "Flecha 1"]
    m = catalogo.MODELOS["su30"]
    assert (grupo["tipo"], grupo["clase"], grupo["modelo"], grupo["aeronaves"], grupo["bando"]) == ("aerea", "caza", "su30", 4, "azul")
    assert (grupo["combustible"], grupo["municion"], grupo["fuerza"]) == (100, 100, 100)
    assert grupo["autonomia_km"] == m.autonomia_km and grupo["echelon"] == "escuadra"
    assert 0 < grupo["lat"] - ba["lat"] < 0.05 and grupo["lat"] != ba["lat"]  # junto a la base, no encima
    (orden,) = [o for o in estado["ordenes"] if o["tipo"] == "despegar"]
    assert orden["estado"] == "resuelta" and "despego de BA Libertador" in orden["resultado"]
    assert any(e["tipo"] == "despegue" and "Flecha 1" in e["descripcion"] for e in estado["eventos"])
    # el rojo no se entera del despegue ni ve el grupo (esta lejos)
    rojo = api("bravo").get(base).json()
    assert all(u["nombre"] != "Flecha 1" for u in rojo["unidades"])
    assert all(e["tipo"] != "despegue" for e in rojo["eventos"])
    # desde el turno siguiente el grupo recibe ordenes
    r = azul.post(f"{base}/ordenes", json={"unidad_id": grupo["id"], "tipo": "mover", "waypoints": [[0.5, 0.5]]})
    assert r.status_code == 200, r.text


def test_el_despegue_se_valida_al_emitir(api):
    prof, base, a, r1, r2 = _preparar(api)
    ba = _base_aerea(prof, base)
    base_roja = _base_aerea(prof, base, nombre="Base Roja", bando="rojo", lat=0.5)
    azul = api("alfa")
    assert "Solo una base aerea" in _despegar(azul, base, a).json()["detail"]  # una infanteria
    dep = prof.post(f"{base}/unidades", json=dict(nombre="Dep", bando="azul", clase="deposito", lat=0.1, lon=0.3)).json()
    assert "Solo una base aerea" in _despegar(azul, base, dep).json()["detail"]
    assert _despegar(azul, base, base_roja).status_code == 404  # base enemiga: no revela que existe
    assert "modelo" in _despegar(azul, base, ba, modelo="mig99").json()["detail"]
    assert "modelo" in _despegar(azul, base, ba, modelo=None).json()["detail"]
    assert "entre 1 y" in _despegar(azul, base, ba, aeronaves_=9).json()["detail"]
    assert _despegar(azul, base, ba, aeronaves_=0).status_code == 422
    assert prof.post(f"{base}/ordenes", json={"unidad_id": ba["id"], "tipo": "despegar", "modelo": "f16", "aeronaves": 2}).status_code == 403
    prof.patch(f"{base}/unidades/{ba['id']}", json={"fuerza": 10})
    assert "muy danada" in _despegar(azul, base, ba).json()["detail"]


def test_el_tope_de_aeronaves_por_bando_incluye_activas_y_pendientes(api):
    prof, base, *_ = _preparar(api)
    ba1 = _base_aerea(prof, base, nombre="B1")
    ba2 = _base_aerea(prof, base, nombre="B2", lat=0.1)
    for i in range(2):  # 16 aeronaves ya en el aire
        prof.post(f"{base}/unidades", json=dict(nombre=f"G{i}", bando="azul", modelo="f16", aeronaves=8, lat=0.2, lon=0.2 + i * 0.01))
    azul = api("alfa")
    assert _despegar(azul, base, ba1, aeronaves_=8).status_code == 200  # 24 = tope
    r = _despegar(azul, base, ba2, aeronaves_=1)
    assert r.status_code == 400 and "Tope de 24" in r.json()["detail"]
    # reemplazar el despegue de la misma base no cuenta dos veces
    assert _despegar(azul, base, ba1, aeronaves_=6).status_code == 200
    assert _despegar(azul, base, ba2, aeronaves_=2).status_code == 200
    # las del otro bando no cuentan
    prof.post(f"{base}/unidades", json=dict(nombre="R", bando="rojo", modelo="su30", aeronaves=8, lat=1.2, lon=0.2))
    assert _despegar(azul, base, ba2, aeronaves_=2).status_code == 200


def test_una_base_destruida_o_danada_antes_de_resolver_rechaza_el_despegue(api):
    prof, base, *_ = _preparar(api)
    ba = _base_aerea(prof, base)
    azul = api("alfa")
    assert _despegar(azul, base, ba).status_code == 200
    prof.patch(f"{base}/unidades/{ba['id']}", json={"fuerza": 10})
    assert prof.post(f"{base}/avanzar_turno").status_code == 200
    (orden,) = [o for o in azul.get(base).json()["ordenes"] if o["tipo"] == "despegar"]
    assert orden["estado"] == "rechazada" and "muy danada" in orden["resultado"]
    assert not [u for u in azul.get(base).json()["unidades"] if u["tipo"] == "aerea"]


def test_dos_grupos_de_la_misma_base_no_nacen_en_el_mismo_punto(db_session):
    esc = _escenario(db_session)
    base = _unidad(db_session, esc, nombre="BA", tipo="base", clase="base_aerea", velocidad_kmh=0)
    g1 = aeronaves.crear_grupo(base, "f16", 2, "A", 0)
    g2 = aeronaves.crear_grupo(base, "f16", 2, "B", 1)
    assert (g1.lat, g1.lon) != (g2.lat, g2.lon)


def test_el_motor_lanza_todos_los_pedidos_del_turno_y_respeta_el_tope(db_session):
    esc = _escenario(db_session)
    b1 = _unidad(db_session, esc, nombre="B1", tipo="base", clase="base_aerea", velocidad_kmh=0)
    b2 = _unidad(db_session, esc, nombre="B2", tipo="base", clase="base_aerea", velocidad_kmh=0, lat=0.5)
    for b, n in ((b1, 8), (b2, 8)):
        db_session.add(Orden(escenario_id=esc.id, unidad_id=b.id, tipo="despegar", turno_emitida=1,
                             detalle=aeronaves.codificar("f16", n, f"G{b.id}")))
    db_session.add(Orden(escenario_id=esc.id, unidad_id=b1.id, tipo="despegar", turno_emitida=1, detalle="{}"))  # sin modelo
    db_session.commit()
    _avanzar(db_session, esc)
    grupos = db_session.query(Unidad).filter(Unidad.tipo == "aerea").all()
    assert len(grupos) == 2 and sum(g.aeronaves for g in grupos) == 16


# ---------- efecto en el combate ----------
def _combate(db_session, modelo_atacante, aeronaves_, defensor_tipo="terrestre", defensor_clase=None):
    esc = _escenario(db_session)
    a = _unidad(db_session, esc, nombre="A", tipo="aerea", clase="caza", modelo=modelo_atacante, aeronaves=aeronaves_,
                bando="azul", alcance_km=100, velocidad_kmh=900)
    d = _unidad(db_session, esc, nombre="D", tipo=defensor_tipo, clase=defensor_clase or "", bando="rojo", lat=0.045,
                alcance_km=10, deteccion_km=1)
    _orden(db_session, esc, a, "atacar", objetivo=d)
    _avanzar(db_session, esc)
    db_session.refresh(d)
    return 100 - d.fuerza


def test_un_grupo_mayor_hace_mas_dano(db_session):
    chico = _combate(db_session, "f16", 2, defensor_tipo="aerea", defensor_clase="caza")
    db_session.rollback()
    grande = _combate(db_session, "f16", 8, defensor_tipo="aerea", defensor_clase="caza")
    assert grande > chico > 0


def test_el_sukhoi_es_mejor_contra_buques_que_el_f16(db_session):
    f16 = _combate(db_session, "f16", 4, defensor_tipo="naval", defensor_clase="fragata")
    su30 = _combate(db_session, "su30", 4, defensor_tipo="naval", defensor_clase="fragata")
    assert su30 > f16 > 0


def test_solo_las_aeronaves_despegan_de_una_base():
    from types import SimpleNamespace

    base = SimpleNamespace(tipo="base", clase="base_aerea", estado="activa", fuerza=100.0, modelo="",
                           dano_pista=0.0, pista_largo_m=3000, pista_util_m=3000, stock_combustible=2000.0,
                           stock_municion=2000.0)
    for modelo in ("t72b1", "lupo", "s400"):
        motivo = aeronaves.error_de_despegue(base, modelo, 4, 0)
        assert motivo and "no es una aeronave" in motivo, (modelo, motivo)
