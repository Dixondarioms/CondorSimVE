"""Mistral, RBS 70 y S-300VM (engine/defensa_aerea.py) y su apresto (Anexo A.16), y el apresto de los buques (A.22)."""

import json
import math
from types import SimpleNamespace

from app.engine import apresto, catalogo, toe
from app.engine import defensa_aerea as da
from tests.test_defensa_aerea_sistemas import _bateria, _blanco


def test_los_sistemas_nuevos_estan_en_el_catalogo():
    for modelo, clase in (("mistral", "antiaerea_portatil"), ("rbs70", "antiaerea"), ("s300vm", "antiaerea")):
        s, m = da.SISTEMAS[modelo], catalogo.MODELOS[modelo]
        assert m.clase == clase and m.alcance_km == max(a.alcance_max_km for a in s.armas)
        # la ilustracion propia o, si se descargo, la foto de referencia (tools/fotos/fotos_referencia.py)
        assert m.foto in (f"/static/fotos/{modelo}.svg", f"/static/fotos/ref_{modelo}.jpg") and s.personal > 0
    assert da.SISTEMAS["mistral"].radar_vigilancia_km == 0  # no emite
    assert da.SISTEMAS["s300vm"].arma("9m82me").alcance_max_km == 200


def test_el_s300_bate_a_200_km_y_el_buk_no():
    lejos = _blanco(1, 170, altura=8000.0)
    s300 = da.enfrentar(_bateria("s300vm"), [lejos], se_movio=False, radar_ok=True, interferida=False, noche=False)
    assert s300.disparos and s300.disparos[0].arma.id == "9m82me"
    buk = da.enfrentar(_bateria("buk_m2e"), [_blanco(1, 170, altura=8000.0)], se_movio=False, radar_ok=True,
                       interferida=False, noche=False)
    assert buk.disparos == []


def test_el_rbs70_guiado_por_laser_no_sufre_la_interferencia_de_radar():
    blanco = _blanco(1, 5, altura=1000.0)
    libre = da.pk_efectivo(da.SISTEMAS["rbs70"].armas[0], blanco["unidad"], interferida=False, noche=False,
                           tripulada=False, firma=1.0, altura_m=1000.0)[0]
    interf = da.pk_efectivo(da.SISTEMAS["rbs70"].armas[0], blanco["unidad"], interferida=True, noche=False,
                            tripulada=False, firma=1.0, altura_m=1000.0)[0]
    assert libre == interf
    radar = da.SISTEMAS["s300vm"].armas[0]
    assert da.pk_efectivo(radar, blanco["unidad"], interferida=True, noche=False, tripulada=False, firma=1.0,
                          altura_m=1000.0)[0] < radar.pk
    # con el radar de tiro apagado, el RBS 70 (sin radar de tiro) y el Mistral siguen tirando
    res = da.enfrentar(_bateria("rbs70"), [_blanco(2, 5, altura=1000.0)], se_movio=False, radar_ok=False,
                       interferida=True, noche=False)
    assert res.disparos and res.disparos[0].arma.tipo == "misil_laser"


def test_el_mistral_no_alcanza_la_cota_alta():
    res = da.enfrentar(_bateria("mistral"), [_blanco(1, 4, altura=6000.0)], se_movio=False, radar_ok=True,
                       interferida=False, noche=False)
    assert res.disparos == []


# ---------- apresto (Anexo A.16 y A.22) ----------
class _Esc:
    apresto_json = personal_json = transmisiones_json = None
    turno_actual, fallas = 1, False


def _u(**kw):
    datos = dict(id=1, nombre="U", bando="azul", tipo="terrestre", clase="antiaerea", modelo="", fuerza=100.0,
                 municion=100.0, combustible=100.0, estado="activa", aeronaves=0, personal=None, lat=0.0, lon=0.0,
                 en_tierra=False, cargas_json=None, arma_elegida=None)
    return SimpleNamespace(**{**datos, **kw})


def _calificar(u):
    esc = _Esc()
    return apresto.calificar(u, toe.partes([u], esc, "azul")["unidades"][0], esc, [u], 1)


def test_apresto_de_mistral_s300_y_rbs70():
    for modelo, texto in (("mistral", "Instalaciones de lanzamiento"), ("s300vm", "Rampas de lanzamiento"),
                          ("rbs70", "Radares e instalaciones")):
        clase = catalogo.MODELOS[modelo].clase
        assert _calificar(_u(clase=clase, modelo=modelo))["tiene"]
        r = _calificar(_u(clase=clase, modelo=modelo, fuerza=70.0))
        assert not r["tiene"] and any(texto in m for m in r["motivos"]), (modelo, r["motivos"])


def test_apresto_de_los_buques():
    fragata = _u(tipo="naval", clase="fragata")
    r = _calificar(fragata)
    assert r["tipo"] == "buque" and r["tiene"]
    r = _calificar(_u(tipo="naval", clase="fragata", combustible=90.0))
    assert any("Cargas líquidas" in m for m in r["motivos"])
    r = _calificar(_u(tipo="naval", clase="patrullero", municion=95.0))  # el 100 % de la dotacion de guerra
    assert any("Dotación de guerra" in m for m in r["motivos"])
    assert json.dumps(r)


def test_disciplina_de_fuego_del_s300():
    """Una salva por aeronave en el turno, un misil por salva lejos y una reserva para la autodefensa."""
    b = _bateria("s300vm")
    lejos = _blanco(1, 170, n=4, altura=8000.0)
    [d] = da.enfrentar(b, [lejos], se_movio=False, radar_ok=True, interferida=False, noche=False).disparos
    assert d.salvas <= 4 and d.misiles == d.salvas  # lejos: 1 misil por salva, sin "rematar" al grupo
    cerca = da.enfrentar(_bateria("s300vm"), [_blanco(2, 40, n=2, altura=8000.0)], se_movio=False, radar_ok=True,
                         interferida=False, noche=False).disparos[0]
    assert cerca.salvas <= 2 and cerca.misiles == 2 * cerca.salvas  # cerca: salva completa
    # contra muchos grupos lejanos gasta hasta la reserva de autodefensa y la guarda para los cercanos
    s = da.SISTEMAS["s300vm"]
    minimo = math.ceil(da.RESERVA_AUTODEFENSA * sum(a.cargados + a.reserva for a in s.armas))
    for _ in range(4):
        da.enfrentar(b, [_blanco(i, 90 + 5 * i, n=4, altura=8000.0) for i in range(3, 9)], se_movio=False,
                     radar_ok=True, interferida=False, noche=False)
    g = json.loads(b.cargas_json)
    assert sum(g["listos"].values()) + sum(g["reserva"].values()) >= minimo
    res = da.enfrentar(b, [_blanco(9, 120, n=4, altura=8000.0)], se_movio=False, radar_ok=True, interferida=False,
                       noche=False)
    assert not res.disparos and "autodefensa" in res.motivos[9]
    assert da.enfrentar(b, [_blanco(10, 40, n=2, altura=8000.0)], se_movio=False, radar_ok=True, interferida=False,
                        noche=False).disparos
