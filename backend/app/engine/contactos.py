"""Ultimo contacto conocido: cuando una unidad enemiga sale del radio de deteccion,
el bando conserva donde y en que turno se la vio por ultima vez."""

from sqlalchemy.orm import Session

from app.engine import clima as clima_mod
from app.engine import guerra_electronica as ge_mod
from app.engine import catalogo
from app.engine.vision import cuadro_sensores, unidades_visibles
from app.models.contacto import Contacto
from app.models.evento import Evento
from app.models.escenario import Escenario
from app.models.unidad import Unidad
from app.terreno import Terreno, get_terreno

BANDOS = ("azul", "rojo")


MAX_CONTACTOS_POR_AVISO = 4
PERFIL = {"alto": "a cota alta", "medio": "a cota media", "rasante": "rasante"}


def _describir(c: dict) -> str:
    clase = catalogo.obtener(c["clase"], c["tipo"]).nombre.lower()
    perfil = f" {PERFIL[c['perfil']]}" if c.get("perfil") in PERFIL else ""
    return f"{clase}{perfil} a {c['distancia_km']:.0f} km, rumbo {c['rumbo']:03d}°"


def avisar_contactos_nuevos(db: Session, escenario: Escenario, unidades, existentes: dict, terreno, ge) -> None:
    """Cada radar o sensor que detecta un enemigo que su bando no tenia a la vista el turno anterior lo informa al
    bando (evento "radar"): que es, a que distancia, en que rumbo y a que cota. Asi el A-2 y el resto del bando se
    enteran aunque nadie este mirando el mapa."""
    turno = escenario.turno_actual
    clima = clima_mod.contexto(db, escenario)
    for bando in BANDOS:
        ya_avisados: set[int] = set()
        for sensor in cuadro_sensores(unidades, bando, terreno, clima, ge):
            nuevos = []
            for c in sensor["contactos"]:
                previo = existentes.get((bando, c["unidad_id"]))
                if c["unidad_id"] in ya_avisados or (previo is not None and previo.turno_visto >= turno - 1):
                    continue
                ya_avisados.add(c["unidad_id"])
                nuevos.append(c)
            if not nuevos:
                continue
            lista = "; ".join(_describir(c) for c in nuevos[:MAX_CONTACTOS_POR_AVISO])
            if len(nuevos) > MAX_CONTACTOS_POR_AVISO:
                lista += f" y {len(nuevos) - MAX_CONTACTOS_POR_AVISO} más"
            db.add(Evento(
                escenario_id=escenario.id, turno=turno, tipo="radar", bando_destino=bando,
                descripcion=f"{sensor['nombre']} informa {len(nuevos)} contacto(s) nuevo(s): {lista}.",
            ))


def actualizar_contactos(db: Session, escenario: Escenario, terreno: Terreno | None = None) -> None:
    terreno = terreno or get_terreno()
    unidades = db.query(Unidad).filter(Unidad.escenario_id == escenario.id).all()
    por_id = {u.id: u for u in unidades}
    existentes = {
        (c.bando, c.unidad_id): c
        for c in db.query(Contacto).filter(Contacto.escenario_id == escenario.id)
    }

    ge = ge_mod.contexto(db, escenario, en_resolucion=True)  # se llama al cerrar la resolucion del turno
    avisar_contactos_nuevos(db, escenario, unidades, existentes, terreno, ge)
    for bando in BANDOS:
        for u in unidades_visibles(unidades, bando, terreno, clima_mod.contexto(db, escenario), ge):
            if u.bando == bando or u.estado == "destruida":
                continue
            c = existentes.get((bando, u.id))
            if c is None:
                db.add(Contacto(
                    escenario_id=escenario.id, bando=bando, unidad_id=u.id,
                    lat=u.lat, lon=u.lon, turno_visto=escenario.turno_actual,
                ))
            else:
                c.lat, c.lon, c.turno_visto = u.lat, u.lon, escenario.turno_actual

    # Una unidad destruida deja de ser un contacto util.
    for (bando, uid), c in existentes.items():
        u = por_id.get(uid)
        if u is None or u.estado == "destruida":
            db.delete(c)
