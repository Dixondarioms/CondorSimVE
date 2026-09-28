# Imágenes de las aeronaves en el mapa

Las imágenes `f16_000.png … f16_345.png` y `su30_000.png … su30_345.png` (24 rumbos cada una, 160 px, fondo
transparente) son **renderizados propios** de dos modelos 3D descargados de Sketchfab, vistos con una cámara
inclinada 42° (ver `tools/sprites3d/`). Los archivos `.glb` originales **no se incluyen** en el repositorio.

| Imágenes | Modelo 3D | Autor | Licencia | Origen |
|---|---|---|---|---|
| `f16_*.png` | F16A | amf1re | Sketchfab Standard | https://sketchfab.com/3d-models/f16a-8e318343bf174e8f955707df54cb1fa6 |
| `su30_*.png` | Sukhoi Su 33 Flanker D | helijah | Sketchfab Standard | https://sketchfab.com/3d-models/sukhoi-su-33-flanker-d-b355182c980e4e53958956a56fa91f2e |

Notas:

- **Licencia:** «Sketchfab Standard» (https://sketchfab.com/licenses). Antes de redistribuir el proyecto fuera de la
  institución, confirme que su uso encaja con esos términos o reemplace las imágenes.
- **El modelo del «Su-30» es un Su-33 (Flanker-D)**, la variante naval del Flanker: tiene alas plegables, canards
  y la librea (camuflaje azul y estrellas rojas) de la aviación naval rusa. Se usó por ser el modelo disponible; el
  Su-30MK2 de la Aviación Militar Bolivariana es muy parecido en forma.
- **Escala:** el F-16 se renderizó a 14,5 m y el Su-33 a 21,2 m de largo, con marcos de 9,6 m y 14 m de semilado, de
  modo que a la misma escala en pantalla conservan su tamaño relativo real (ver `SPRITES` en `js/modelo3d.js`).
- Las aeronaves sin modelo (p. ej. un caza enemigo no identificado) se dibujan con un caza genérico procedural
  (`js/modelo3d.js`), sin imágenes.
