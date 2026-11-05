"""Genera las operaciones historicas del Condor (reproduccion educativa) a partir de sus fichas de investigacion.

Cada ficha (backend/data/historicas/<id>.json) reune, con fuentes abiertas citadas, las unidades, las posiciones
(aproximadas cuando no se conocen), los blancos, la cronologia hora por hora y el resultado real de una operacion.
Esta herramienta la traduce a una plantilla del sistema (backend/data/plantillas_sistema/historica_<id>.json):

  - cada paso de la cronologia es un evento automatico a su hora: un mensaje que explica lo que paso y, si
    corresponde, la orden programada (despegar, mover, atacar, lanzar, aterrizar) a la unidad que lo hizo;
  - a la hora de fin, el bando que ejecuto la operacion se retira y el ejercicio termina;
  - los blancos son objetivos «destruir» del bando que ataca (los no logrados quedan como fallidos al retirarse);
  - la ficha historica (fecha, resumen, resultado real, incertidumbres y fuentes) viaja con el escenario: el informe
    la muestra junto a lo que resulto en el simulador.

Nadie da ordenes en una reproduccion (routers/ordenes.py): los bandos siguen la cronologia y las defensas reaccionan
solas (fuego automatico). Uso:

    backend\\venv\\Scripts\\python tools/crear_operaciones_historicas.py          # todas las fichas
    backend\\venv\\Scripts\\python tools/crear_operaciones_historicas.py opera_1981
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "backend"))

from app.engine import catalogo, eventos_auto, geo, plantillas  # noqa: E402

FICHAS = RAIZ / "backend" / "data" / "historicas"
SALIDA = RAIZ / "backend" / "data" / "plantillas_sistema"
ORDENES = {"despegar", "mover", "atacar", "lanzar", "reabastecer", "aterrizar", "mensaje"}
ESPERA_KM = 80.0  # un avion que va hacia el blanco que atacara despues espera a esta distancia, fuera de sus defensas


def _con_espera(cronologia: list, unidades: dict) -> None:
    """Si un avion vuela hacia el blanco que atacara mas tarde, lo deja esperando a ESPERA_KM (no da vueltas sobre las
    defensas enemigas hasta la hora del ataque): el ataque programado lo lleva desde ahi."""
    for i, paso in enumerate(cronologia):
        u = unidades.get(paso.get("unidad"))
        destino = (paso.get("ruta") or [None])[-1] or paso.get("destino")
        if u is None or destino is None or paso.get("accion") not in ("despegar", "mover"):
            continue
        if catalogo.CLASES[u["clase"]].tipo != "aerea" or u["clase"] in ("helicoptero", "helicoptero_artillado"):
            continue
        ataque = next((p for p in cronologia[i + 1:] if p.get("unidad") == u["nombre"] and p.get("accion") in ("atacar", "lanzar")), None)
        blanco = unidades.get((ataque or {}).get("blanco"))
        if blanco is None or geo.distancia_km(destino[0], destino[1], blanco["lat"], blanco["lon"]) > 20:
            continue
        previo = (paso.get("ruta") or [None, None])[-2] if len(paso.get("ruta") or []) >= 2 else [u["lat"], u["lon"]]
        lat, lon = geo.avanzar_hacia(blanco["lat"], blanco["lon"], previo[0], previo[1], ESPERA_KM)
        espera = [round(lat, 4), round(lon, 4)]
        if paso.get("ruta"):
            paso["ruta"] = paso["ruta"][:-1] + [espera]
        else:
            paso["destino"] = espera


def _minutos(hora: str) -> int:
    h, m = hora.split(":")
    return int(h) * 60 + int(m)


def _texto(paso: dict) -> str:
    return f"{paso['hora']} · {paso['texto'].strip()}"


def _orden(paso: dict, unidades: dict) -> dict | None:
    """La orden programada de un paso de la cronologia (None si el paso solo se narra)."""
    nombre = paso.get("unidad")
    u = unidades.get(nombre)
    if u is None:
        return None
    accion = paso.get("accion")
    ruta = paso.get("ruta") or ([paso["destino"]] if paso.get("destino") else [])
    ruta = [[round(float(p[0]), 4), round(float(p[1]), 4)] for p in ruta]
    blanco = paso.get("blanco")
    if accion in ("despegar", "mover", "reabastecer"):
        if ruta:
            return {"tipo": "ordenar", "unidad": nombre, "orden": "mover", "waypoints": ruta}
        if accion == "despegar" and u.get("en_tierra_en"):
            return {"tipo": "ordenar", "unidad": nombre, "orden": "despegar"}
        return None
    if accion == "atacar" and blanco in unidades:
        return {"tipo": "ordenar", "unidad": nombre, "orden": "atacar", "blanco": blanco}
    if accion == "lanzar" and blanco in unidades and catalogo.CLASES[u["clase"]].tipo == "aerea":
        # un misil lanzado desde un avion (Exocet, HARM...) es el ataque de ese avion con sus armas
        return {"tipo": "ordenar", "unidad": nombre, "orden": "atacar", "blanco": blanco}
    if accion == "lanzar" and blanco in unidades:
        return {"tipo": "ordenar", "unidad": nombre, "orden": "lanzar", "blanco": blanco,
                "misiles": max(1, min(eventos_auto.MAX_MISILES, int(paso.get("misiles") or 2)))}
    if accion == "aterrizar":
        base = blanco if blanco in unidades else u.get("en_tierra_en")
        if base in unidades:
            return {"tipo": "ordenar", "unidad": nombre, "orden": "aterrizar", "blanco": base}
    return None


def construir(ficha: dict) -> dict:
    """La plantilla del sistema (dict, el formato de plantillas.desde_dict) de una ficha historica."""
    unidades = {u["nombre"]: u for u in ficha["unidades"]}
    errores = []
    filas = []
    for u in ficha["unidades"]:
        if u.get("modelo") in catalogo.MODELOS:
            u["clase"] = catalogo.MODELOS[u["modelo"]].clase  # la clase la manda el modelo del catalogo
        clase = u["clase"]
        if clase not in catalogo.CLASES:
            errores.append(f"clase desconocida: {clase} ({u['nombre']})")
            continue
        modelo = u.get("modelo") or ""
        if modelo and (modelo not in catalogo.MODELOS or catalogo.MODELOS[modelo].clase != clase):
            errores.append(f"modelo {modelo} no existe o no es de la clase {clase} ({u['nombre']})")
            modelo = ""
        base = u.get("en_tierra_en")
        filas.append({"nombre": u["nombre"], "bando": u["bando"], "clase": clase, "lat": float(u["lat"]), "lon": float(u["lon"]),
                      "modelo": modelo, "aeronaves": max(1, min(catalogo.MAX_AERONAVES_GRUPO, int(u.get("aeronaves") or 1))),
                      "en_tierra": bool(base), "base": base, "perfil_vuelo": u.get("perfil")})
    if errores:
        raise SystemExit(f"{ficha['id']}: " + "; ".join(errores))

    inicio, fin = _minutos(ficha["hora_inicio"]), _minutos(ficha["hora_fin"])
    cronologia = sorted(ficha["cronologia"], key=lambda p: (_minutos(p["hora"]) - inicio) % 1440)
    _con_espera(cronologia, unidades)
    reglas = []
    armadas = set()  # la carga de la mision va con la primera orden de cada grupo
    for i, paso in enumerate(cronologia, 1):
        if paso.get("accion") not in ORDENES:
            raise SystemExit(f"{ficha['id']}: accion desconocida en {paso['hora']}: {paso.get('accion')}")
        acciones = [{"tipo": "mensaje", "para": "todos", "texto": _texto(paso)[:500]}]
        orden = _orden(paso, unidades)
        if orden is not None:
            carga = unidades[orden["unidad"]].get("carga")
            if carga and orden["unidad"] not in armadas and orden["orden"] != "lanzar":
                orden["carga"] = carga
                armadas.add(orden["unidad"])
            acciones.append(orden)
        reglas.append({"id": f"h{i:02d}", "nombre": f"{paso['hora']} · {paso['texto'][:60]}", "activo": True, "repetir": False,
                       "disparador": {"tipo": "hora", "hora": paso["hora"]}, "acciones": acciones})
    atacante = "rojo"
    reglas.append({"id": "fin", "nombre": f"{ficha['hora_fin']} · fin de la operación", "activo": True, "repetir": False,
                   "disparador": {"tipo": "hora", "hora": ficha["hora_fin"]},
                   "acciones": [{"tipo": "mensaje", "para": "todos",
                                 "texto": f"{ficha['hora_fin']} · Fin de la operación. Compare en el Informe lo que resultó "
                                          "en el simulador con lo que pasó en la realidad."},
                                {"tipo": "retirar", "bando": atacante}, {"tipo": "finalizar"}]})
    problemas = eventos_auto.validar(reglas)
    if problemas:
        raise SystemExit(f"{ficha['id']}: " + "; ".join(problemas))

    objetivos, vistos = [], set()
    for b in ficha.get("blancos") or []:
        blanco = unidades.get(b["unidad"])
        if (blanco is not None and b["unidad"] not in vistos and blanco["bando"] != atacante
                and catalogo.CLASES[blanco["clase"]].tipo != "aerea"):  # los derribos no son objetivos
            vistos.add(b["unidad"])
            # neutralizar: dejarlo al 50 % o menos (una pasada rara vez destruye una instalacion)
            objetivos.append({"bando": atacante, "tipo": "neutralizar", "nombre": f"Neutralizar {b['unidad']}"[:80],
                              "puntos": 10, "unidad": b["unidad"]})

    real = ficha["resultado_real"]
    historia = {"fecha": ficha["fecha"], "zona_horaria": ficha.get("zona_horaria", ""), "resumen": ficha["resumen"],
                "contexto": ficha.get("contexto", ""), "resultado_real": real,
                "incertidumbres": ficha.get("incertidumbres") or [], "fuentes": ficha.get("fuentes") or []}
    descripcion = (f"{ficha['resumen']} Reproducción histórica: las unidades siguen solas la cronología real "
                   f"({ficha['hora_inicio']} a {ficha['hora_fin']}, {ficha.get('zona_horaria', 'hora local')}) y nadie da "
                   "órdenes; las defensas reaccionan solas. Al final, el informe compara el resultado con lo que pasó. "
                   "Posiciones y cifras aproximadas según fuentes abiertas (ver el informe).")
    return {
        "id": f"historica_{ficha['id']}", "nombre": ficha["nombre"], "descripcion": descripcion[:plantillas.LARGO_MAX_DESCRIPCION],
        "origen": "codigo", "clima": ficha.get("clima", "despejado"), "hora_inicio_min": inicio,
        "nacion_azul": ficha.get("nacion_azul", ""), "nacion_rojo": ficha.get("nacion_rojo", ""),
        "dia_noche": True, "ia_azul": False, "ia_rojo": False, "fecha_inicio": ficha["fecha"],
        "unidades": filas, "objetivos": objetivos, "eventos_auto": reglas, "historia": historia,
    }


def main() -> int:
    elegidas = set(sys.argv[1:])
    hechas = 0
    for archivo in sorted(FICHAS.glob("*.json")):
        ficha = json.loads(archivo.read_text(encoding="utf-8"))
        if elegidas and ficha["id"] not in elegidas:
            continue
        datos = construir(ficha)
        plantillas.desde_dict(datos)  # valida que el simulador la pueda cargar
        destino = SALIDA / f"{datos['id']}.json"
        destino.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{datos['id']}: {len(datos['unidades'])} unidades, {len(datos['eventos_auto'])} eventos, "
              f"{len(datos['objetivos'])} objetivos -> {destino.relative_to(RAIZ)}")
        hechas += 1
    return 0 if hechas else 1


if __name__ == "__main__":
    sys.exit(main())
