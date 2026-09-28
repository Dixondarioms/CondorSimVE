"""Crea un escenario de demostracion en Venezuela (piedemonte andino / Llanos).

    python -m app.crear_demo

Ambos bandos empiezan sin verse: hay que explorar (la aviacion detecta mas lejos)
y el terreno (montana, bosque) frena el avance y oculta a las unidades.
"""

from app.db import SessionLocal, init_db
from app.engine import catalogo
from app.models.escenario import Escenario
from app.models.unidad import Unidad

UNIDADES = [
    # nombre, bando, clase, lat, lon, escalon
    ("1ra Brigada de Infanteria", "azul", "infanteria", 8.60, -70.60, "brigada"),
    ("Grupo Blindado A", "azul", "blindado", 8.62, -70.45, "batallon"),
    ("Artilleria de Campana A", "azul", "artilleria", 8.60, -70.55, "batallon"),
    ("Ala de Caza 1", "azul", "caza", 8.70, -70.40, ""),
    ("Base Aerea Barinas", "azul", "base_aerea", 8.62, -70.21, ""),
    ("Batallon de Montana R", "rojo", "infanteria", 8.60, -70.85, "batallon"),
    ("Compania de Fusileros R", "rojo", "infanteria", 8.75, -70.95, "compania"),
    ("Escuadrilla R", "rojo", "caza", 8.80, -71.20, ""),
    ("Deposito R Merida", "rojo", "deposito", 8.59, -71.14, ""),
]


def main() -> None:
    init_db()
    with SessionLocal() as db:
        esc = Escenario(nombre="Demo: Piedemonte andino - Llanos")
        db.add(esc)
        db.flush()
        for nombre, bando, clase_id, lat, lon, escalon in UNIDADES:
            c = catalogo.CLASES[clase_id]
            db.add(Unidad(
                escenario_id=esc.id, nombre=nombre, bando=bando, tipo=c.tipo, clase=c.id,
                echelon=escalon or c.escalon, lat=lat, lon=lon, velocidad_kmh=c.velocidad_kmh,
                alcance_km=c.alcance_km, deteccion_km=c.deteccion_km, autonomia_km=c.autonomia_km,
                sidc=catalogo.generar_sidc(bando, c, escalon),
            ))
        db.commit()
        print(f"Escenario {esc.id} creado con {len(UNIDADES)} unidades.")


if __name__ == "__main__":
    main()
