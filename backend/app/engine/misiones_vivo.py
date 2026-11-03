"""Misiones aereas planificadas en tiempo real (la planificacion, la validacion y la OTA son las de engine/misiones.py
y engine/ota.py).

En cada paso del motor (engine/tiempo_real.py):
- `activar`: las misiones programadas despegan al comenzar su hora de despegue (o en el acto, si ya paso);
- `avanzar`: cada grupo en mision vuela su ruta en vivo. Los puntos de paso se atraviesan; en una orbita se queda las
  horas indicadas actuando segun su rol (CAP intercepta, CAS ataca lo que ve a su alcance cada pasada, CSAR rescata,
  la cisterna y la alerta temprana trabajan solas); en el blanco ataca (una pasada) y sigue; en un punto de reunion
  espera a los demas grupos del paquete; en un punto de reabastecimiento espera junto a la cisterna hasta llenarse; y
  al final aterriza en su base (o en otra, si esa no lo recibe). La escolta acompaña al grupo escoltado.
Con combustible critico abandona la ruta y regresa a la base propia mas cercana. Una orden directa al grupo reemplaza
la mision (routers/ordenes.py).
"""

import json
from collections import defaultdict

from app.engine import aeronaves as aeronaves_mod
from app.engine import apoyo_aereo, catalogo, geo, ota, relieve
from app.engine import armas as armas_mod
from app.engine import interceptacion as intercep
from app.engine import misiones as mis
from app.engine import tiempo_real as tr
from app.models.mision import Mision

ESPERA_REUNION_MAX_S = ota.ESPERA_REUNION_MAX * 3600.0  # lo que un grupo espera a su paquete en el punto de reunion
ESPERA_CISTERNA_MAX_S = 1800.0  # lo que espera junto a la cisterna en el punto de reabastecimiento
LLENO_PARA_SEGUIR = 95.0  # % de combustible con el que deja el punto de reabastecimiento


def _ahora_turno(ctx) -> int:
    return ctx.esc.turno_actual


def activar(ctx) -> None:
    """Despega (o pone en ruta) las misiones programadas cuya hora de despegue ya empezo."""
    ctx.db.flush()  # la sesion no se vacia sola: sin esto se releeria el estado anterior de las misiones
    hay = ctx.db.query(Mision.id).filter(Mision.escenario_id == ctx.esc.id, Mision.estado == "programada",
                                         Mision.turno_despegue <= tr.turno_de(ctx.t)).first()
    if hay is None:
        return
    antes = set(ctx.unidades)
    mis.activar(ctx.db, ctx.esc, ctx.unidades, ctx.lista, tr.turno_de(ctx.t), defaultdict(int))
    for uid in set(ctx.unidades) - antes:  # grupos nuevos: salen hacia su ruta
        ctx.unidades[uid].rumbo = 0.0
    for m in ctx.db.query(Mision).filter(Mision.escenario_id == ctx.esc.id, Mision.estado == "en_curso",
                                         Mision.espera_hasta.is_(None), Mision.indice == 0):
        u = ctx.unidades.get(m.unidad_id)
        if u is not None:
            tr.cancelar_ordenes_de(ctx.db, u, f"La reemplaza la misión {m.id}.", tr.hora_del_dia(ctx.esc))
    ctx.informe.cambios = True


def _terminar(ctx, m: Mision, estado: str, texto: str) -> None:
    mis._terminar(ctx.db, m, estado, f"[{tr.hora_del_dia(ctx.esc)}] {texto}", _ahora_turno(ctx))
    ctx.alerta("mision", m.bando, f"Misión {m.id} ({m.rol}{' ' + m.nombre if m.nombre else ''}) {estado}: {texto}",
               nivel="info" if estado == "cumplida" else "aviso")
    ctx.informe.cambios = True


def _evento(ctx, m: Mision, texto: str) -> None:
    mis._evento(ctx.db, m, _ahora_turno(ctx), f"[{tr.hora_del_dia(ctx.esc)}] {texto}")
    ctx.informe.cambios = True


def _visible(ctx, x, bando: str) -> bool:
    return ctx.visible_para(x, bando)


def _blanco_automatico(ctx, u, rol_id: str):
    """Enemigo de superficie que su bando ve, al alcance del grupo (SEAD prefiere radares y antiaerea)."""
    clase = catalogo.perfil(u)
    candidatos = [x for x in ctx.lista
                  if x.bando != u.bando and x.estado == "activa" and mis._tipo_efectivo(x) != "aerea"
                  and clase.ataque_vs.get(mis._tipo_efectivo(x), 0.0) > 0
                  and geo.distancia_km(u.lat, u.lon, x.lat, x.lon) <= armas_mod.alcance(u, x) and _visible(ctx, x, u.bando)]
    if rol_id == "SEAD":
        from app.engine import guerra_electronica as ge_mod
        emisores = [x for x in candidatos if ge_mod.emite_radar(x) or ctx.ge.emite(x)]
        candidatos = emisores or candidatos
    return min(candidatos, key=lambda x: geo.distancia_km(u.lat, u.lon, x.lat, x.lon), default=None)


def _orbitar(ctx, u, lat: float, lon: float, patrulla: bool, h: float) -> None:
    u.mision, u.mision_lat, u.mision_lon = ("patrulla" if patrulla else "espera"), lat, lon
    tr._orbitar(ctx, u, h)


def avanzar(ctx, h: float) -> set[int]:
    """Hace volar `h` segundos a cada grupo en mision. Devuelve los ids de los grupos que conduce (el motor no los
    mueve por su cuenta ni los manda a aterrizar por combustible: lo resuelve su mision)."""
    conducidos: set[int] = set()
    ctx.db.flush()
    for m in ctx.db.query(Mision).filter(Mision.escenario_id == ctx.esc.id, Mision.estado == "en_curso").order_by(Mision.id):
        u = ctx.unidades.get(m.unidad_id)
        if u is None or u.estado != "activa":
            if u is not None and catalogo.obtener(u.clase, u.tipo).se_consume and m.indice >= len(mis.puntos_de(m)) - 1:
                _terminar(ctx, m, "cumplida", "La munición merodeadora impactó en su blanco.")
            else:
                _terminar(ctx, m, "fallida", "El grupo fue derribado o se perdió.")
            continue
        if u.orden_id is not None:  # una orden directa la reemplazo (routers/ordenes.py la aborta; por las dudas)
            _terminar(ctx, m, "abortada", "Redirigida por una orden directa.")
            continue
        if u.en_tierra:
            if m.indice > 0 or m.espera_hasta is not None:
                _terminar(ctx, m, "abortada", "El grupo aterrizó antes de completar la ruta.")
            continue
        conducidos.add(u.id)
        try:
            _volar(ctx, m, u, h)
        except Exception:  # noqa: BLE001 - una mision con datos raros no detiene el ejercicio
            tr.log.exception("Mision %s: no se pudo avanzar", m.id)
            _terminar(ctx, m, "abortada", "Error al conducir la misión.")
    return conducidos


def _volar(ctx, m: Mision, u, h: float) -> None:
    pts = mis.puntos_de(m)
    if m.indice >= len(pts):
        _terminar(ctx, m, "cumplida", "Ruta completada.")
        return
    # ---- escolta: acompaña al grupo escoltado mientras su mision siga; luego vuelve a la base ----
    if m.rol == "ESCOLTA" and m.espera != -2:
        if u.combustible > ctx.doctrina(u)["combustible_regreso"] and _escoltar(ctx, m, u, h):
            return
        m.espera = -2
        _evento(ctx, m, "La misión escoltada terminó: regresa a la base.")
    # ---- combustible critico: abandona la ruta y regresa ----
    if (u.combustible <= ctx.doctrina(u)["combustible_regreso"] and pts[-1]["tipo"] == "aterrizaje"
            and len(pts) - m.indice > 1 and not catalogo.obtener(u.clase, u.tipo).se_consume):
        base = aeronaves_mod.base_mas_cercana(u, ctx.lista)
        if base is not None:
            pts = [{"tipo": "aterrizaje", "lat": base.lat, "lon": base.lon, "base_id": base.id}]
            m.puntos_json, m.indice, m.espera, m.espera_hasta = json.dumps(pts), 0, -1, None
            _evento(ctx, m, f"Combustible crítico ({u.combustible:.0f} %): abandona la ruta y regresa a {base.nombre}.")
    p = pts[m.indice]
    # ---- detenido en un punto: orbita, reunion o reabastecimiento ----
    if m.espera_hasta is not None:
        if p["tipo"] == "orbita":
            _en_orbita(ctx, m, u, p, h)
        elif p.get("reunion"):
            _en_reunion(ctx, m, u, p, h)
        elif p.get("reabastecimiento"):
            _en_reabastecimiento(ctx, m, u, p, h)
        else:
            m.espera_hasta = None
        return
    # ---- vuelo hacia el proximo punto de detencion (los puntos de paso se atraviesan) ----
    i0 = j = m.indice
    while j < len(pts) - 1 and pts[j]["tipo"] == "paso" and not pts[j].get("reunion") and not pts[j].get("reabastecimiento"):
        j += 1
    destino = pts[j]
    perfil = next((q.get("perfil") for q in reversed(pts[:i0 + 1]) if q.get("perfil")), None)
    if perfil and perfil in relieve.perfiles_permitidos(u) and u.perfil_vuelo != perfil:
        u.perfil_vuelo = perfil
    objetivo = None
    if destino["tipo"] == "blanco" and destino.get("objetivo_unidad_id"):
        x = ctx.unidades.get(destino["objetivo_unidad_id"])
        if x is not None and x.estado == "activa" and x.bando != u.bando:
            objetivo = x
    wps = [[q["lat"], q["lon"]] for q in pts[i0:j + 1]]
    if objetivo is not None and _visible(ctx, objetivo, u.bando):
        wps[-1] = [objetivo.lat, objetivo.lon]  # el blanco se movio y se lo sigue viendo: se lo persigue
        if m.rol == "INTERCEPCION" and i0 == j:  # punteria adelantada: hacia donde estara el blanco
            ve, vn = intercep.velocidad_de(objetivo)
            plat, plon, _ = intercep.punto_de_mira(u.lat, u.lon, u.velocidad_kmh, objetivo.lat, objetivo.lon, ve, vn)
            wps[-1] = [plat, plon]
    if destino["tipo"] == "aterrizaje":
        base = ctx.unidades.get(destino.get("base_id"))
        if base is not None:
            wps[-1] = [base.lat, base.lon]  # un portaaviones se mueve
    u.mision, u.mision_lat, u.mision_lon = "", None, None
    mov = tr._avanzar(ctx, u, wps, h)
    m.indice = i0 + min(mov.alcanzados, len(wps) - 1)
    faltan = geo.distancia_km(u.lat, u.lon, wps[-1][0], wps[-1][1])
    llego = faltan <= mis.LLEGADA_KM
    if destino.get("reabastecimiento"):
        if llego:
            m.indice, m.espera_hasta = j, ctx.t + ESPERA_CISTERNA_MAX_S
            m.resultado = "En el punto de reabastecimiento: espera a la cisterna."
        else:
            m.resultado = f"Vuela al punto de reabastecimiento: faltan {faltan:.0f} km."
    elif destino.get("reunion"):
        if llego:
            m.indice, m.espera_hasta = j, ctx.t + ESPERA_REUNION_MAX_S
            m.resultado = "En el punto de reunión: espera a los demás grupos del paquete."
        else:
            m.resultado = f"Vuela al punto de reunión: faltan {faltan:.0f} km."
    elif destino["tipo"] == "orbita":
        if llego:
            horas = int(destino.get("turnos") or 1)
            m.indice, m.espera_hasta, m.espera = j, ctx.t + horas * 3600.0, horas
            m.resultado = f"Llega a la órbita; la mantiene {horas} h."
            if m.rol == "CSAR":
                mis._rescatar(ctx.db, ctx.esc, m, u, _ahora_turno(ctx))
        else:
            m.resultado = f"Vuela hacia la órbita: faltan {faltan:.0f} km."
    elif destino["tipo"] == "blanco" and destino.get("corte"):
        if llego:
            m.indice = j + 1
            m.resultado = mis._cortar_carretera(ctx.db, ctx.esc, m, u, destino, ctx.terreno, _ahora_turno(ctx))
            _evento(ctx, m, m.resultado)
        else:
            m.resultado = f"Vuela al corte de carretera: faltan {faltan:.0f} km."
    elif destino["tipo"] == "blanco":
        en_alcance = objetivo is not None and geo.distancia_km(u.lat, u.lon, objetivo.lat, objetivo.lon) <= armas_mod.alcance(u, objetivo)
        if m.rol == "INTERCEPCION":
            if objetivo is None or not intercep.tipo_blanco(objetivo):
                m.indice = j + 1
                m.resultado = "El blanco de la interceptación ya no está en vuelo o a flote: regresa."
                _evento(ctx, m, m.resultado)
                return
            # con las armas restringidas se lo identifica a la vista antes de tirar (sigue el curso hasta tenerlo cerca)
            estado = ctx.doctrina(u)[intercep.dominio(objetivo)]
            if en_alcance and ctx.esc.niebla and estado == "restringido" and not ctx.identificado(u.bando, objetivo):
                m.resultado = f"Se acerca a {objetivo.nombre} para identificarlo antes de tirar."
                return
            if not en_alcance and llego and not _visible(ctx, objetivo, u.bando):
                m.indice = j + 1
                m.resultado = f"No encontró a {objetivo.nombre} en el punto de encuentro: sigue la ruta."
                _evento(ctx, m, m.resultado)
                return
            if not en_alcance:
                m.resultado = f"Vuela al punto de encuentro con {objetivo.nombre}: faltan {faltan:.0f} km."
                return
        if en_alcance or llego:
            m.indice = j + 1
            blanco = objetivo if en_alcance else _blanco_automatico(ctx, u, m.rol)
            if blanco is not None:
                tr._pasada(ctx, u, blanco, None, tr.RECARGA_PASADA_S)
                m.resultado = f"Atacó a {blanco.nombre}."
                if catalogo.obtener(u.clase, u.tipo).se_consume:
                    u.estado, u.fuerza = "destruida", 0.0
                    _terminar(ctx, m, "cumplida", f"La munición merodeadora impactó en {blanco.nombre}.")
            else:
                m.resultado = "Llega al blanco pero no encuentra enemigos a su alcance."
                _evento(ctx, m, m.resultado)
        else:
            m.resultado = f"Vuela hacia el blanco: faltan {faltan:.0f} km."
    elif destino["tipo"] == "aterrizaje":
        base = ctx.unidades.get(destino.get("base_id"))
        if base is not None and geo.distancia_km(u.lat, u.lon, base.lat, base.lon) <= aeronaves_mod.RADIO_ATERRIZAJE_KM:
            motivo = aeronaves_mod.error_de_aterrizaje(u, base, ctx.lista)
            if motivo is None:
                aeronaves_mod.aterrizar(u, base, len(aeronaves_mod.estacionadas(base, ctx.lista)))
                u.espera_hasta = ctx.t + u.espera_restante * 3600.0
                m.indice = len(pts)
                _terminar(ctx, m, "cumplida", f"Misión cumplida: aterrizó en {base.nombre}.")
            else:
                otra = aeronaves_mod.base_mas_cercana(u, ctx.lista)
                if otra is not None and otra is not base:
                    pts[j] = {"tipo": "aterrizaje", "lat": otra.lat, "lon": otra.lon, "base_id": otra.id}
                    m.puntos_json = json.dumps(pts)
                    m.resultado = f"{motivo} Se desvía a {otra.nombre}."
                    _evento(ctx, m, m.resultado)
                else:
                    _terminar(ctx, m, "abortada", f"{motivo} No hay otra base disponible.")
        elif base is None:
            _terminar(ctx, m, "abortada", "La base de aterrizaje ya no existe.")
        else:
            m.resultado = f"Regresa a {base.nombre}: faltan {faltan:.0f} km."


def _en_orbita(ctx, m: Mision, u, p: dict, h: float) -> None:
    _orbitar(ctx, u, p["lat"], p["lon"], m.rol == "CAP", h)
    if m.rol == "CAS" and not (u.recarga_hasta and u.recarga_hasta > ctx.t) and u.municion > 0:
        blanco = _blanco_automatico(ctx, u, "CAS")
        if blanco is not None:
            tr._pasada(ctx, u, blanco, None, tr.RECARGA_PASADA_S)
    elif m.rol == "CSAR":
        mis._rescatar(ctx.db, ctx.esc, m, u, _ahora_turno(ctx))
    falta = m.espera_hasta - ctx.t
    if falta <= 0:
        m.indice, m.espera, m.espera_hasta = m.indice + 1, -1, None
        m.resultado = "Termina la órbita y sigue la ruta."
    else:
        m.espera = max(1, int(-(-falta // 3600)))
        m.resultado = f"En órbita: {int(falta // 60)} min más."


def _en_reunion(ctx, m: Mision, u, p: dict, h: float) -> None:
    _orbitar(ctx, u, p["lat"], p["lon"], False, h)
    if mis._reunion_completa(ctx.db, m, m.indice, ctx.unidades):
        m.indice, m.espera_hasta = m.indice + 1, None
        m.resultado = "Paquete reunido: sigue la ruta."
        _evento(ctx, m, "El paquete se reunió en el punto de reunión y sigue la ruta.")
    elif ctx.t >= m.espera_hasta:
        m.indice, m.espera_hasta = m.indice + 1, None
        m.resultado = "No se completó la reunión: sigue la ruta sin los demás grupos."
        _evento(ctx, m, m.resultado)


def _en_reabastecimiento(ctx, m: Mision, u, p: dict, h: float) -> None:
    _orbitar(ctx, u, p["lat"], p["lon"], False, h)
    hay = any(apoyo_aereo.es_cisterna(x) and x.bando == u.bando and apoyo_aereo.en_vuelo(x)
              and geo.distancia_km(x.lat, x.lon, u.lat, u.lon) <= catalogo.obtener(x.clase, x.tipo).nodo_movil_km
              for x in ctx.lista)
    if u.combustible >= LLENO_PARA_SEGUIR or ctx.t >= m.espera_hasta:
        lleno = u.combustible >= LLENO_PARA_SEGUIR
        m.indice, m.espera_hasta = m.indice + 1, None
        m.resultado = "Reabastecido: sigue la ruta." if lleno else "Sin reabastecer: sigue la ruta."
        if not lleno:
            _evento(ctx, m, "No se completó el reabastecimiento en vuelo" + ("" if hay else " (no había una cisterna "
                                                                          "propia a su alcance)") + ": sigue la ruta.")
    else:
        m.resultado = ("Junto a la cisterna: se reabastece." if hay
                       else "En el punto de reabastecimiento, pero no hay una cisterna propia a su alcance.")


def _escoltar(ctx, m: Mision, u, h: float) -> bool:
    """Se coloca junto al grupo escoltado y patrulla alli (intercepta lo que lo amenace). False si la mision escoltada
    termino o no existe: el escolta sigue su propia ruta (el aterrizaje)."""
    e = ctx.db.get(Mision, mis.escolta_de(m) or -1)
    if e is None or e.escenario_id != m.escenario_id or e.estado not in mis.ACTIVAS:
        return False
    escoltado = ctx.unidades.get(e.unidad_id) if e.unidad_id else None
    if e.estado == "programada" or escoltado is None or escoltado.estado != "activa" or escoltado.en_tierra:
        _orbitar(ctx, u, u.mision_lat if u.mision == "patrulla" and u.mision_lat is not None else u.lat,
                 u.mision_lon if u.mision == "patrulla" and u.mision_lon is not None else u.lon, True, h)
        m.resultado = f"Espera en el aire al grupo de {e.nombre or e.rol}."
        return True
    d = geo.distancia_km(u.lat, u.lon, escoltado.lat, escoltado.lon)
    if d > mis.RADIO_ESCOLTA_KM:
        u.mision, u.mision_lat, u.mision_lon = "", None, None
        tr._avanzar(ctx, u, [[escoltado.lat, escoltado.lon]], h)
        d = geo.distancia_km(u.lat, u.lon, escoltado.lat, escoltado.lon)
    else:  # vuela junto al escoltado, con su rumbo
        u.lat, u.lon = geo.destino(escoltado.lat, escoltado.lon, ((escoltado.rumbo or 0.0) + 135.0) % 360.0, 3.0)
        u.rumbo = escoltado.rumbo
        ctx.mundo.movio_en[u.id] = ctx.t + h
        tr._cambiar(ctx, u, "combustible", u.combustible - aeronaves_mod.combustible_loiter(u) * h / 3600.0, "escolta")
    u.mision, u.mision_lat, u.mision_lon = "patrulla", u.lat, u.lon  # intercepta lo que amenace al grupo
    m.resultado = (f"Escolta a {escoltado.nombre} ({d:.0f} km)." if d <= mis.RADIO_ESCOLTA_KM
                   else f"Alcanza a {escoltado.nombre}: faltan {d:.0f} km.")
    return True
