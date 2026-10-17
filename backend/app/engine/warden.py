"""Analisis de sistemas del enemigo con el modelo de los cinco anillos de Warden.

Cada objetivo se ubica en un anillo, del centro hacia afuera:
  1. Liderazgo: mando, control y comunicaciones (centros de comunicaciones, guerra electronica);
  2. Elementos organicos esenciales: energia y combustible (centrales, refinerias, depositos);
  3. Infraestructura: transporte y apoyo (puentes, bases aereas, PRO, puertos);
  4. Poblacion: no es objetivo (la protege el derecho internacional humanitario);
  5. Fuerzas desplegadas: las unidades militares (terrestres, aereas, navales, defensa aerea y radares).
Atacar los anillos interiores produce efectos sobre todo el sistema; los exteriores, efectos locales. El cuadro del
bando cuenta los objetivos enemigos que conoce en cada anillo y su estado.
"""

from __future__ import annotations

NOMBRE = {1: "Anillo 1, liderazgo (mando y control)", 2: "Anillo 2, elementos orgánicos esenciales",
          3: "Anillo 3, infraestructura", 4: "Anillo 4, población", 5: "Anillo 5, fuerzas desplegadas"}
EFECTO = {1: "afecta la conducción de todo el sistema enemigo (órdenes demoradas, menos coordinación)",
          2: "reduce la energía y el combustible del que dependen sus radares, bases y fuerzas",
          3: "corta el transporte y el apoyo: puentes, bases y puertos",
          4: "no es objetivo militar",
          5: "reduce su fuerza de combate en la zona"}
POR_CLASE = {"centro_comunicaciones": 1, "guerra_electronica": 1,
             "termoelectrica": 2, "hidroelectrica": 2, "refineria": 2, "deposito": 2,
             "puente": 3, "base_aerea": 3, "punto_recobre": 3, "puerto": 3}


def anillo(u) -> int:
    return POR_CLASE.get(getattr(u, "clase", None) or "", 5)


def resumen(conocidos: list, bando: str) -> list[dict]:
    """Objetivos enemigos conocidos por anillo: total y cuantos estan degradados, neutralizados o destruidos.
    `conocidos`: [(unidad, se_ve_ahora)]."""
    filas = {a: {"anillo": a, "nombre": NOMBRE[a], "efecto": EFECTO[a], "objetivos": 0, "degradados": 0,
                 "neutralizados": 0, "destruidos": 0, "sin_noticias": 0, "ejemplos": []} for a in (1, 2, 3, 5)}
    for u, visto in conocidos:
        if u.bando == bando:
            continue
        f = filas[anillo(u)]
        f["objetivos"] += 1
        if len(f["ejemplos"]) < 4:
            f["ejemplos"].append(u.nombre)
        if not visto:
            f["sin_noticias"] += 1
        elif u.estado == "destruida" or (u.fuerza or 0) <= 0:
            f["destruidos"] += 1
        elif u.fuerza < 30:
            f["neutralizados"] += 1
        elif u.fuerza < 70:
            f["degradados"] += 1
    return list(filas.values())
