"""El codigo de la interfaz se revalida siempre; las teselas y la API mantienen su politica."""


def test_el_codigo_de_la_interfaz_se_revalida_siempre(api):
    c = api()
    for ruta in ("/", "/static/js/app.js", "/static/js/aviacion.js", "/static/css/style.css"):
        r = c.get(ruta)
        assert r.status_code == 200, ruta
        assert r.headers["cache-control"] == "no-cache", ruta
        assert r.headers.get("etag"), ruta  # la revalidacion responde 304 sin volver a enviar el archivo si no cambio
    etag = c.get("/static/js/app.js").headers["etag"]
    assert c.get("/static/js/app.js", headers={"If-None-Match": etag}).status_code == 304


def test_las_teselas_y_la_api_no_cambian_de_politica(api):
    c = api("alfa")
    assert "cache-control" not in c.get("/static/tiles_sat/5/9/15.jpg").headers
    assert c.get("/api/auth/yo").headers["cache-control"] == "no-store"
