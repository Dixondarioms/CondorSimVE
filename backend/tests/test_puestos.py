"""Puestos por funcion dentro del bando: Estado Mayor, Inteligencia (A2), Operaciones (A3), Logistica (A4)
y Planificacion (A5). Todos ven lo mismo; cambia que ordenes puede emitir cada uno."""

from app.engine import catalogo, puestos
from tests.test_api import _preparar


class _U:
    def __init__(self, tipo, clase=None):
        self.tipo, self.clase, self.modelo = tipo, clase, ""


def _f(tipo, clase, orden=None):
    u = _U(tipo, clase)
    return puestos.funcion_de_orden(u, orden, catalogo.perfil(u))


# ---------- matriz de funciones (logica pura) ----------
def test_el_estado_mayor_tiene_todas_las_funciones_y_es_el_puesto_por_defecto():
    assert puestos.obtener("mando").funciones == frozenset(puestos.FUNCIONES)
    assert puestos.obtener("").id == "mando" and puestos.obtener(None).id == "mando"
    assert puestos.obtener("no-existe").id == "mando"


def test_cada_celula_tiene_solo_lo_suyo():
    assert puestos.obtener("inteligencia").funciones == {"guerra_electronica"}
    assert puestos.obtener("operaciones").funciones == {"aereo"}
    assert puestos.obtener("logistica").funciones == {"logistica"}
    assert puestos.obtener("planificacion").funciones == {"superficie", "despegar", "listo"}
    # ninguna funcion queda sin un puesto especializado responsable
    for f in puestos.FUNCIONES:
        assert puestos.responsables(f), f
    assert [p.id for p in puestos.responsables("listo")] == ["planificacion"]


def test_la_funcion_de_una_orden_depende_de_la_unidad_y_del_tipo():
    assert _f("terrestre", "infanteria", "mover") == "superficie"
    assert _f("terrestre", "blindado", "atacar") == "superficie"
    assert _f("naval", "fragata", "mover") == "superficie"
    assert _f("terrestre", "ingenieros", "mover") == "logistica"  # ingenieros: siempre logistica
    assert _f("terrestre", "ingenieros", "construir") == "logistica"
    assert _f("terrestre", "transporte", "mover") == "logistica"  # convoy
    assert _f("terrestre", "infanteria", "construir") == "logistica"  # una obra, sea quien sea
    assert _f("aerea", "caza", "patrullar") == "aereo"
    assert _f("aerea", "caza", "mover") == "aereo"
    assert _f("aerea", "helicoptero", "aterrizar") == "aereo"
    assert _f("base", "base_aerea", "despegar") == "despegar"
    assert _f("base", "deposito", "mover") == "despegar"  # las bases son de planificacion
    assert _f("terrestre", "infanteria", None) == "superficie"
    # radares y guerra electronica terrestre: A2; los medios aereos de GE y los drones: A3
    assert _f("terrestre", "guerra_electronica", "interferir") == "guerra_electronica"
    assert _f("terrestre", "guerra_electronica", "mover") == "guerra_electronica"
    assert _f("terrestre", "radar", "mover") == "guerra_electronica"
    assert _f("aerea", "avion_ge", "interferir") == "aereo"
    assert _f("aerea", "dron_reconocimiento", "mover") == "aereo"
    assert _f("aerea", "municion_merodeadora", "atacar") == "aereo"


# ---------- API ----------
def _con_puestos(api):
    """Un alumno azul por puesto, ademas de alfa (Estado Mayor), asignados al escenario de _preparar."""
    prof = api("prof")
    for nombre, puesto in (("a2int", "inteligencia"), ("a3ops", "operaciones"), ("a4log", "logistica"), ("a5plan", "planificacion")):
        r = prof.post("/api/usuarios", json={"username": nombre, "password": "clave-segura-1", "rol": "azul", "puesto": puesto})
        assert r.status_code == 200 and r.json()["puesto"] == puesto, r.text
    return _preparar(api)


def _unidad(prof, base, **kw):
    r = prof.post(f"{base}/unidades", json=dict(bando="azul", lat=0.3, lon=0.3, **kw))
    assert r.status_code == 200, r.text
    return r.json()


def _mover(cliente, base, unidad):
    return cliente.post(f"{base}/ordenes", json={"unidad_id": unidad["id"], "tipo": "mover", "waypoints": [[0.31, 0.31]]})


def test_los_usuarios_nuevos_son_estado_mayor_y_solo_los_alumnos_tienen_puesto(api):
    prof = api("prof")
    assert api("alfa").get("/api/auth/yo").json()["puesto"] == "mando"
    r = prof.post("/api/usuarios", json={"username": "mira", "password": "clave-segura-1", "rol": "observador", "puesto": "inteligencia"})
    assert r.status_code == 200 and r.json()["puesto"] == "mando"  # sin bando no hay puesto
    assert prof.post("/api/usuarios", json={"username": "x", "password": "clave-segura-1", "rol": "azul", "puesto": "jefe"}).status_code == 422


def test_inteligencia_ve_pero_no_ordena_ni_confirma(api):
    prof, base, a, *_ = _con_puestos(api)
    a2 = api("a2int")
    assert a2.get(base).status_code == 200  # misma vista que el resto del bando
    r = _mover(a2, base, a)
    assert r.status_code == 403 and "Planificacion (A5)" in r.json()["detail"] and "Inteligencia" in r.json()["detail"]
    r = a2.post(f"{base}/listo", json={"listo": True})
    assert r.status_code == 403 and "Planificacion (A5)" in r.json()["detail"]


def test_planificacion_ordena_en_superficie_y_confirma_pero_no_conduce_aeronaves(api):
    prof, base, a, *_ = _con_puestos(api)
    caza = _unidad(prof, base, nombre="Caza", tipo="aerea", clase="caza")
    a5 = api("a5plan")
    assert _mover(a5, base, a).status_code == 200
    r = _mover(a5, base, caza)
    assert r.status_code == 403 and "Operaciones en curso (A3)" in r.json()["detail"]
    assert a5.post(f"{base}/listo", json={"listo": True}).status_code == 200


def test_operaciones_conduce_solo_aeronaves(api):
    prof, base, a, *_ = _con_puestos(api)
    caza = _unidad(prof, base, nombre="Caza", tipo="aerea", clase="caza")
    a3 = api("a3ops")
    assert _mover(a3, base, caza).status_code == 200
    r = _mover(a3, base, a)
    assert r.status_code == 403 and "Planificacion (A5)" in r.json()["detail"]
    assert a3.post(f"{base}/listo", json={"listo": True}).status_code == 403


def test_logistica_conduce_ingenieros_y_convoyes_y_nadie_mas_lo_hace(api):
    prof, base, a, *_ = _con_puestos(api)
    ing = _unidad(prof, base, nombre="Ing", tipo="terrestre", clase="ingenieros")
    convoy = _unidad(prof, base, nombre="Convoy", tipo="terrestre", clase="transporte")
    a4, a5 = api("a4log"), api("a5plan")
    assert _mover(a4, base, ing).status_code == 200
    assert _mover(a4, base, convoy).status_code == 200
    r = _mover(a4, base, a)
    assert r.status_code == 403 and "Planificacion (A5)" in r.json()["detail"]
    r = _mover(a5, base, ing)
    assert r.status_code == 403 and "Logistica (A4)" in r.json()["detail"]


def test_el_despegue_desde_la_base_lo_ordena_planificacion(api):
    prof, base, a, *_ = _con_puestos(api)
    ba = _unidad(prof, base, nombre="BA", tipo="base", clase="base_aerea")
    orden = {"unidad_id": ba["id"], "tipo": "despegar", "modelo": "f16", "aeronaves": 2, "indicativo": "AGUILA"}
    r = api("a3ops").post(f"{base}/ordenes", json=orden)
    assert r.status_code == 403 and "Planificacion (A5)" in r.json()["detail"]
    assert api("a5plan").post(f"{base}/ordenes", json=orden).status_code == 200


def test_cancelar_una_orden_respeta_el_puesto(api):
    prof, base, a, *_ = _con_puestos(api)
    a5 = api("a5plan")
    orden = _mover(a5, base, a).json()
    r = api("a3ops").delete(f"{base}/ordenes/{orden['id']}")
    assert r.status_code == 403
    assert a5.delete(f"{base}/ordenes/{orden['id']}").status_code == 200


def test_el_estado_mayor_hace_todo(api):
    prof, base, a, *_ = _con_puestos(api)
    caza = _unidad(prof, base, nombre="Caza", tipo="aerea", clase="caza")
    ing = _unidad(prof, base, nombre="Ing", tipo="terrestre", clase="ingenieros")
    alfa = api("alfa")
    for u in (a, caza, ing):
        assert _mover(alfa, base, u).status_code == 200, u["nombre"]
    assert alfa.post(f"{base}/listo", json={"listo": True}).status_code == 200


def test_cambiar_el_puesto_revoca_la_sesion_y_aplica_al_volver_a_entrar(api):
    prof, base, a, *_ = _con_puestos(api)
    a2 = api("a2int")
    uid = a2.get("/api/auth/yo").json()["id"]
    r = prof.patch(f"/api/usuarios/{uid}", json={"puesto": "planificacion"})
    assert r.status_code == 200 and r.json()["puesto"] == "planificacion"
    assert a2.get("/api/auth/yo").status_code == 401
    a2 = api("a2int")
    assert a2.get("/api/auth/yo").json()["puesto"] == "planificacion"
    assert _mover(a2, base, a).status_code == 200


def test_al_sacar_a_un_alumno_del_bando_su_puesto_vuelve_a_estado_mayor(api):
    prof, *_ = _con_puestos(api)
    uid = next(u["id"] for u in prof.get("/api/usuarios").json() if u["username"] == "a4log")
    r = prof.patch(f"/api/usuarios/{uid}", json={"rol": "observador"})
    assert (r.json()["rol"], r.json()["puesto"]) == ("observador", "mando")
