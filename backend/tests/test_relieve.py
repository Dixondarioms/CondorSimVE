"""Relieve y linea de vista: las montañas y el horizonte ocultan a los sensores; perfil de vuelo de las aeronaves."""

import zlib

import pytest

from app.engine import geo, movimiento, relieve, vision
from app.models.orden import Orden
from app.routers import unidades as router_unidades
from app.terreno import Grilla, Terreno
from tests.conftest import TerrenoFalso
from tests.test_ciclo_vuelo import _caza, _refrescar
from tests.test_guerra_electronica import T, _u
from tests.test_orders import _avanzar, _escenario, _unidad

GRADO_KM = 111.195


class TerrenoConRelieve(TerrenoFalso):
    """Llano a 100 m con una cordillera de 3 000 m de norte a sur entre 20 y 30 km al este del origen."""

    tiene_elevacion = True

    def altura(self, lat, lon):
        return 3000.0 if 20 <= lon * GRADO_KM <= 30 else 100.0


class Mar(TerrenoFalso):
    """Mar abierto: solo la curvatura de la Tierra oculta."""

    tiene_elevacion = True

    def altura(self, lat, lon):
        return -200.0


MONTANA = TerrenoConRelieve()


def _este(id_, bando, clase, km_este, **kw):
    """Unidad suelta `km_este` km al este del origen."""
    return _u(id_, bando, clase, lon=km_este / GRADO_KM, **kw)


# ---------------------------------------------------------------- linea de vista
def test_la_cordillera_oculta_al_avion_rasante_y_medio_pero_no_al_alto():
    radar = _u(1, "azul", "radar")
    # a 40 km, tras la cordillera (a 20-30 km, 3 000 m): solo el perfil alto (6 000 m) libra la cresta
    for perfil, visto in (("rasante", False), ("medio", False), ("alto", True)):
        avion = _este(2, "rojo", "caza", 40, perfil_vuelo=perfil)
        assert relieve.linea_de_vista(MONTANA, radar, avion) is visto, perfil
        assert vision.detecta(radar, avion, MONTANA) is visto, perfil
    # del mismo lado de la cordillera, el rasante se ve
    assert vision.detecta(radar, _este(3, "rojo", "caza", 15, perfil_vuelo="rasante"), MONTANA)


def test_sin_alturas_no_hay_sombras_como_antes():
    radar = _u(1, "azul", "radar")
    avion = _este(2, "rojo", "caza", 60, perfil_vuelo="rasante")
    assert not T.tiene_elevacion
    assert relieve.linea_de_vista(T, radar, avion)
    assert vision.detecta(radar, avion, T)


def test_el_horizonte_de_radar_oculta_sobre_el_mar():
    destructor = _u(1, "azul", "destructor")
    # dos buques: radar de 30 m y blanco de 25 m -> horizonte ~43 km (radio efectivo 4/3)
    assert vision.detecta(destructor, _u(2, "rojo", "fragata", 35), Mar())
    assert not vision.detecta(destructor, _u(3, "rojo", "fragata", 55), Mar())
    # un avion a cota media sobre el mar se sigue viendo a 55 km; un misil rasante, no
    assert vision.detecta(destructor, _u(4, "rojo", "caza", 55), Mar())
    assert not vision.detecta(destructor, _u(5, "rojo", "caza", 65, perfil_vuelo="rasante"), Mar())  # horizonte ~54 km


def test_un_radar_en_la_cumbre_ve_lo_que_hay_detras_de_ella():
    en_el_llano = _u(1, "azul", "radar")
    en_la_cumbre = _este(2, "azul", "radar", 29.5)  # en el borde este de la cordillera (desde el centro la tapa la meseta)
    rasante = _este(3, "rojo", "caza", 60, perfil_vuelo="rasante")
    assert not vision.detecta(en_el_llano, rasante, MONTANA)
    assert vision.detecta(en_la_cumbre, rasante, MONTANA)


def test_la_escucha_electronica_tambien_necesita_linea_de_vista():
    radar = _este(1, "rojo", "radar", 60)
    escucha = _u(2, "azul", "guerra_electronica")
    assert vision.detecta(escucha, radar, T)
    assert not vision.detecta(escucha, radar, MONTANA)


# ---------------------------------------------------------------- perfil de vuelo
def test_perfiles_por_clase():
    assert relieve.perfil_de(_u(1, "azul", "caza")) == "medio"
    assert relieve.perfil_de(_u(2, "azul", "helicoptero")) == "rasante"
    assert relieve.perfiles_permitidos(_u(3, "azul", "helicoptero")) == ("medio", "rasante")
    assert relieve.perfil_de(_u(4, "azul", "helicoptero", perfil_vuelo="alto")) == "rasante"  # no puede: el de su clase
    assert relieve.perfil_de(_u(5, "azul", "misil_crucero", perfil_vuelo="alto")) == "rasante"
    assert relieve.perfiles_permitidos(_u(6, "azul", "misil_crucero")) == ()
    assert relieve.perfil_de(_u(7, "azul", "infanteria")) is None


def test_la_antiaerea_portatil_no_alcanza_al_perfil_alto_y_castiga_al_rasante():
    manpads = _u(1, "azul", "antiaerea_portatil")
    assert relieve.fuera_de_techo(manpads, _u(2, "rojo", "caza", perfil_vuelo="alto"))
    assert not relieve.fuera_de_techo(manpads, _u(3, "rojo", "caza"))
    assert relieve.factor_portatil(manpads, _u(4, "rojo", "caza", perfil_vuelo="rasante")) == relieve.FACTOR_PORTATIL_RASANTE
    assert relieve.factor_portatil(_u(5, "azul", "antiaerea"), _u(6, "rojo", "caza", perfil_vuelo="rasante")) == 1.0


def test_el_vuelo_rasante_gasta_mas_combustible_y_el_alto_menos():
    gasto = {}
    for perfil in relieve.PERFILES:
        avion = _u(1, "azul", "caza", velocidad_kmh=900, autonomia_km=1800, combustible=100, perfil_vuelo=perfil)
        gasto[perfil] = movimiento.simular(avion, [[0.0, 5.0]], T).combustible_gastado
    assert gasto["alto"] < gasto["medio"] < gasto["rasante"]
    assert gasto["rasante"] == pytest.approx(gasto["medio"] * 1.3)


# ---------------------------------------------------------------- en el turno
def test_la_antiaerea_no_dispara_sola_a_traves_de_la_cordillera(db_session):
    esc = _escenario(db_session)
    _unidad(db_session, esc, nombre="AA", clase="antiaerea", alcance_km=60, deteccion_km=60, velocidad_kmh=30)
    radar = _unidad(db_session, esc, nombre="Radar", clase="radar", deteccion_km=150, alcance_km=0, velocidad_kmh=0)
    intruso = _caza(db_session, esc, nombre="Intruso", bando="rojo", lon=40 / GRADO_KM, perfil_vuelo="rasante")
    _avanzar(db_session, esc, MONTANA)
    assert not db_session.query(Orden).filter(Orden.detalle == "defensa aerea").all()
    _refrescar(db_session, intruso)
    assert intruso.fuerza == 100
    # el mismo intruso en perfil alto: el radar lo ve por encima de la cordillera y la antiaerea le dispara
    intruso.perfil_vuelo = "alto"
    db_session.commit()
    _avanzar(db_session, esc, MONTANA)
    assert db_session.query(Orden).filter(Orden.detalle == "defensa aerea").count() == 1
    assert radar.id


# ---------------------------------------------------------------- API
def _preparar_api(api):
    prof = api("prof")
    esc = prof.post("/api/escenarios", json={"nombre": "Relieve"}).json()
    return prof, f"/api/escenarios/{esc['id']}"


def test_api_perfil_de_vuelo_y_cobertura(api, monkeypatch):
    prof, ruta = _preparar_api(api)
    caza = prof.post(f"{ruta}/unidades", json={"nombre": "Halcon", "bando": "azul", "tipo": "aerea", "clase": "caza",
                                               "lat": 0.1, "lon": 0.0}).json()
    helo = prof.post(f"{ruta}/unidades", json={"nombre": "Helo", "bando": "azul", "tipo": "aerea", "clase": "helicoptero",
                                               "lat": 0.1, "lon": 0.05}).json()
    radar = prof.post(f"{ruta}/unidades", json={"nombre": "Radar", "bando": "azul", "tipo": "terrestre", "clase": "radar",
                                                "lat": 0.0, "lon": 0.0}).json()
    assert caza["perfil_actual"] == "medio" and caza["perfiles_permitidos"] == ["alto", "medio", "rasante"]
    assert helo["perfil_actual"] == "rasante" and "alto" not in helo["perfiles_permitidos"]

    r = prof.post(f"{ruta}/unidades/{caza['id']}/perfil", json={"perfil_vuelo": "rasante"})
    assert r.status_code == 200 and r.json()["perfil_actual"] == "rasante"
    assert prof.post(f"{ruta}/unidades/{helo['id']}/perfil", json={"perfil_vuelo": "alto"}).status_code == 400
    assert prof.post(f"{ruta}/unidades/{radar['id']}/perfil", json={"perfil_vuelo": "alto"}).status_code == 400
    assert prof.post(f"{ruta}/unidades/{caza['id']}/perfil", json={"perfil_vuelo": "orbital"}).status_code == 422

    # sin alturas, la cobertura no esta disponible; con la cordillera, a baja cota se ve menos lejos al este
    assert prof.get(f"{ruta}/unidades/{radar['id']}/cobertura").json()["disponible"] is False
    monkeypatch.setattr(router_unidades, "get_terreno", lambda: MONTANA)
    cob = prof.get(f"{ruta}/unidades/{radar['id']}/cobertura").json()
    assert cob["disponible"] and set(cob["perfiles"]) == {"alto", "medio", "rasante"}
    este = 18  # rumbo 90 de 72 rumbos (cada 5 grados)
    lejos = {p: geo.distancia_km(0.0, 0.0, *cob["perfiles"][p]["poligono"][este]) for p in relieve.PERFILES}
    oeste = {p: geo.distancia_km(0.0, 0.0, *cob["perfiles"][p]["poligono"][54]) for p in relieve.PERFILES}
    # al este la cordillera corta la cobertura, mas cuanto mas bajo vuela el blanco
    assert lejos["rasante"] < 21 < lejos["medio"] < 31 < lejos["alto"] < 45
    # al oeste, llano: a cota media o alta el alcance del radar; a baja cota, el horizonte (~54 km)
    assert oeste["alto"] == pytest.approx(150, abs=1) and oeste["medio"] == pytest.approx(150, abs=1)
    assert 45 < oeste["rasante"] < 60
    assert prof.get(f"{ruta}/unidades/{caza['id']}/cobertura").json()["disponible"] is False  # solo sensores en tierra o mar


def test_un_alumno_no_cambia_el_perfil_de_una_aeronave_ajena(api):
    prof, ruta = _preparar_api(api)
    rojo = prof.post(f"{ruta}/unidades", json={"nombre": "Caza R", "bando": "rojo", "tipo": "aerea", "clase": "caza",
                                               "lat": 0.1, "lon": 0.0}).json()
    alfa_id = next(u["id"] for u in prof.get("/api/usuarios").json() if u["username"] == "alfa")
    prof.put(f"{ruta}/usuarios", json={"usuario_ids": [alfa_id]})
    alfa = api("alfa")
    assert alfa.post(f"{ruta}/unidades/{rojo['id']}/perfil", json={"perfil_vuelo": "alto"}).status_code == 404


# ---------------------------------------------------------------- grilla real
def test_la_grilla_de_alturas_se_consulta_por_celda():
    meta = {"id": "prueba", "z": 9, "x0": 151, "y0": 238, "ancho": 4, "alto": 4, "elev_paso": 2, "elev_ancho": 2, "elev_alto": 2}
    alturas = memoryview(zlib.decompress(zlib.compress(bytes([10, 0, 20, 0, 30, 0, 40, 0])))).cast("h")  # 10 20 / 30 40
    g = Grilla(meta, bytes(16), alturas)
    t = Terreno(grillas=[g])
    assert t.tiene_elevacion
    n = 2 ** 9 * 256

    def punto(px, py):  # centro del pixel (px, py) de la grilla (sobre Venezuela, zoom 9)
        import math
        x, y = 151 * 256 + px + 0.5, 238 * 256 + py + 0.5
        lon = x / n * 360.0 - 180.0
        lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
        return lat, lon

    assert t.altura(*punto(0, 0)) == 10 and t.altura(*punto(3, 0)) == 20
    assert t.altura(*punto(1, 3)) == 30 and t.altura(*punto(2, 2)) == 40
    assert t.altura(*punto(10, 10)) is None
    assert not Terreno(grillas=[Grilla(meta, bytes(16))]).tiene_elevacion
