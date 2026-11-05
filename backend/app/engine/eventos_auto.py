"""Eventos automaticos del director (Cóndor): reglas «cuando pasa esto, hacer aquello» que el motor evalua solo.

Cada regla tiene un disparador y una o mas acciones:
- disparadores: una unidad entra a un area (un poligono; de un bando o una unidad concreta), llega una hora del
  ejercicio, se destruye una unidad, o se cumple (o falla) un objetivo;
- acciones: enviar un mensaje a un bando o a todos, hacer aparecer unidades, cambiar el clima, dar (o quitar) puntos,
  pausar el reloj y hacer que un lanzador tire una salva de misiles (de crucero o balísticos) contra una unidad: un
  ataque programado por el director, que no exige que el bando del lanzador vea al blanco.
Las unidades y los objetivos se nombran por su nombre (no por su numero): asi las reglas sirven tambien al guardar el
escenario como plantilla y crear otro desde ella. Una regla se dispara una vez, salvo que se marque «repetir» (la de
la hora, entonces, todos los dias; la del area, cada vez que una unidad entra).
Se guardan en el escenario (Escenario.eventos_auto_json: {"reglas": [...], "puntos": [...]}); los puntos otorgados
suman en el marcador (engine/objetivos.py).
"""

from __future__ import annotations

import json

from app.engine import catalogo, clima as clima_mod
from app.engine import zonas as zonas_mod

DISPARADORES = {"entra_area": "Una unidad entra a un área", "hora": "Llega una hora del ejercicio",
                "destruida": "Se destruye una unidad", "objetivo": "Se cumple o falla un objetivo"}
ACCIONES = {"mensaje": "Enviar un mensaje", "aparecer": "Hacer aparecer unidades", "clima": "Cambiar el clima",
            "puntos": "Dar o quitar puntos", "pausar": "Pausar el reloj", "lanzar": "Lanzar misiles",
            "retirar": "Retirar un bando", "finalizar": "Terminar el ejercicio", "ordenar": "Dar una orden"}
# ordenes que puede dar un evento (reproduccion de operaciones historicas, engine/historicas.py)
ORDENES_PROGRAMADAS = ("mover", "atacar", "patrullar", "aterrizar", "despegar", "lanzar", "interferir")
ESPERA_ATAQUE_S = 1800.0  # una orden de regreso espera a que termine el ataque en curso (hasta 30 minutos)
BANDOS_FILTRO = ("cualquiera", "azul", "rojo", "neutral")
MAX_REGLAS = 50
MAX_ACCIONES = 6
MAX_APARECER = 12
MAX_MISILES = 4
REMITENTE = "Director"  # firma de los mensajes automaticos en el chat


def config(esc) -> dict:
    try:
        d = json.loads(getattr(esc, "eventos_auto_json", None) or "{}")
    except ValueError:
        d = {}
    if not isinstance(d, dict):
        d = {}
    d.setdefault("reglas", [])
    d.setdefault("puntos", [])
    return d


def guardar(esc, d: dict) -> None:
    esc.eventos_auto_json = json.dumps(d, ensure_ascii=False) if d.get("reglas") or d.get("puntos") else None


def _hora_min(texto: str) -> int | None:
    try:
        h, m = str(texto).split(":")
        h, m = int(h), int(m)
    except (ValueError, AttributeError):
        return None
    return h * 60 + m if 0 <= h < 24 and 0 <= m < 60 else None


def validar(reglas: list) -> list[str]:
    """Problemas de una lista de reglas (vacia si estan bien)."""
    errores = []
    if not isinstance(reglas, list) or len(reglas) > MAX_REGLAS:
        return [f"Hasta {MAX_REGLAS} reglas."]
    for i, r in enumerate(reglas, 1):
        if not isinstance(r, dict):
            errores.append(f"Regla {i}: mal formada.")
            continue
        d = r.get("disparador") or {}
        tipo = d.get("tipo")
        if tipo not in DISPARADORES:
            errores.append(f"Regla {i}: elija qué la dispara.")
        elif tipo == "entra_area":
            if zonas_mod.error_de_poligono([tuple(p) for p in d.get("area") or []]):
                errores.append(f"Regla {i}: elija el área (una zona dibujada en el mapa).")
            if d.get("bando", "cualquiera") not in BANDOS_FILTRO:
                errores.append(f"Regla {i}: bando no válido.")
        elif tipo == "hora" and _hora_min(d.get("hora")) is None:
            errores.append(f"Regla {i}: la hora va como HH:MM.")
        elif tipo == "destruida" and not str(d.get("unidad") or "").strip():
            errores.append(f"Regla {i}: elija la unidad.")
        elif tipo == "objetivo" and (not str(d.get("objetivo") or "").strip() or d.get("estado", "cumplido") not in ("cumplido", "fallido")):
            errores.append(f"Regla {i}: elija el objetivo y si se cumple o falla.")
        acciones = r.get("acciones") or []
        if not acciones or len(acciones) > MAX_ACCIONES:
            errores.append(f"Regla {i}: entre 1 y {MAX_ACCIONES} acciones.")
        for a in acciones:
            t = (a or {}).get("tipo")
            if t not in ACCIONES:
                errores.append(f"Regla {i}: acción desconocida.")
            elif t == "mensaje" and (not str(a.get("texto") or "").strip() or a.get("para") not in ("azul", "rojo", "todos")):
                errores.append(f"Regla {i}: el mensaje necesita texto y destinatario.")
            elif t == "aparecer" and (a.get("clase") not in catalogo.CLASES or a.get("bando") not in ("azul", "rojo", "neutral")
                                      or not 1 <= int(a.get("cantidad") or 0) <= MAX_APARECER
                                      or a.get("lat") is None or a.get("lon") is None):
                errores.append(f"Regla {i}: para hacer aparecer unidades elija bando, clase, cantidad (1 a {MAX_APARECER}) y el punto.")
            elif t == "clima" and a.get("clima") not in clima_mod.CLIMAS:
                errores.append(f"Regla {i}: clima no válido.")
            elif t == "puntos" and (a.get("bando") not in ("azul", "rojo") or not isinstance(a.get("puntos"), int)):
                errores.append(f"Regla {i}: puntos para Azul o Rojo (un número entero).")
            elif t == "lanzar" and (not str(a.get("unidad") or "").strip() or not str(a.get("blanco") or "").strip()
                                    or not isinstance(a.get("misiles"), int) or not 1 <= a["misiles"] <= MAX_MISILES):
                errores.append(f"Regla {i}: para lanzar elija el lanzador, el blanco y de 1 a {MAX_MISILES} misiles.")
            elif t == "retirar" and a.get("bando") not in ("azul", "rojo"):
                errores.append(f"Regla {i}: elija el bando que se retira.")
            elif t == "ordenar":
                errores += [f"Regla {i}: {e}" for e in _error_de_orden(a)]
    return errores


def normalizar(reglas: list, previas: list) -> list:
    """Las reglas que guarda el director, conservando cuantas veces ya se disparo cada una (por su id)."""
    disparos = {r.get("id"): int(r.get("disparos") or 0) for r in previas}
    salida = []
    usados = set()
    for i, r in enumerate(reglas, 1):
        rid = str(r.get("id") or "").strip()[:20] or f"r{i}"
        while rid in usados:
            rid += "x"
        usados.add(rid)
        salida.append({"id": rid, "nombre": str(r.get("nombre") or f"Regla {i}").strip()[:80], "activo": bool(r.get("activo", True)),
                       "repetir": bool(r.get("repetir")), "disparador": r["disparador"], "acciones": r["acciones"],
                       "disparos": disparos.get(rid, 0)})
    return salida


# ---------------------------------------------------------------------------------------------------- en vivo
def _unidad(ctx, nombre: str):
    nombre = (nombre or "").strip()
    return next((u for u in ctx.lista if u.nombre == nombre), None)


def _cumple(ctx, r: dict, dentro_previo: set, dentro_ahora: set) -> list:
    """Unidades (o [None]) por las que la regla se dispara ahora; [] si no."""
    d = r["disparador"]
    tipo = d["tipo"]
    if tipo == "hora":
        objetivo = _hora_min(d["hora"])
        inicio = ctx.esc.hora_inicio_min or 0
        primera = ((objetivo - inicio) % 1440) * 60.0  # primer momento del ejercicio con esa hora
        if ctx.t < primera:
            return []
        veces = 1 + int((ctx.t - primera) // 86400) if r.get("repetir") else 1
        return [None] if r.get("disparos", 0) < veces else []
    if tipo == "destruida":
        u = _unidad(ctx, d["unidad"])
        return [u] if u is not None and u.estado == "destruida" else []
    if tipo == "objetivo":
        from app.models.objetivo import Objetivo

        o = ctx.db.query(Objetivo).filter(Objetivo.escenario_id == ctx.esc.id, Objetivo.nombre == d["objetivo"]).first()
        return [None] if o is not None and o.estado == d.get("estado", "cumplido") else []
    # entra_area: las unidades que no estaban y ahora estan
    nuevas = [uid for (rid, uid) in dentro_ahora if rid == r["id"] and (rid, uid) not in dentro_previo]
    return [ctx.unidades[uid] for uid in nuevas if uid in ctx.unidades]


def _dentro(ctx, r: dict) -> set:
    d = r["disparador"]
    poligono = [tuple(p) for p in d["area"]]
    bando, nombre = d.get("bando", "cualquiera"), (d.get("unidad") or "").strip()
    return {(r["id"], u.id) for u in ctx.lista
            if u.estado == "activa" and u.tipo != "base" and not getattr(u, "transporte_id", None)
            and (bando == "cualquiera" or u.bando == bando) and (not nombre or u.nombre == nombre)
            and zonas_mod.dentro(u.lat, u.lon, poligono)}


def evaluar(ctx) -> None:
    """Revisa las reglas activas y cumple las acciones de las que se dispararon (desde tiempo_real._subpaso)."""
    d = config(ctx.esc)
    reglas = d["reglas"]
    if not reglas:
        return
    cambio = _pendientes(ctx, d)
    m = ctx.mundo
    previo = m.eventos_dentro
    ahora = set()
    for r in reglas:
        if r.get("activo", True) and r["disparador"]["tipo"] == "entra_area":
            ahora |= _dentro(ctx, r)
    if not m.eventos_listo:  # recien arrancado: lo que ya esta adentro no cuenta como entrada
        m.eventos_dentro, m.eventos_listo = ahora, True
        previo = ahora
    for r in reglas:
        if not r.get("activo", True) or (r.get("disparos", 0) and not r.get("repetir")):
            continue
        por = _cumple(ctx, r, previo, ahora)
        if not por:
            continue
        for u in (por if r["disparador"]["tipo"] == "entra_area" and r.get("repetir") else por[:1]):
            _actuar(ctx, d, r, u)
            r["disparos"] = r.get("disparos", 0) + 1
            cambio = True
    m.eventos_dentro = ahora
    if cambio or d.get("pendientes"):
        guardar(ctx.esc, d)
        ctx.informe.cambios = True


def _actuar(ctx, d: dict, r: dict, quien) -> None:
    from app.engine.tiempo_real import hora_del_dia

    motivo = f"Evento «{r['nombre']}»" + (f" ({quien.nombre})" if quien is not None else "")
    ctx.evento("direccion", "instructor", f"{motivo} disparado.")  # solo lo ve el director
    for a in r["acciones"]:
        t = a["tipo"]
        if t == "mensaje":
            ctx.evento("mensaje", a["para"], a["texto"].strip())
            ctx.alerta("evento", a["para"], a["texto"].strip(), quien.lat if quien else None, quien.lon if quien else None)
            mensaje_al_chat(ctx, a["para"], a["texto"].strip())
        elif t == "aparecer":
            nuevas = aparecer(ctx, a)
            if nuevas:
                ctx.evento("direccion", a["bando"], f"Se incorporan al ejercicio: {', '.join(u.nombre for u in nuevas)}.",
                           nuevas[0].lat, nuevas[0].lon)
        elif t == "clima":
            ctx.esc.clima = a["clima"]
            ctx.clima = clima_mod.contexto(ctx.db, ctx.esc) if ctx.esc.efectos_clima else ctx.clima
            ctx.evento("clima", "todos", f"El clima cambió a {a['clima']}.")
        elif t == "puntos":
            d["puntos"].append({"bando": a["bando"], "puntos": int(a["puntos"]), "turno": ctx.esc.turno_actual,
                                "regla": r["nombre"], "hora": hora_del_dia(ctx.esc)})
            signo = "+" if a["puntos"] >= 0 else ""
            ctx.evento("direccion", a["bando"], f"{motivo}: {signo}{a['puntos']} puntos.")
        elif t == "lanzar":
            lanzar(ctx, a, motivo)
        elif t == "retirar":
            retirar(ctx, a["bando"])
        elif t == "finalizar":
            ctx.fin = f"{motivo}: el ejercicio terminó."
        elif t == "ordenar":
            if ordenar(ctx, a, motivo) == "espera":  # termina antes el ataque en curso
                d.setdefault("pendientes", []).append({"accion": a, "motivo": motivo, "desde": ctx.t})
        elif t == "pausar":
            alerta = {"causa": "evento", "bando": "todos", "nivel": "aviso", "lat": None, "lon": None,
                      "texto": f"[{hora_del_dia(ctx.esc)}] {motivo}: el reloj se detiene.", "sim_segundos": ctx.t}
            ctx.informe.alertas.append(alerta)
            if ctx.pausa is None:
                ctx.pausa = alerta


def aparecer(ctx, a: dict) -> list:
    """Crea las unidades de la accion «aparecer» (con los datos de su clase) junto al punto elegido."""
    from app.models.unidad import Unidad

    clase = catalogo.CLASES[a["clase"]]
    n = max(1, min(MAX_APARECER, int(a.get("cantidad") or 1)))
    base = (a.get("nombre") or clase.nombre).strip()[:100]
    nuevas = []
    for i in range(n):
        lat = float(a["lat"]) + 0.01 * (i // 4)
        lon = float(a["lon"]) + 0.01 * (i % 4)
        u = Unidad(escenario_id=ctx.esc.id, nombre=base if n == 1 else f"{base} {i + 1}", bando=a["bando"], tipo=clase.tipo,
                   clase=clase.id, echelon=clase.escalon, lat=lat, lon=lon, fuerza=100.0, velocidad_kmh=clase.velocidad_kmh,
                   alcance_km=clase.alcance_km, deteccion_km=clase.deteccion_km, autonomia_km=clase.autonomia_km,
                   carga=clase.carga_max, sidc=catalogo.generar_sidc(a["bando"], clase), estado="activa")
        ctx.db.add(u)
        ctx.db.flush()
        ctx.unidades[u.id] = u
        ctx.lista.append(u)
        nuevas.append(u)
    return nuevas


def _pendientes(ctx, d: dict) -> bool:
    """Ordenes de regreso que esperaban el fin de un ataque: se dan cuando el ataque termino (o vencio la espera)."""
    quedan, cambio = [], False
    for p in d.get("pendientes") or []:
        u = _unidad(ctx, p["accion"]["unidad"])
        previa = ctx.orden_de(u) if u is not None else None
        if u is not None and previa is not None and previa.tipo == "atacar" and ctx.t - p["desde"] < ESPERA_ATAQUE_S:
            quedan.append(p)
            continue
        ordenar(ctx, {**p["accion"], "forzar": True}, p["motivo"])
        cambio = True
    if cambio:
        d["pendientes"] = quedan
        guardar(ctx.esc, d)
    return cambio


def _error_de_orden(a: dict) -> list[str]:
    orden = a.get("orden")
    if orden not in ORDENES_PROGRAMADAS:
        return [f"orden no válida (posibles: {', '.join(ORDENES_PROGRAMADAS)})."]
    if not str(a.get("unidad") or "").strip():
        return ["elija la unidad que recibe la orden."]
    if orden in ("atacar", "aterrizar", "lanzar") and not str(a.get("blanco") or "").strip():
        return ["elija el blanco (o la base, para aterrizar)."]
    if orden in ("mover", "patrullar", "interferir"):
        puntos = a.get("waypoints") or []
        if not puntos or not all(isinstance(p, (list, tuple)) and len(p) == 2 for p in puntos):
            return ["marque la ruta (uno o más puntos)."]
    if orden == "lanzar" and not 1 <= int(a.get("misiles") or 0) <= MAX_MISILES:
        return [f"de 1 a {MAX_MISILES} misiles."]
    return []


def ordenar(ctx, a: dict, motivo: str) -> bool:
    """Orden programada (cronologia de una operacion real): pasa por el motor como la de un alumno, pero sin exigir
    que su bando vea al blanco (los blancos de una operacion planificada se conocen de antemano)."""
    from app.engine import misiles
    from app.engine.tiempo_real import aplicar_orden
    from app.models.orden import Orden

    u = _unidad(ctx, a["unidad"])
    if u is None or u.estado != "activa":
        ctx.evento("direccion", "instructor", f"{motivo}: {a['unidad']} ya no está en servicio; no se dio la orden.")
        return False
    tipo = a["orden"]
    if tipo == "lanzar":
        return lanzar(ctx, {"unidad": a["unidad"], "blanco": a["blanco"], "misiles": int(a.get("misiles") or 1)}, motivo)
    blanco = _unidad(ctx, a.get("blanco") or "") if a.get("blanco") else None
    if tipo in ("atacar", "aterrizar") and (blanco is None or blanco.estado != "activa"):
        ctx.evento("direccion", "instructor", f"{motivo}: {a.get('blanco')} ya no está; {u.nombre} no recibió la orden.")
        return False
    if tipo == "despegar" and not u.en_tierra:
        return False
    previa = ctx.orden_de(u)
    if (previa is not None and previa.tipo == "atacar" and tipo in ("mover", "aterrizar", "patrullar")
            and not a.get("forzar")):
        return "espera"
    if a.get("carga"):  # la carga de armamento de la mision (engine/armas.py), sacada de su base si esta en tierra
        from app.engine import armas as armas_mod

        if armas_mod.aplica(u):
            armas_mod.armar(u, a["carga"], ctx.unidades.get(u.base_id) if u.en_tierra and u.base_id else None)
    detalle = misiles.codificar(int(a.get("misiles") or 1)) if tipo == "lanzar" else ""
    puntos = [list(p) for p in (a.get("waypoints") or [])]
    if tipo == "interferir" and puntos:
        detalle = ""
    orden = Orden(escenario_id=ctx.esc.id, unidad_id=u.id, tipo=tipo, waypoints_json=json.dumps(puntos),
                  objetivo_unidad_id=blanco.id if blanco is not None else None, detalle=detalle,
                  turno_emitida=ctx.esc.turno_actual)
    ctx.db.add(orden)
    ctx.db.flush()
    if previa is not None and previa.id != orden.id:
        ctx.terminar(previa, u, "Reemplazada por la orden siguiente de la cronología.", "cancelada")
    aplicar_orden(ctx.db, ctx.esc, orden, u)
    ctx.db.flush()
    ctx.releer()
    return True


def retirar(ctx, bando: str) -> None:
    """El bando se retira: el adversario automatico deja de conducirlo, sus aeronaves en vuelo vuelven a la base mas
    cercana, las demas unidades dejan lo que hacian y sus objetivos pendientes se cierran (los de proteger se cumplen
    si la unidad sigue viva; los demas, fallan)."""
    from app.engine import aeronaves as aeronaves_mod
    from app.engine.tiempo_real import _regresar
    from app.models.evento import Evento
    from app.models.objetivo import Objetivo

    setattr(ctx.esc, f"ia_{bando}", False)
    for u in list(ctx.lista):
        if u.bando != bando or u.estado != "activa" or getattr(u, "transporte_id", None) or catalogo.es_misil(u):
            continue
        orden = ctx.orden_de(u)
        if u.tipo == "aerea" and not u.en_tierra:
            if orden is not None and orden.tipo == "aterrizar":
                continue  # ya vuelve
            base = aeronaves_mod.base_mas_cercana(u, ctx.lista)
            if base is not None:
                _regresar(ctx, u, orden, base, "retirada", f"{u.nombre} se retira a {base.nombre}.")
                continue
        if orden is not None:
            ctx.terminar(orden, u, "Cancelada: el bando se retira.", "cancelada")
    unidades = {u.id: u for u in ctx.lista}
    for o in ctx.db.query(Objetivo).filter(Objetivo.escenario_id == ctx.esc.id, Objetivo.bando == bando,
                                           Objetivo.estado == "pendiente"):
        viva = o.unidad_id in unidades and unidades[o.unidad_id].estado != "destruida"
        o.estado = "cumplido" if o.tipo == "proteger" and viva else "fallido"
        o.turno_resuelto = ctx.esc.turno_actual
        palabra = "cumplido" if o.estado == "cumplido" else "fallido"
        ctx.db.add(Evento(escenario_id=ctx.esc.id, turno=ctx.esc.turno_actual, sim_segundos=ctx.t, tipo="objetivo",
                          bando_destino=bando, descripcion=f"Objetivo {palabra} al retirarse: {o.nombre}"
                          + (f" (+{o.puntos} puntos)" if o.estado == "cumplido" and o.puntos else "")))
    nombre = "Azul" if bando == "azul" else "Rojo"
    ctx.evento("direccion", "todos", f"El bando {nombre} se retira: deja de atacar y sus aeronaves vuelven a sus bases.")
    ctx.alerta("evento", "todos", f"El bando {nombre} se retira.", None, None)
    ctx.informe.cambios = True


def mensaje_al_chat(ctx, para: str, texto: str) -> None:
    """El mensaje queda tambien en Comunicaciones (la red del bando o la difusion), firmado por el director."""
    from app.models.mensaje import Mensaje

    m = Mensaje(escenario_id=ctx.esc.id, canal=para, remitente_id=None, remitente_nombre=REMITENTE,
                remitente_rol="instructor", texto=texto, turno=ctx.esc.turno_actual)
    ctx.db.add(m)
    ctx.db.flush()
    ctx.informe.chats.append(m)


def lanzar(ctx, a: dict, motivo: str) -> bool:
    """La salva de la accion «lanzar»: como la orden del lanzador, sin exigir que su bando vea al blanco."""
    from app.engine import balisticos, misiles
    from app.engine.tiempo_real import aplicar_orden
    from app.models.orden import Orden

    lanzador, blanco = _unidad(ctx, a["unidad"]), _unidad(ctx, a["blanco"])
    n = int(a["misiles"])
    if lanzador is None or blanco is None:
        error = "no existe el lanzador o el blanco."
    else:
        error = (balisticos.error_de_lanzamiento(lanzador, blanco, n) if balisticos.lanza(lanzador)
                 else misiles.error_de_lanzamiento(lanzador, blanco, n))
    if error:
        ctx.evento("direccion", "instructor", f"{motivo}: no se pudo lanzar ({error})")
        return False
    orden = Orden(escenario_id=ctx.esc.id, unidad_id=lanzador.id, tipo="lanzar", waypoints_json="[]",
                  objetivo_unidad_id=blanco.id, detalle=misiles.codificar(n), turno_emitida=ctx.esc.turno_actual)
    ctx.db.add(orden)
    ctx.db.flush()
    aplicar_orden(ctx.db, ctx.esc, orden, lanzador)
    ctx.db.flush()
    ctx.releer()  # los misiles vuelan desde este mismo paso
    return True


def puntos_de(esc, hasta_turno: int | None = None) -> dict[str, int]:
    """Puntos que dieron (o quitaron) los eventos automaticos a cada bando (hasta esa hora, si se indica)."""
    salida = {"azul": 0, "rojo": 0}
    for p in config(esc)["puntos"]:
        if p.get("bando") in salida and (hasta_turno is None or int(p.get("turno") or 0) <= hasta_turno):
            salida[p["bando"]] += int(p.get("puntos") or 0)
    return salida
