"""Catalogo propio: tipos de unidad que el instructor define desde la consola (orden de batalla de la AMB), sin tocar
el codigo ni reiniciar el servidor.

Cada tipo propio es un `catalogo.Modelo` de una clase existente (la clase da el simbolo APP-6, la movilidad y las
reglas; el tipo, el nombre y los valores de juego). Se guardan en backend/data/modelos_usuario.json (la variable
SIMULADOR_MODELOS_USUARIO cambia el archivo) y se agregan a catalogo.MODELOS con el prefijo "u_" en el id, asi
nunca pisan un modelo del sistema. Al agregar una unidad, el instructor elige el tipo dentro de su clase.
"""

import json
import logging
import os
import re
import unicodedata
from pathlib import Path

from app.engine import catalogo

log = logging.getLogger("uvicorn.error")

RUTA = Path(os.environ.get("SIMULADOR_MODELOS_USUARIO")
            or Path(__file__).resolve().parent.parent.parent / "data" / "modelos_usuario.json")
PREFIJO = "u_"
MAX_TIPOS = 200
# ilustracion por clase para los tipos propios de aeronave (las de los buques salen de las fotos de referencia)
FOTO_CLASE = {
    "caza": "caza_embarcado.svg", "ataque": "ataque_ligero.svg", "helicoptero": "helo_ataque.svg",
    "helicoptero_artillado": "helo_transporte.svg", "avion_ge": "avion_ge.svg",
    "dron_reconocimiento": "dron_reconocimiento.svg", "dron_ataque": "dron_armado.svg",
    "municion_merodeadora": "municion_merodeadora.svg", "alerta_temprana": "e2d.svg", "cisterna": "kc135.svg",
    "misil_crucero": "crucero.svg",
}
LIMITES = {"velocidad_kmh": 3000, "alcance_km": 2000, "deteccion_km": 1000, "autonomia_km": 20000, "defensa": 5.0}


class TipoInvalido(ValueError):
    """Datos de un tipo propio inaceptables (la API lo traduce a 400)."""


def generar_id(nombre: str) -> str:
    plano = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii").lower()
    return PREFIJO + re.sub(r"[^a-z0-9]+", "_", plano).strip("_")[:40]


def _numero(d: dict, campo: str, maximo: float) -> float:
    try:
        v = float(d.get(campo))
    except (TypeError, ValueError):
        raise TipoInvalido(f"{campo}: indique un numero") from None
    if not 0 <= v <= maximo:
        raise TipoInvalido(f"{campo}: debe estar entre 0 y {maximo:g}")
    return v


def construir(d: dict) -> catalogo.Modelo:
    """Valida un tipo propio (dict del JSON o de la API) y lo convierte en un Modelo del catalogo."""
    if not isinstance(d, dict):
        raise TipoInvalido("Tipo mal formado")
    nombre = str(d.get("nombre") or "").strip()
    if not 2 <= len(nombre) <= 80:
        raise TipoInvalido("El nombre debe tener entre 2 y 80 caracteres")
    clase = catalogo.CLASES.get(d.get("clase") or "")
    if clase is None or clase.tipo == "base" or clase.misil:
        raise TipoInvalido("Elija una clase de unidad (no una base ni un misil)")
    ataque = d.get("ataque_vs") or {}
    if not isinstance(ataque, dict):
        raise TipoInvalido("ataque_vs debe ser {terrestre, aerea, naval}")
    atk = {}
    for t in ("terrestre", "aerea", "naval"):
        try:
            atk[t] = float(ataque.get(t, clase.ataque_vs.get(t, 0.0)))
        except (TypeError, ValueError):
            raise TipoInvalido(f"ataque contra {t}: indique un numero") from None
        if not 0 <= atk[t] <= 5:
            raise TipoInvalido(f"ataque contra {t}: debe estar entre 0 y 5")
    id_ = d.get("id") or generar_id(nombre)
    if not re.fullmatch(r"u_[a-z0-9_]{1,40}", id_):
        raise TipoInvalido("Identificador invalido")
    defensa = _numero(d, "defensa", LIMITES["defensa"]) if d.get("defensa") is not None else clase.defensa
    if defensa < 0.05:
        raise TipoInvalido("La defensa debe ser al menos 0,05 (1 = la de una unidad tipica)")
    foto = FOTO_CLASE.get(clase.id)
    return catalogo.Modelo(
        id_, clase.id, nombre, str(d.get("corto") or nombre)[:14], str(d.get("fabricante") or "")[:60] or "-",
        str(d.get("pais") or "")[:40] or "-", str(d.get("funcion") or clase.nombre)[:80],
        str(d.get("descripcion") or "")[:600], str(d.get("armamento") or clase.armamento)[:300],
        _numero(d, "velocidad_kmh", LIMITES["velocidad_kmh"]) if d.get("velocidad_kmh") is not None else clase.velocidad_kmh,
        _numero(d, "alcance_km", LIMITES["alcance_km"]) if d.get("alcance_km") is not None else clase.alcance_km,
        _numero(d, "deteccion_km", LIMITES["deteccion_km"]) if d.get("deteccion_km") is not None else clase.deteccion_km,
        _numero(d, "autonomia_km", LIMITES["autonomia_km"]) if d.get("autonomia_km") is not None else clase.autonomia_km,
        atk,
        defensa,
        f"/static/fotos/{foto}" if foto else "",
        {"autor": "Catálogo propio del instructor", "licencia": "—", "url_licencia": "", "pagina": ""},
    )


def _como_dict(m: catalogo.Modelo) -> dict:
    return {"id": m.id, "clase": m.clase, "nombre": m.nombre, "corto": m.corto, "fabricante": m.fabricante,
            "pais": m.pais, "funcion": m.funcion, "descripcion": m.descripcion, "armamento": m.armamento,
            "velocidad_kmh": m.velocidad_kmh, "alcance_km": m.alcance_km, "deteccion_km": m.deteccion_km,
            "autonomia_km": m.autonomia_km, "ataque_vs": m.ataque_vs, "defensa": m.defensa}


def leer() -> list[catalogo.Modelo]:
    if not RUTA.is_file():
        return []
    try:
        datos = json.loads(RUTA.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        log.warning("modelos_usuario: no se pudo leer %s: %s (se ignora)", RUTA, e)
        return []
    tipos = []
    for d in (datos.get("tipos") or []) if isinstance(datos, dict) else []:
        try:
            tipos.append(construir(d))
        except TipoInvalido as e:
            log.warning("modelos_usuario: tipo %r ignorado: %s", d.get("nombre") if isinstance(d, dict) else d, e)
    return tipos


def aplicar() -> list[str]:
    """Reemplaza en catalogo.MODELOS los tipos propios por los del archivo. Devuelve sus ids."""
    for id_ in [k for k in catalogo.MODELOS if k.startswith(PREFIJO)]:
        del catalogo.MODELOS[id_]
    tipos = leer()
    for m in tipos:
        catalogo.MODELOS[m.id] = m
    return [m.id for m in tipos]


def _escribir(tipos: list[catalogo.Modelo]) -> None:
    RUTA.parent.mkdir(parents=True, exist_ok=True)
    tmp = RUTA.with_suffix(".tmp")
    tmp.write_text(json.dumps({"_comentario": "Catalogo propio del instructor (Consola -> Catalogo propio).",
                               "tipos": [_como_dict(m) for m in tipos]}, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(RUTA)


def guardar(d: dict) -> catalogo.Modelo:
    """Crea o reemplaza (mismo id) un tipo propio y lo deja disponible al instante."""
    nuevo = construir(d)
    tipos = [m for m in leer() if m.id != nuevo.id]
    if len(tipos) >= MAX_TIPOS:
        raise TipoInvalido(f"El catalogo propio admite hasta {MAX_TIPOS} tipos")
    _escribir(tipos + [nuevo])
    aplicar()
    return nuevo


def eliminar(id_: str) -> bool:
    tipos = leer()
    quedan = [m for m in tipos if m.id != id_]
    if len(quedan) == len(tipos):
        return False
    _escribir(quedan)
    aplicar()
    return True


aplicar()
