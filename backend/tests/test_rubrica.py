"""Rubrica de evaluacion del informe posterior (GET /api/escenarios/{id}/aar/rubrica): ordenes, turnos pasivos,
logistica, perdidas, objetivos, misiones y observaciones automaticas por bando, por puesto responsable y por
alumno (autor registrado en cada orden y mision)."""

import csv
import io

from app import auth
from app.engine import aar
from app.models.aar import RegistroLogistico
from app.models.asignacion import Asignacion
from app.models.mision import Mision
from app.models.objetivo import Objetivo
from app.models.orden import Orden
from app.models.usuario import Usuario
from tests.test_api import _preparar
from tests.test_orders import _escenario, _orden, _unidad


def test_motivo_generico_agrupa_cifras_y_parentesis():
    assert aar.motivo_generico("Objetivo fuera de alcance (12.3 km > 10.0 km).") == "Objetivo fuera de alcance"
    assert aar.motivo_generico("Objetivo fuera de alcance (40 km > 10 km).") == "Objetivo fuera de alcance"
    assert aar.motivo_generico("Recargando (2 turno(s) restante(s)).") == "Recargando"
    assert aar.motivo_generico("En tierra: faltan 2 turno(s) para reabastecer.") == "En tierra: faltan N turno para reabastecer"
    assert aar.motivo_generico("") == "(sin motivo)"


def _jugar(api):
    """Azul: dos ataques fuera de alcance (rechazados al resolver) y uno valido; rojo: solo ataca en el turno 2."""
    prof, base, a, r1, r2 = _preparar(api)
    # C ve a R1 (5 km) pero no lo alcanza (2 km): la orden se acepta y el motor la rechaza al resolver
    c = prof.post(f"{base}/unidades", json=dict(nombre="C", bando="azul", tipo="terrestre", lat=0.0, lon=0.001,
                                                alcance_km=2, deteccion_km=10)).json()
    azul, rojo = api("alfa"), api("bravo")

    def atacar(cliente, quien, objetivo):
        r = cliente.post(f"{base}/ordenes", json={"unidad_id": quien["id"], "tipo": "atacar", "objetivo_unidad_id": objetivo["id"]})
        assert r.status_code == 200, r.text

    atacar(azul, c, r1)
    prof.post(f"{base}/avanzar_turno")
    atacar(azul, c, r1)
    atacar(rojo, r1, a)
    prof.post(f"{base}/avanzar_turno")
    atacar(azul, a, r1)
    prof.post(f"{base}/avanzar_turno")
    return prof, base, a, r1, r2


def test_la_rubrica_cuenta_ordenes_rechazos_turnos_pasivos_y_perdidas(api):
    prof, base, a, r1, r2 = _jugar(api)
    r = prof.get(f"{base}/aar/rubrica")
    assert r.status_code == 200, r.text
    rub = r.json()
    assert rub["escenario"]["turnos_resueltos"] == 3
    az, ro = rub["bandos"]["azul"], rub["bandos"]["rojo"]

    assert (az["ordenes"]["emitidas"], az["ordenes"]["resueltas"], az["ordenes"]["rechazadas"]) == (3, 1, 2)
    assert az["ordenes"]["motivos_rechazo"] == [{"motivo": "Objetivo fuera de alcance", "veces": 2}]
    assert az["ordenes"]["tasa_rechazo"] == 66.7
    assert az["turnos_pasivos"] == {"cantidad": 0, "turnos": []}
    assert (ro["ordenes"]["emitidas"], ro["ordenes"]["resueltas"]) == (1, 1)
    assert ro["turnos_pasivos"] == {"cantidad": 2, "turnos": [1, 3]}

    # ambos combatieron: lo que uno inflige lo sufre el otro
    assert az["perdidas"]["infligidas"] == ro["perdidas"]["sufridas"] > 0
    assert az["perdidas"]["sufridas"] == ro["perdidas"]["infligidas"] > 0

    # unidades terrestres -> puesto responsable A5 (planificacion); las demas celdas quedan en cero
    assert az["puestos"]["planificacion"]["ordenes"]["emitidas"] == 3
    assert az["puestos"]["planificacion"]["ordenes"]["rechazadas"] == 2
    assert all(az["puestos"][p]["ordenes"]["emitidas"] == 0 for p in ("inteligencia", "operaciones", "logistica"))
    assert "puesto responsable" in rub["nota_puestos"]

    # por alumno: alfa (azul) firmo las 3 ordenes; bravo (rojo) solo la del turno 2; el observador no se evalua
    alumnos = {a["username"]: a for a in rub["alumnos"]}
    assert list(alumnos) == ["alfa", "bravo"]
    alfa, bravo = alumnos["alfa"], alumnos["bravo"]
    assert (alfa["bando"], alfa["puesto"], alfa["sigla"], alfa["asignado"]) == ("azul", "mando", "EM", True)
    assert (alfa["ordenes"]["emitidas"], alfa["ordenes"]["rechazadas"], alfa["ordenes"]["tasa_rechazo"]) == (3, 2, 66.7)
    assert alfa["turnos_activos"] == {"cantidad": 3, "turnos": [1, 2, 3]}
    assert alfa["turnos_pasivos"] == {"cantidad": 0, "turnos": []}
    assert "2 orden(es) rechazada(s) de alfa por 'Objetivo fuera de alcance'" in " ".join(alfa["observaciones"])
    assert (bravo["ordenes"]["emitidas"], bravo["turnos_pasivos"]["turnos"], bravo["turnos_activos"]["turnos"]) == (1, [1, 3], [2])
    assert "2 turno(s) sin emitir ninguna orden (turno(s) 1, 3)" in " ".join(bravo["observaciones"])
    assert rub["sin_autor"] == {"azul": {"ordenes": 0, "misiones": 0}, "rojo": {"ordenes": 0, "misiones": 0}}

    obs_azul = " ".join(az["observaciones"])
    assert "2 orden(es) rechazada(s) por 'Objetivo fuera de alcance': revisar la apreciacion de distancias" in obs_azul
    assert "Alta proporcion de ordenes rechazadas (67 % de 3)" in obs_azul
    assert any("en A5" in o for o in az["puestos"]["planificacion"]["observaciones"])
    obs_rojo = " ".join(ro["observaciones"])
    assert "2 turno(s) sin emitir ninguna orden (turno(s) 1, 3)" in obs_rojo


def test_logistica_objetivos_y_misiones_en_la_rubrica(db_session):
    esc = _escenario(db_session)
    a = _unidad(db_session, esc, nombre="A", bando="azul", municion=10.0)
    b = _unidad(db_session, esc, nombre="B", bando="azul", combustible=20.0, municion=15.0)
    _unidad(db_session, esc, nombre="R", bando="rojo", estado="destruida")
    esc.turno_actual = 3
    db_session.add_all([
        RegistroLogistico(escenario_id=esc.id, turno=2, unidad_id=a.id, unidad_nombre="A", bando="azul",
                          variable="municion", antes=5.0, despues=10.0, causa="reabastecimiento"),
        RegistroLogistico(escenario_id=esc.id, turno=2, unidad_id=a.id, unidad_nombre="A", bando="azul",
                          variable="combustible", antes=50.0, despues=40.0, causa="movimiento"),
        Objetivo(escenario_id=esc.id, bando="azul", tipo="destruir", nombre="Destruir R", puntos=30, estado="cumplido"),
        Objetivo(escenario_id=esc.id, bando="rojo", tipo="proteger", nombre="Proteger R", puntos=20, estado="fallido"),
        Mision(escenario_id=esc.id, bando="azul", rol="cap", estado="abortada", turno_despegue=1, creada_turno=1),
        Mision(escenario_id=esc.id, bando="azul", rol="cap", estado="cumplida", turno_despegue=2, creada_turno=2),
        Mision(escenario_id=esc.id, bando="azul", rol="cap", estado="fallida", turno_despegue=2, creada_turno=2),
    ])
    db_session.commit()

    rub = aar.construir_rubrica(db_session, esc)
    az, ro = rub["bandos"]["azul"], rub["bandos"]["rojo"]
    criticas = {c["unidad"]: c for c in az["logistica"]["unidades_criticas"]}
    assert set(criticas) == {"A", "B"} and criticas["B"]["variables"] == ["combustible", "municion"]
    assert criticas["A"]["minimo"] == 10.0 and az["logistica"]["unidades_en_nivel_critico"] == 2
    assert az["logistica"]["reabastecimientos"] == 1  # el movimiento no cuenta
    assert az["objetivos"] == {"cumplidos": 1, "fallidos": 0, "pendientes": 0, "puntos": 30}
    assert ro["objetivos"]["fallidos"] == 1
    assert az["misiones"]["planificadas"] == 3 and az["misiones"]["abortadas"] == 1 and az["misiones"]["fallidas"] == 1
    assert az["puestos"]["planificacion"]["misiones"] == 3  # sin unidad: despegue desde base -> A5
    assert (az["perdidas"]["enemigas_destruidas"], ro["perdidas"]["unidades_destruidas"]) == (1, 1)
    # las misiones cuentan como actividad: turnos 1 y 2 no son pasivos para azul; rojo sin ordenes ni misiones
    assert az["turnos_pasivos"]["turnos"] == [] and ro["turnos_pasivos"]["turnos"] == [1, 2]
    obs = " ".join(az["observaciones"])
    assert "2 unidad(es) llegaron a menos del 25 %" in obs and "se hicieron 1 reabastecimiento(s)" in obs
    assert "Todos los objetivos asignados se cumplieron." in az["observaciones"]
    assert "Misiones aereas abortadas o fallidas (2) igualan o superan a las cumplidas (1)" in obs
    assert "El bando no emitio ninguna orden durante el ejercicio." in ro["observaciones"]
    assert "1 objetivo(s) fallido(s)" in " ".join(ro["observaciones"])


def _usuario(db, nombre, rol, puesto="mando", esc=None):
    u = Usuario(username=nombre, password_hash=auth.hash_password("clave-segura-1"), rol=rol, puesto=puesto)
    db.add(u)
    db.commit()
    if esc is not None:
        db.add(Asignacion(usuario_id=u.id, escenario_id=esc.id))
        db.commit()
    return u


def test_alumnos_sin_actividad_ordenes_sin_autor_y_misiones_por_nombre(db_session):
    """Un alumno asignado que no emitio nada aparece con su observacion; las ordenes anteriores a la migracion
    (sin autor) se cuentan aparte por bando y las automaticas del motor no se atribuyen a nadie; una mision previa
    que solo guardo el nombre de usuario se atribuye por ese nombre."""
    esc = _escenario(db_session)
    esc.turno_actual = 3
    a = _unidad(db_session, esc, nombre="A", bando="azul")
    r = _unidad(db_session, esc, nombre="R", bando="rojo")
    caza = _unidad(db_session, esc, nombre="Caza", tipo="aerea", clase="caza")
    quieto = _usuario(db_session, "quieto", "azul", "logistica", esc)
    piloto = _usuario(db_session, "piloto", "azul", "operaciones")
    _usuario(db_session, "mirando", "observador", esc=esc)
    _orden(db_session, esc, a, "mover", waypoints=[[1, 1]])  # sin autor: anterior a la migracion
    _orden(db_session, esc, r, "mover", waypoints=[[1, 1]])
    db_session.add(Orden(escenario_id=esc.id, unidad_id=caza.id, tipo="atacar", objetivo_unidad_id=r.id,
                         detalle="intercepcion", turno_emitida=2, waypoints_json="[]", estado="resuelta"))
    db_session.add(Mision(escenario_id=esc.id, bando="azul", rol="cap", estado="cumplida", turno_despegue=1,
                          creada_turno=1, autor="piloto"))
    db_session.add(Mision(escenario_id=esc.id, bando="rojo", rol="cap", estado="cumplida", turno_despegue=1,
                          creada_turno=1))
    db_session.commit()

    rub = aar.construir_rubrica(db_session, esc)
    alumnos = {x["username"]: x for x in rub["alumnos"]}
    assert list(alumnos) == ["piloto", "quieto"]  # el observador no se evalua; piloto entra por su mision
    assert alumnos["quieto"]["sigla"] == "A4" and alumnos["quieto"]["asignado"] is True
    assert alumnos["quieto"]["observaciones"] == ["No emitio ninguna orden ni planifico misiones durante el ejercicio."]
    assert alumnos["quieto"]["turnos_pasivos"] == {"cantidad": 2, "turnos": [1, 2]}
    p = alumnos["piloto"]
    assert (p["asignado"], p["sigla"], p["misiones"]["planificadas"], p["misiones"]["cumplidas"]) == (False, "A3", 1, 1)
    assert p["turnos_activos"]["turnos"] == [1] and p["turnos_pasivos"]["turnos"] == [2]
    assert p["observaciones"] == ["1 turno(s) sin emitir ninguna orden (turno(s) 2): mantener la iniciativa o dejar "
                                  "constancia de la decision de esperar."]
    # la intercepcion automatica no cuenta como "sin autor"
    assert rub["sin_autor"] == {"azul": {"ordenes": 1, "misiones": 0}, "rojo": {"ordenes": 1, "misiones": 1}}
    assert "sin autor registrado" in rub["nota_alumnos"]
    # las secciones por bando siguen contando todas las ordenes (incluidas las automaticas)
    assert rub["bandos"]["azul"]["ordenes"]["emitidas"] == 2
    assert quieto.id != piloto.id


def test_el_puesto_del_alumno_es_el_que_ocupaba_al_emitir(db_session):
    esc = _escenario(db_session)
    a = _unidad(db_session, esc, nombre="A", bando="azul")
    u = _usuario(db_session, "cambiante", "azul", "planificacion", esc)
    db_session.add(Orden(escenario_id=esc.id, unidad_id=a.id, tipo="mover", waypoints_json="[[1, 1]]", turno_emitida=1,
                         autor_id=u.id, autor_puesto="operaciones"))
    db_session.commit()
    u.puesto = "mando"  # el instructor lo cambio de puesto despues
    db_session.commit()
    alumnos = aar.construir_rubrica(db_session, esc)["alumnos"]
    assert [(x["username"], x["puesto"], x["ordenes"]["emitidas"]) for x in alumnos] == [("cambiante", "operaciones", 1)]


def test_las_ordenes_y_misiones_registran_su_autor(api):
    prof, base, a, r1, r2 = _preparar(api)
    azul = api("alfa")
    assert azul.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "mover", "waypoints": [[0.1, 0]]}).status_code == 200
    ordenes = azul.get(f"{base}/ordenes").json()
    assert [(o["autor"], o["autor_puesto"]) for o in ordenes] == [("alfa", "mando")]
    estado = azul.get(base).json()
    assert estado["ordenes"][0]["autor"] == "alfa" and estado["ordenes"][0]["autor_puesto"] == "mando"
    lote = azul.post(f"{base}/ordenes/lote", json={"unidad_ids": [a["id"]], "orden": {"tipo": "mover", "waypoints": [[0.2, 0]]}})
    assert lote.status_code == 200 and lote.json()["emitidas"] == 1
    assert [o["autor"] for o in azul.get(f"{base}/ordenes").json()] == ["alfa"]
    informe = prof.get(f"{base}/aar").json()
    assert informe["turnos"][-1]["ordenes"][0]["autor"] == "alfa"


def test_puesto_responsable_segun_la_unidad_y_la_orden(db_session):
    esc = _escenario(db_session)
    caza = _unidad(db_session, esc, nombre="Caza", tipo="aerea", clase="caza")
    conv = _unidad(db_session, esc, nombre="Convoy", clase="transporte")
    radar = _unidad(db_session, esc, nombre="Radar", clase="radar")
    base = _unidad(db_session, esc, nombre="Base", tipo="base", clase="base_aerea")
    for u, tipo in ((caza, "mover"), (conv, "mover"), (radar, "mover"), (base, "despegar")):
        _orden(db_session, esc, u, tipo, waypoints=[[1, 1]])
    rub = aar.construir_rubrica(db_session, esc)
    pu = rub["bandos"]["azul"]["puestos"]
    assert {p: pu[p]["ordenes"]["emitidas"] for p in pu} == {
        "inteligencia": 1, "operaciones": 1, "logistica": 1, "planificacion": 1}
    assert rub["bandos"]["azul"]["ordenes"]["pendientes"] == 4
    assert rub["bandos"]["azul"]["observaciones"] == ["Sin observaciones destacables."]


def test_la_rubrica_respeta_los_permisos_y_va_en_la_exportacion_y_el_html(api):
    prof, base, *_ = _jugar(api)
    for nombre in ("alfa", "bravo"):
        assert api(nombre).get(f"{base}/aar/rubrica").status_code == 403
    assert api("obs").get(f"{base}/aar/rubrica").status_code == 200
    assert api().get(f"{base}/aar/rubrica").status_code == 401
    exportado = prof.get(f"{base}/exportar").json()
    assert exportado["rubrica"]["bandos"]["azul"]["ordenes"]["rechazadas"] == 2
    html = prof.get(f"{base}/aar.html").text
    assert "Rubrica de evaluacion" in html and "Objetivo fuera de alcance (2)" in html
    assert "Turnos pasivos" in html and "A5 · Planificacion" in html
    assert "revisar la apreciacion de distancias" in html
    assert "Evaluacion por alumno" in html and "<td>alfa</td>" in html and "<td>bravo</td>" in html
    assert "rechazada(s) de alfa" in html
    assert "<td>alfa</td>" in prof.get(f"{base}/aar/diapositivas.html").text
    r = prof.get(f"{base}/aar/rubrica.csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    filas = list(csv.DictReader(io.StringIO(r.text)))
    assert [(f["alumno"], f["bando"], f["puesto"], f["ordenes_emitidas"], f["ordenes_rechazadas"], f["turnos_pasivos"])
            for f in filas] == [("alfa", "azul", "EM", "3", "2", "0"), ("bravo", "rojo", "EM", "1", "0", "2")]
    assert api("alfa").get(f"{base}/aar/rubrica.csv").status_code == 403
    prof.post(f"{base}/finalizar")
    assert api("alfa").get(f"{base}/aar/rubrica").status_code == 200
    assert api("alfa").get(f"{base}/aar/rubrica.csv").status_code == 200


def test_rubrica_html_escapa_nombres(api):
    prof, base, a, r1, r2 = _preparar(api)
    prof.patch(f"{base}/unidades/{a['id']}", json={"nombre": "<b>A</b>", "municion": 5})
    prof.post(f"{base}/avanzar_turno")
    html = prof.get(f"{base}/aar.html").text
    assert "&lt;b&gt;A&lt;/b&gt; (municion 5 %" in html and "<b>A</b> (municion" not in html
