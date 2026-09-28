# Renderizador de sprites 3D

Convierte modelos `.glb` de aeronaves en las imágenes que se dibujan en el mapa (`frontend/static/aeronaves/`).
Solo hace falta al preparar o cambiar las imágenes; el simulador no lo usa al ejecutarse.

```
cd tools/sprites3d
npm install
python servidor.py --modelo f16=C:\ruta\f16a.glb --modelo su30=C:\ruta\su33.glb --salida salida
```

Con el servidor en marcha, abra en el navegador (necesita WebGL):

1. **Inspección** (para elegir el eje de la proa): `http://127.0.0.1:8766/render.html?modelo=f16&modo=inspeccion&px=760`
2. **Render** de 24 rumbos:
   `http://127.0.0.1:8766/render.html?modelo=f16&modo=render&nariz=-z&largo=14.5&marco=9.6&pasos=24&px=256`
   `http://127.0.0.1:8766/render.html?modelo=su30&modo=render&nariz=-x&largo=21.2&marco=14&pasos=24&px=256`

   `nariz`: eje del modelo hacia donde apunta la proa; `largo`: largo real en metros; `marco`: semilado del cuadro en
   metros. Los PNG salen en `salida/` (256 px); se reducen a 160 px con Pillow y se copian a
   `frontend/static/aeronaves/` con el nombre `<modelo>_<rumbo de 3 cifras>.png`.

Si cambia el `marco` de un modelo, actualice `SPRITES` en `frontend/static/js/modelo3d.js`.
Los `.glb` **no se versionan** (licencia Sketchfab Standard): están en `.gitignore`.
