"""Doctrina y reglas de enfrentamiento del Cóndor (como en los simuladores de mando modernos).

Cada bando tiene su doctrina y cada unidad puede tener la suya; lo que la unidad no fija, lo hereda de su bando:

- armas_aire / armas_superficie (estado de las armas contra aeronaves y contra unidades de superficie):
    libre        tira solo contra cualquier enemigo detectado a su alcance;
    restringido  tira solo contra enemigos identificados (engine/contactos_vivo.py);
    retenido     no tira por su cuenta: solo con una orden de ataque.
  Por defecto, aire libre y superficie retenido (como el SIETE: patrullas y antiaerea tiran solas; en tierra y en el
  mar, solo con orden). Con superficie libre o restringido, una unidad sin orden tira contra lo que tiene a su alcance.
- disparos_por_blanco: misiles por salva de la defensa aerea (0 = segun el arma: 1 de lejos, la salva completa de cerca).
- distancia_pct: a que fraccion de su alcance maximo abre fuego (100, 75 o 50 %): mas cerca, mas probable el impacto.
- combustible_regreso: % de combustible con el que una aeronave deja lo que hace y vuelve a la base (bingo).
- regreso_sin_armas: una aeronave que agoto su armamento vuelve sola a la base (winchester).
"""

import json

ESTADOS_ARMAS = ("libre", "restringido", "retenido")
DEFECTO = {"armas_aire": "libre", "armas_superficie": "retenido", "disparos_por_blanco": 0, "distancia_pct": 100,
           "combustible_regreso": 25, "regreso_sin_armas": True}
VALORES = {
    "armas_aire": ESTADOS_ARMAS,
    "armas_superficie": ESTADOS_ARMAS,
    "disparos_por_blanco": (0, 1, 2, 4),
    "distancia_pct": (50, 75, 100),
    "combustible_regreso": (20, 25, 30, 40, 50),
    "regreso_sin_armas": (True, False),
}
NOMBRES = {"libre": "libre", "restringido": "restringido (solo identificados)", "retenido": "retenido (solo con orden)"}


def _cargar(texto) -> dict:
    try:
        d = json.loads(texto or "{}")
    except ValueError:
        return {}
    return d if isinstance(d, dict) else {}


def errores(cambios: dict, admite_nulos: bool = False) -> list[str]:
    """Problemas de un cambio de doctrina (claves o valores desconocidos); con `admite_nulos`, None = heredar."""
    salida = []
    for k, v in cambios.items():
        if k not in VALORES:
            salida.append(f"Campo de doctrina desconocido: {k}")
        elif v is None and admite_nulos:
            continue
        elif v not in VALORES[k] or (isinstance(v, bool) != isinstance(VALORES[k][0], bool)):
            salida.append(f"Valor no válido para {k}: {v!r}")
    return salida


def de_bando(esc, bando: str) -> dict:
    d = dict(DEFECTO)
    d.update({k: v for k, v in _cargar(getattr(esc, "doctrina_json", None)).get(bando, {}).items() if k in DEFECTO})
    return d


def propia(u) -> dict:
    """Lo que fija la unidad (sin lo heredado)."""
    return {k: v for k, v in _cargar(getattr(u, "doctrina_json", None)).items() if k in DEFECTO and v is not None}


def de_unidad(esc, u) -> dict:
    d = de_bando(esc, u.bando)
    d.update(propia(u))
    return d


def fijar_bando(esc, bando: str, cambios: dict) -> dict:
    todo = _cargar(getattr(esc, "doctrina_json", None))
    actual = {k: v for k, v in todo.get(bando, {}).items() if k in DEFECTO}
    actual.update(cambios)
    todo[bando] = actual
    esc.doctrina_json = json.dumps(todo, sort_keys=True)
    return de_bando(esc, bando)


def fijar_unidad(u, cambios: dict) -> dict:
    """Cambia la doctrina propia de la unidad; un valor None vuelve a heredar el del bando."""
    actual = propia(u)
    for k, v in cambios.items():
        if v is None:
            actual.pop(k, None)
        else:
            actual[k] = v
    u.doctrina_json = json.dumps(actual, sort_keys=True) if actual else None
    return actual


def texto(d: dict) -> str:
    """Resumen legible de una doctrina."""
    disparos = "según el arma" if not d["disparos_por_blanco"] else f"{d['disparos_por_blanco']} por blanco"
    return (f"Contra aeronaves: {NOMBRES[d['armas_aire']]}; contra superficie: {NOMBRES[d['armas_superficie']]}; "
            f"misiles: {disparos}; abre fuego al {d['distancia_pct']} % del alcance; regresa con "
            f"{d['combustible_regreso']} % de combustible" + ("; vuelve sin armamento." if d["regreso_sin_armas"] else "."))
