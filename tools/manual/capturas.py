# Capturas de pantalla del simulador con Chrome headless (arnes de pruebas: datos simulados, sin sesion).
import os
import subprocess
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent / "salida"  # PNG/JPG generados (no se versionan)
AQUI.mkdir(exist_ok=True)
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE = os.environ.get("SIETE_URL", "http://127.0.0.1:8000")  # otro puerto: SIETE_URL=http://127.0.0.1:8002
ARNES = BASE + "/static/pruebas/arnes.html"

CAPTURAS = [
    ("cap_login", BASE + "/", 1280, 800, 4000, None),
    ("cap_instructor", f"{ARNES}?rol=instructor&lat=8.62&lon=-70.5&zoom=10", 1440, 900, 9000, 875),
    ("cap_azul", f"{ARNES}?rol=azul&puesto=mando&lat=8.62&lon=-70.55&zoom=11", 1440, 900, 9000, 875),
    ("cap_a3", f"{ARNES}?rol=azul&puesto=operaciones&lat=8.62&lon=-70.55&zoom=11", 1440, 900, 9000, 875),
    ("cap_base_plano", f"{ARNES}?rol=instructor&lat=8.6165&lon=-70.2175&zoom=15", 1440, 900, 10000, 875),
    ("cap_base_cerca", f"{ARNES}?rol=instructor&lat=8.6155&lon=-70.2185&zoom=17", 1440, 900, 10000, 875),
    ("cap_carlota", f"{ARNES}?rol=instructor&lat=10.4855&lon=-66.8425&zoom=15", 1440, 900, 10000, 875),
    ("cap_naval", f"{ARNES}?rol=azul&puesto=mando&lat=10.66&lon=-68.0&zoom=11", 1440, 900, 9000, 875),
    ("cap_videowall", f"{ARNES}?rol=instructor&modo=videowall&vista=completa&lat=8.62&lon=-70.5&zoom=10", 1440, 900, 9000, 875),
    ("cap_replay", f"{ARNES}?rol=instructor&abrir=replay&instante=2.5", 1440, 900, 12000, 875),
    ("cap_rubrica", f"{ARNES}?rol=instructor&abrir=rubrica", 1440, 900, 12000, 875),
    ("cap_ia_noche", f"{ARNES}?rol=azul&puesto=mando&ia=rojo&nivel=prudente&noche=1&hora=1260&lat=8.6&lon=-70.57&zoom=11", 1440, 900, 9000, None),
    ("cap_maqueta", BASE + "/static/maqueta/index.html", 1440, 900, 6000, None),
]
FOTOS = ["f16.jpg", "su30.jpg"]
ILUSTRACIONES = ["caza_embarcado", "helo_ataque", "helo_transporte", "ataque_ligero", "crucero",
                 "dron_reconocimiento", "dron_armado", "municion_merodeadora", "avion_ge"]


def chrome(url, salida, w, h, espera):
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                    f"--user-data-dir={AQUI / 'perfil'}", "--disk-cache-size=1", f"--window-size={w},{h}", f"--virtual-time-budget={espera}",
                    f"--screenshot={salida}", url], capture_output=True, timeout=180)


for nombre, url, w, h, espera, recorte in CAPTURAS:
    salida = AQUI / f"{nombre}.png"
    chrome(url, salida, w, h, espera)
    im = Image.open(salida)
    if recorte:
        im = im.crop((0, 0, im.width, recorte))
        im.save(salida)
    im.convert("RGB").save(AQUI / f"{nombre}.jpg", "JPEG", quality=85)  # el manual usa las JPG (PDF mas liviano)
    print(nombre, salida.stat().st_size)

# galeria de miniaturas 3D (HTML estatico generado por galeria.js con Node; las imagenes salen del servidor)
subprocess.run(["node", str(Path(__file__).resolve().parent / "galeria.js")], check=True)
salida = AQUI / "cap_miniaturas.png"
chrome((AQUI / "galeria.html").as_uri(), salida, 1400, 1060, 6000)
Image.open(salida).convert("RGB").save(AQUI / "cap_miniaturas.jpg", "JPEG", quality=85)
print("cap_miniaturas", salida.stat().st_size)

for ilus in ILUSTRACIONES:
    salida = AQUI / f"ilus_{ilus}.png"
    chrome(f"{BASE}/static/fotos/{ilus}.svg", salida, 640, 360, 1500)
    print(ilus, salida.stat().st_size)

# mapa de America (region continental a ~1,2 km/pixel) con Venezuela en detalle encima; se toma solo si existe la region
if (Path(__file__).resolve().parents[2] / "frontend" / "static" / "tiles" / "america" / "3").is_dir():
    salida = AQUI / "cap_america.png"
    chrome(f"{ARNES}?rol=instructor&lat=8&lon=-75&zoom=4", salida, 1440, 900, 9000)
    if salida.exists():
        im = Image.open(salida)
        im = im.crop((0, 0, im.width, 875))
        im.save(salida)
        im.convert("RGB").save(AQUI / "cap_america.jpg", "JPEG", quality=85)
        print("cap_america", salida.stat().st_size)
