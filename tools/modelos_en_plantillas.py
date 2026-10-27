"""Pone a cada unidad de las plantillas del sistema el modelo real que le corresponde por su nombre
(backend/app/engine/modelo_por_nombre.py): por ejemplo, «A-29 Super Tucano 1 (Hotel)» pasa a ser un A-29.

    backend\\venv\\Scripts\\python tools\\modelos_en_plantillas.py
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "backend"))

from app.engine import catalogo  # noqa: E402
from app.engine.modelo_por_nombre import modelo_para  # noqa: E402

CARPETA = RAIZ / "backend" / "data" / "plantillas_sistema"


def aplicar(plantilla: dict) -> int:
    """Corrige los modelos de las unidades de una plantilla (dict). Devuelve cuantas cambio."""
    cambios = 0
    for u in plantilla["unidades"]:
        actual = u.get("modelo") or None
        nombre_actual = catalogo.MODELOS[actual].nombre if actual in catalogo.MODELOS else None
        nuevo = modelo_para(u["clase"], u["nombre"], actual, nombre_actual)
        if nuevo:
            u["modelo"] = nuevo
            u.setdefault("aeronaves", 1)
            cambios += 1
    return cambios


def main():
    for ruta in sorted(CARPETA.glob("*.json")):
        p = json.loads(ruta.read_text(encoding="utf-8"))
        n = aplicar(p)
        if n:
            ruta.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{ruta.name}: {n} unidades con su modelo real")


if __name__ == "__main__":
    main()
