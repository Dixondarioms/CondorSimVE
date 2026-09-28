"""Ultimo contacto conocido: cuando una unidad enemiga sale del radio de deteccion,
el bando conserva donde y en que turno se la vio por ultima vez."""

from sqlalchemy.orm import Session

from app.engine.vision import unidades_visibles
from app.models.contacto import Contacto
from app.models.escenario import Escenario
from app.models.unidad import Unidad
from app.terreno import Terreno, get_terreno

BANDOS = ("azul", "rojo")


def actualizar_contactos(db: Session, escenario: Escenario, terreno: Terreno | None = None) -> None:
    terreno = terreno or get_terreno()
    unidades = db.query(Unidad).filter(Unidad.escenario_id == escenario.id).all()
    por_id = {u.id: u for u in unidades}
    existentes = {
        (c.bando, c.unidad_id): c
        for c in db.query(Contacto).filter(Contacto.escenario_id == escenario.id)
    }

    for bando in BANDOS:
        for u in unidades_visibles(unidades, bando, terreno, escenario.clima):
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
