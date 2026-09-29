# Imágenes satelitales (capa "Satélite")

`tiles_sat/{z}/{x}/{y}.jpg` son teselas de la capa **"s2cloudless_3857"** de **EOxCloudless**
(https://cloudless.eox.at), un mosaico global sin nubes hecho con datos Copernicus Sentinel-2 (ESA),
servido por EOX IT Services GmbH (https://eox.at) vía su WMTS público (https://tiles.maps.eox.at).

- **Licencia:** Creative Commons Attribution 4.0 (CC BY 4.0) — https://creativecommons.org/licenses/by/4.0/
- **Atribución exigida:** "EOxCloudless https://cloudless.eox.at by EOX IT Services GmbH
  (Contains modified Copernicus Sentinel data 2016)" — ya incluida en el control de atribución del mapa
  (`frontend/static/js/app.js`, `initMapa()`); no la quite si cambia de capa.
- **Resolución real:** ~10 m/píxel (igual que ESA WorldCover). Se descargó hasta el zoom 12; más
  allá el servidor solo interpola, así que no aporta información real.
- **Regenerar/ampliar:** `python tools/preparar_satelite.py --hasta-zoom N` (reanuda: no vuelve a bajar lo
  que ya está). No toca `frontend/static/tiles/` (relieve) ni `backend/data/terreno/` (grilla del motor):
  esto es solo la imagen de fondo alternativa, no cambia las reglas de movimiento ni la niebla de guerra.
