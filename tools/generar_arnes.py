"""Genera el arnes de pruebas visuales de la interfaz: frontend/static/pruebas/arnes.html.

El arnes ejecuta el app.js REAL en el navegador contra un servidor simulado (fetch y WebSocket falsos con datos de
ejemplo), asi se puede revisar y probar toda la interfaz (graficos, chat, videowall, linea de tiempo...) sin
iniciar sesion ni tocar la base de datos. Hay que regenerarlo si cambia index.html o el catalogo de unidades:

    backend\\venv\\Scripts\\python tools/generar_arnes.py

Abrir  http://localhost:8000/static/pruebas/arnes.html?rol=instructor  (rol = instructor | azul | rojo | observador)
Para un alumno se puede agregar &puesto=comandante|jem|a1|a2|a3|a3da|a4|ce.
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "backend"))

from app.engine import catalogo, misiones, modelos_usuario, plantillas  # noqa: E402

# tipos del catalogo propio de ejemplo (Consola -> Catalogo propio), solo en el arnes
TIPOS_PROPIOS = [
    {"nombre": "Buk-M2E", "corto": "Buk-M2E", "clase": "antiaerea", "pais": "Rusia",
     "descripcion": "Sistema antiaéreo de alcance medio (ejemplo del catálogo propio).", "alcance_km": 45, "deteccion_km": 100},
    {"nombre": "VN-16 (Infantería de Marina)", "corto": "VN-16", "clase": "blindado", "pais": "China",
     "descripcion": "Vehículo anfibio de asalto (ejemplo del catálogo propio)."},
]

DESTINO = RAIZ / "frontend" / "static" / "pruebas"


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    clases = []
    for c in catalogo.CLASES.values():
        d = catalogo.como_dict(c)
        d["sidc_azul"] = catalogo.generar_sidc("azul", c)
        d["sidc_rojo"] = catalogo.generar_sidc("rojo", c)
        clases.append(d)
    (DESTINO / "catalogo.json").write_text(
        json.dumps({"clases": clases, "escalones": [e for e in catalogo.ESCALONES if e],
                    "climas": ["despejado", "nublado", "lluvia", "tormenta"],
                    "misiones": misiones.roles_publicos(),
                    "modelos": [catalogo.modelo_dict(m) for m in catalogo.MODELOS.values() if not m.id.startswith("u_")]
                    + [catalogo.modelo_dict(modelos_usuario.construir(t)) for t in TIPOS_PROPIOS],
                    # plantillas del sistema (las mismas que GET /api/plantillas)
                    "plantillas": [plantillas.plantilla_dict(p) for p in plantillas.PLANTILLAS.values()],
                    "aeronaves": {"max_grupo": catalogo.MAX_AERONAVES_GRUPO, "max_bando": catalogo.MAX_AERONAVES_BANDO,
                                  "max_drones": catalogo.MAX_DRONES_BANDO}},
                   ensure_ascii=False),
        encoding="utf-8")

    html = (RAIZ / "frontend" / "index.html").read_text(encoding="utf-8")
    marca = '<script src="/static/js/app.js"></script>'
    if marca not in html:
        raise SystemExit("index.html ya no carga /static/js/app.js: actualice el generador")
    html = html.replace(marca, '<script src="/static/pruebas/arnes.js"></script>\n  ' + marca)
    html = html.replace("<title>Simulador Fénix</title>", "<title>Simulador Fénix - ARNÉS DE PRUEBAS (datos simulados)</title>")
    (DESTINO / "arnes.html").write_text(html, encoding="utf-8")
    print(f"Arnes generado en {DESTINO} ({len(clases)} clases de unidad)")


if __name__ == "__main__":
    main()
