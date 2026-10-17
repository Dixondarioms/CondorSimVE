"""Reparticiones del TIEM dentro del bando: Comandante, Jefe de Estado Mayor, A-1 Personal, A-2 Inteligencia,
A-3 Operaciones, A-3 D/A Defensa Aerea, A-4 Logistica y C-E Comunicaciones y Electronica. Todas ven lo mismo;
cambia que ordenes puede emitir cada una."""

from app.engine import catalogo, puestos
from tests.test_api import _preparar


class _U:
    def __init__(self, tipo, clase=None):
        self.tipo, self.clase, self.modelo = tipo, clase, ""


def _f(tipo, clase, orden=None):
    u = _U(tipo, clase)
    return puestos.funcion_de_orden(u, orden, catalogo.perfil(u))


# ---------- matriz de funciones (logica pura) ----------
def test_el_comandante_y_el_jem_tienen_todas_las_funciones_y_el_comandante_es_el_puesto_por_defecto():
    for p in ("comandante", "jem"):
        assert puestos.obtener(p).funciones == frozenset(puestos.FUNCIONES)
    assert puestos.obtener("").id == "comandante" and puestos.obtener(None).id == "comandante"
    assert puestos.obtener("no-existe").id == "comandante"


def test_los_puestos_anteriores_al_tiem_se_traducen():
    assert {v: puestos.normalizar(v) for v in ("mando", "inteligencia", "operaciones", "logistica", "planificacion")} == {
        "mando": "comandante", "inteligencia": "a2", "operaciones": "a3", "logistica": "a4", "planificacion": "a3"}
    assert puestos.obtener("planificacion").sigla == "A-3"


def test_cada_reparticion_tiene_solo_lo_suyo():
    assert puestos.obtener("a1").funciones == frozenset()  # Personal no ordena unidades
    assert puestos.obtener("a2").funciones == {"reconocimiento"}
    assert puestos.obtener("a3").funciones == {"superficie", "aereo", "caza", "despegar"}
    assert puestos.obtener("a3da").funciones == {"defensa_aerea", "caza", "despegar"}
    assert puestos.obtener("a4").funciones == {"logistica"}
    assert puestos.obtener("ce").funciones == {"guerra_electronica"}
    # toda funcion sobre unidades tiene una reparticion responsable; LISTO es solo del Comandante y el JEM
    for f in puestos.FUNCIONES:
        if f != "listo":
            assert puestos.responsables(f), f
    assert puestos.responsables("listo") == []
    assert [p.id for p in puestos.responsables("caza")] == ["a3", "a3da"]
    assert [p.id for p in puestos.especializados()] == ["a2", "a3", "a3da", "a4", "ce"]


def test_la_funcion_de_una_orden_depende_de_la_unidad_y_del_tipo():
    assert _f("terrestre", "infanteria", "mover") == "superficie"
    assert _f("terrestre", "blindado", "atacar") == "superficie"
    assert _f("terrestre", "lanzador_misiles", "lanzar") == "superficie"
    assert _f("naval", "fragata", "mover") == "superficie"
    assert _f("terrestre", "ingenieros", "mover") == "logistica"  # ingenieros: siempre logistica
    assert _f("terrestre", "ingenieros", "construir") == "logistica"
    assert _f("terrestre", "transporte", "mover") == "logistica"  # convoy
    assert _f("terrestre", "infanteria", "construir") == "logistica"  # una obra, sea quien sea
    assert _f("aerea", "caza", "patrullar") == "caza"
    assert _f("aerea", "ataque", "atacar") == "aereo"
    assert _f("aerea", "helicoptero", "aterrizar") == "aereo"
    assert _f("aerea", "cisterna", "mover") == "aereo"
    assert _f("aerea", "dron_ataque", "atacar") == "aereo"
    assert _f("aerea", "municion_merodeadora", "atacar") == "aereo"
    assert _f("base", "base_aerea", "despegar") == "despegar"
    assert _f("base", "deposito", "mover") == "despegar"
    assert _f("terrestre", "infanteria", None) == "superficie"
    # defensa aerea: radares, antiaereas y alerta temprana
    for tipo, clase in (("terrestre", "radar"), ("terrestre", "antiaerea"), ("terrestre", "antiaerea_portatil"),
                        ("aerea", "alerta_temprana")):
        assert _f(tipo, clase, "mover") == "defensa_aerea", clase
    # guerra electronica (C-E) y reconocimiento (A-2)
    assert _f("terrestre", "guerra_electronica", "interferir") == "guerra_electronica"
    assert _f("aerea", "avion_ge", "interferir") == "guerra_electronica"
    assert _f("terrestre", "reconocimiento", "mover") == "reconocimiento"
    assert _f("aerea", "dron_reconocimiento", "mover") == "reconocimiento"


# ---------- API ----------
def _con_puestos(api):
    """Un alumno azul por reparticion, ademas de alfa (Comandante), asignados al escenario de _preparar."""
    prof = api("prof")
    for nombre in ("a1", "a2", "a3", "a3da", "a4", "ce", "jem"):
        r = prof.post("/api/usuarios", json={"username": f"u{nombre}", "password": "clave-segura-1", "rol": "azul", "puesto": nombre})
        assert r.status_code == 200 and r.json()["puesto"] == nombre, r.text
    return _preparar(api)


def _unidad(prof, base, **kw):
    r = prof.post(f"{base}/unidades", json=dict(bando="azul", lat=0.3, lon=0.3, **kw))
    assert r.status_code == 200, r.text
    return r.json()


def _mover(cliente, base, unidad):
    return cliente.post(f"{base}/ordenes", json={"unidad_id": unidad["id"], "tipo": "mover", "waypoints": [[0.31, 0.31]]})


def test_los_usuarios_nuevos_son_comandante_y_solo_los_alumnos_tienen_puesto(api):
    prof = api("prof")
    assert api("alfa").get("/api/auth/yo").json()["puesto"] == "comandante"
    r = prof.post("/api/usuarios", json={"username": "mira", "password": "clave-segura-1", "rol": "observador", "puesto": "a2"})
    assert r.status_code == 200 and r.json()["puesto"] == "comandante"  # sin bando no hay puesto
    assert prof.post("/api/usuarios", json={"username": "x", "password": "clave-segura-1", "rol": "azul", "puesto": "jefe"}).status_code == 422
    # un cliente viejo que manda un id anterior al TIEM recibe la reparticion que lo reemplaza
    r = prof.post("/api/usuarios", json={"username": "viejo", "password": "clave-segura-1", "rol": "azul", "puesto": "planificacion"})
    assert r.status_code == 200 and r.json()["puesto"] == "a3"


def test_personal_e_inteligencia_ven_pero_no_ordenan_ni_confirman(api):
    prof, base, a, *_ = _con_puestos(api)
    for nombre in ("ua1", "ua2"):
        c = api(nombre)
        assert c.get(base).status_code == 200  # misma vista que el resto del bando
        r = _mover(c, base, a)
        assert r.status_code == 403 and "Operaciones (A-3)" in r.json()["detail"], r.text
        r = c.post(f"{base}/listo", json={"listo": True})
        assert r.status_code == 403 and "Comandante" in r.json()["detail"]


def test_operaciones_conduce_la_maniobra_pero_no_la_defensa_aerea_ni_confirma(api):
    prof, base, a, *_ = _con_puestos(api)
    caza = _unidad(prof, base, nombre="Caza", tipo="aerea", clase="caza")
    ataque = _unidad(prof, base, nombre="Ataque", tipo="aerea", clase="ataque")
    radar = _unidad(prof, base, nombre="Radar", tipo="terrestre", clase="radar")
    a3 = api("ua3")
    for u in (a, caza, ataque):
        assert _mover(a3, base, u).status_code == 200, u["nombre"]
    r = _mover(a3, base, radar)
    assert r.status_code == 403 and "Defensa Aerea (A-3 D/A)" in r.json()["detail"]
    assert a3.post(f"{base}/listo", json={"listo": True}).status_code == 403


def test_defensa_aerea_conduce_radares_antiaereas_y_la_caza(api):
    prof, base, a, *_ = _con_puestos(api)
    radar = _unidad(prof, base, nombre="Radar", tipo="terrestre", clase="radar")
    aa = _unidad(prof, base, nombre="AA", tipo="terrestre", clase="antiaerea")
    caza = _unidad(prof, base, nombre="Caza", tipo="aerea", clase="caza")
    ataque = _unidad(prof, base, nombre="Ataque", tipo="aerea", clase="ataque")
    da = api("ua3da")
    for u in (radar, aa, caza):
        assert _mover(da, base, u).status_code == 200, u["nombre"]
    assert _mover(da, base, ataque).status_code == 403
    assert _mover(da, base, a).status_code == 403


def test_logistica_conduce_ingenieros_y_convoyes_y_nadie_mas_lo_hace(api):
    prof, base, a, *_ = _con_puestos(api)
    ing = _unidad(prof, base, nombre="Ing", tipo="terrestre", clase="ingenieros")
    convoy = _unidad(prof, base, nombre="Convoy", tipo="terrestre", clase="transporte")
    a4, a3 = api("ua4"), api("ua3")
    assert _mover(a4, base, ing).status_code == 200
    assert _mover(a4, base, convoy).status_code == 200
    r = _mover(a4, base, a)
    assert r.status_code == 403 and "Operaciones (A-3)" in r.json()["detail"]
    r = _mover(a3, base, ing)
    assert r.status_code == 403 and "Logistica (A-4)" in r.json()["detail"]


def test_ce_conduce_la_guerra_electronica_y_a2_el_reconocimiento(api):
    prof, base, a, *_ = _con_puestos(api)
    ge = _unidad(prof, base, nombre="GE", tipo="terrestre", clase="guerra_electronica")
    rec = _unidad(prof, base, nombre="Rec", tipo="terrestre", clase="reconocimiento")
    ce, a2 = api("uce"), api("ua2")
    assert _mover(ce, base, ge).status_code == 200
    assert _mover(a2, base, rec).status_code == 200
    r = _mover(a2, base, ge)
    assert r.status_code == 403 and "Comunicaciones y Electronica (C-E)" in r.json()["detail"]
    r = _mover(ce, base, rec)
    assert r.status_code == 403 and "Inteligencia (A-2)" in r.json()["detail"]


def test_el_despegue_desde_la_base_lo_ordenan_operaciones_o_defensa_aerea(api):
    prof, base, a, *_ = _con_puestos(api)
    ba = _unidad(prof, base, nombre="BA", tipo="base", clase="base_aerea")
    orden = {"unidad_id": ba["id"], "tipo": "despegar", "modelo": "f16", "aeronaves": 2, "indicativo": "AGUILA"}
    r = api("ua4").post(f"{base}/ordenes", json=orden)
    assert r.status_code == 403 and "Operaciones (A-3) o Defensa Aerea (A-3 D/A)" in r.json()["detail"]
    assert api("ua3").post(f"{base}/ordenes", json=orden).status_code == 200
    assert api("ua3da").post(f"{base}/ordenes", json=dict(orden, indicativo="HALCON")).status_code == 200


def test_cancelar_una_orden_respeta_la_reparticion(api):
    prof, base, a, *_ = _con_puestos(api)
    a3 = api("ua3")
    orden = _mover(a3, base, a).json()
    r = api("ua4").delete(f"{base}/ordenes/{orden['id']}")
    assert r.status_code == 403
    assert a3.delete(f"{base}/ordenes/{orden['id']}").status_code == 200


def test_el_comandante_y_el_jem_hacen_todo(api):
    prof, base, a, *_ = _con_puestos(api)
    caza = _unidad(prof, base, nombre="Caza", tipo="aerea", clase="caza")
    ing = _unidad(prof, base, nombre="Ing", tipo="terrestre", clase="ingenieros")
    radar = _unidad(prof, base, nombre="Radar", tipo="terrestre", clase="radar")
    for nombre in ("alfa", "ujem"):
        c = api(nombre)
        for u in (a, caza, ing, radar):
            assert _mover(c, base, u).status_code == 200, (nombre, u["nombre"])
        assert c.post(f"{base}/listo", json={"listo": True}).status_code == 200


def test_cambiar_la_reparticion_revoca_la_sesion_y_aplica_al_volver_a_entrar(api):
    prof, base, a, *_ = _con_puestos(api)
    a2 = api("ua2")
    uid = a2.get("/api/auth/yo").json()["id"]
    r = prof.patch(f"/api/usuarios/{uid}", json={"puesto": "a3"})
    assert r.status_code == 200 and r.json()["puesto"] == "a3"
    assert a2.get("/api/auth/yo").status_code == 401
    a2 = api("ua2")
    assert a2.get("/api/auth/yo").json()["puesto"] == "a3"
    assert _mover(a2, base, a).status_code == 200


def test_al_sacar_a_un_alumno_del_bando_su_puesto_vuelve_a_comandante(api):
    prof, *_ = _con_puestos(api)
    uid = next(u["id"] for u in prof.get("/api/usuarios").json() if u["username"] == "ua4")
    r = prof.patch(f"/api/usuarios/{uid}", json={"rol": "observador"})
    assert (r.json()["rol"], r.json()["puesto"]) == ("observador", "comandante")
