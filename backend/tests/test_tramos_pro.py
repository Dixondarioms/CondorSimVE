"""Un PRO con pista solo va en un tramo de carretera apto o en un aerodromo (engine/tramos_pro.py, tools/preparar_tramos_pro.py)."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

from app.engine import plataformas, recobre
from app.engine import tramos_pro as tp

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "tools"))
import preparar_tramos_pro  # noqa: E402

CARACAS = (10.5000, -66.9150)  # centro de la ciudad: sin tramos rectos aptos
MAIQUETIA = (10.6031, -66.9906)  # aeropuerto de 3.520 m


def _tramo_largo():
    d = json.loads((tp.GEO / "venezuela" / "tramos_pro.geojson").read_text(encoding="utf-8"))
    f = max(d["features"], key=lambda f: f["properties"]["largo_m"])
    (lon1, lat1), (lon2, lat2) = f["geometry"]["coordinates"]
    return (lat1 + lat2) / 2, (lon1 + lon2) / 2, f["properties"]


def _pro(lat, lon, pista_m):
    return SimpleNamespace(id=1, nombre="PRO", clase="punto_recobre", tipo="base", bando="azul", estado="activa",
                           fuerza=100.0, personal=None, lat=lat, lon=lon, pista_m=pista_m, existencias_json=None,
                           combustible=100.0, municion=100.0, stock_combustible=400.0, stock_municion=400.0)


def test_los_tramos_cumplen_los_minimos():
    d = json.loads((tp.GEO / "venezuela" / "tramos_pro.geojson").read_text(encoding="utf-8"))
    c = d["criterios"]
    assert len(d["features"]) > 100
    for f in d["features"]:
        p = f["properties"]
        assert p["largo_m"] >= c["largo_minimo_m"] and p["ancho_m"] >= c["ancho_minimo_m"]
        assert p["pendiente_pct"] <= c["pendiente_max_pct"]


def test_sobre_un_tramo_apto_si_y_lejos_de_el_no():
    lat, lon, p = _tramo_largo()
    tipo, t, _ = tp.sitio(lat, lon, 2000)
    assert tipo == "tramo" and t["id"] == p["id"]
    # una pista mas larga que el tramo no cabe: lo dice y sugiere bajarla
    tipo, _, motivo = tp.sitio(lat, lon, p["largo_m"] + 500)
    assert tipo == "no_apto" and "es más corto" in motivo
    tipo, _, motivo = tp.sitio(*CARACAS, 1500)
    assert tipo == "no_apto" and "tramo de carretera apto" in motivo and "ORI" not in motivo
    if plataformas._indice_aerodromos():  # planos de los aerodromos instalados (datos de mapa, fuera del repositorio)
        assert tp.sitio(*MAIQUETIA, 3000)[0] == "aerodromo"
    assert tp.sitio(*CARACAS, 0)[0] == "sin_pista"  # sin pista (helicopteros) va en cualquier sitio
    assert tp.sitio(0.0, 0.0, 1500)[0] == "sin_datos"  # sin carreteras cargadas no se puede verificar


def test_fuera_de_un_ori_la_pista_del_pro_no_sirve():
    lat, lon, _ = _tramo_largo()
    bien, mal = _pro(lat, lon, 2000), _pro(*CARACAS, 2000)
    assert plataformas.largo_pista(bien) == 2000 and plataformas.largo_pista(mal) == 0
    assert "no tiene pista" in plataformas.error_de_pista(plataformas.catalogo.MODELOS["f16"], mal)
    assert any("Pista no apta" in x for x in recobre.deficiencias(mal))
    assert not any("Pista" in x for x in recobre.deficiencias(bien))
    assert recobre.sitio_texto(bien).startswith("Tramo ") and recobre.sitio_texto(mal) == ""


def test_api_no_deja_poner_un_pro_con_pista_en_cualquier_sitio(api):
    prof = api("prof")
    esc = prof.post("/api/escenarios", json={"nombre": "Tramos PRO"}).json()
    ruta = f"/api/escenarios/{esc['id']}/unidades"
    pro = dict(nombre="PRO 1", bando="azul", clase="punto_recobre", lat=CARACAS[0], lon=CARACAS[1], pista_m=1500)
    r = prof.post(ruta, json=pro)
    assert r.status_code == 400 and "tramo de carretera apto" in r.json()["detail"]
    lat, lon, _ = _tramo_largo()
    r = prof.post(ruta, json={**pro, "lat": lat, "lon": lon})
    assert r.status_code == 200, r.text
    assert r.json()["pista_largo_m"] == 1500
    # moverlo fuera del tramo con la pista puesta tampoco
    assert prof.patch(f"{ruta}/{r.json()['id']}", json={"lat": CARACAS[0], "lon": CARACAS[1]}).status_code == 400
    # sin pista (solo helicopteros) va en cualquier sitio
    r = prof.post(ruta, json={**pro, "pista_m": 0})
    assert r.status_code == 200
    assert prof.patch(f"{ruta}/{r.json()['id']}", json={"pista_m": 1200}).status_code == 400
    assert prof.post(ruta, json={**pro, "clase": "infanteria", "tipo": "terrestre"}).status_code == 400  # solo bases y PRO


def test_la_herramienta_separa_lo_recto_y_estima_el_ancho():
    assert preparar_tramos_pro._ancho({"highway": "trunk", "lanes": "2"}) == 12.0
    assert preparar_tramos_pro._ancho({"highway": "primary"}) == 9.0  # 2 canales de 3,5 m y hombrillos de 1 m: angosta
    assert preparar_tramos_pro._ancho({"highway": "primary", "width": "20"}) == 20.0
    assert not preparar_tramos_pro._apta({"highway": "trunk", "bridge": "yes"})
    assert not preparar_tramos_pro._apta({"highway": "trunk", "surface": "unpaved"})
    # 3 km rectos y despues una curva cerrada: un solo tramo recto de ~3 km
    puntos = [(-67.0 + 0.009 * k, 9.0) for k in range(4)] + [(-66.973, 9.01), (-66.973, 9.03)]
    tramos = list(preparar_tramos_pro.rectas(puntos))
    assert tramos and tramos[0][:2] == (0, 3) and 2900 < tramos[0][2] < 3000
