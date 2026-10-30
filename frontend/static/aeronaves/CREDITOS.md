# Imágenes de las unidades en el mapa

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

## Modelos 3D con licencia libre (octubre de 2026)

Estas imágenes (`<id>_000.png … <id>_345.png`, 24 rumbos, 160 px) son **renderizados propios** de modelos 3D con
licencia **CC0** (dominio público) o **CC BY 4.0** (uso libre con atribución: autor, obra y licencia, que figuran
abajo). Los modelos sin pintura (STL y OBJ) se pintaron de un solo tono; al Short Tucano y al Boeing 737 se les quitó
la librea original. Cómo se renderizó cada uno: `tools/sprites3d/modelos.json`.

| Imágenes | Se usan para | Modelo 3D | Autor | Licencia | Origen |
|---|---|---|---|---|---|
| `a29_*.png` | EMB-314 Super Tucano (A-29) | Airplane emb 314 Super Tucano | igor_ihs | CC BY 4.0 | https://www.thingiverse.com/thing:2290210 (copia: https://archive.org/details/thingiverse-2290210) |
| `at27_*.png` | EMB-312 Tucano (AT-27) | Short Tucano | mgg8 | CC0 | https://sketchfab.com/3d-models/27e4951f09eb44a7a126184fd2681f91 (descarga: airmuseums.co.uk) |
| `k8_*.png` | Hongdu K-8W | PAC K8 trainer | Waseem Shaukat | CC BY 4.0 | https://www.thingiverse.com/thing:5229573 (copia: https://archive.org/details/thingiverse-5229573) |
| `f22_*.png` | F-22A Raptor | F-22 Rapter Complete | Gabemiester08 | CC BY 4.0 | https://www.thingiverse.com/thing:3699149 (copia: https://archive.org/details/thingiverse-3699149) |
| `fa18_*.png` | F/A-18 (también Super Hornet y Growler) | F-18 Hornet | FoxFan | CC BY 4.0 | https://www.thingiverse.com/thing:5232638 (copia: https://archive.org/details/thingiverse-5232638) |
| `f35_*.png` | F-35A y F-35B | Lockheed Martin F-35 Lightning II | mgg8 | CC0 | https://sketchfab.com/3d-models/1161f64164ce481189ce67d39502c068 (descarga: airmuseums.co.uk) |
| `mi17_*.png` | Mi-17V-5 y Mi-8AMTSh | Hip H Helicopter (Mi-17) | Pfelpensson | CC BY 4.0 | https://www.thingiverse.com/thing:4592107 (copia: https://archive.org/details/thingiverse-4592107) |
| `mi24_*.png` | Mi-35M | Soviet rotary wing (Mi-24D) | mgg8 | CC0 | https://sketchfab.com/3d-models/21f5bfe5f831452b816391c1cbe99c5c (descarga: airmuseums.co.uk) |
| `ah64_*.png` | AH-64E Apache | AH-64 Apache and AH-1 Cobra | mgg8 | CC0 | https://sketchfab.com/3d-models/d52dfce9eed74c14b602fca5869fea56 (descarga: airmuseums.co.uk) |
| `mq1_*.png` | MQ-1 Predator | General Atomics MQ-1 Predator | mgg8 | CC0 | https://sketchfab.com/3d-models/969dd1f037ad44fe9ae9eb82fce6bff8 (descarga: airmuseums.co.uk) |
| `shahed136_*.png` | Shahed-136 | Shahed-136 (Geran-2) scale model | Yprit | CC BY 4.0 | https://www.thingiverse.com/thing:5807626 (copia: https://archive.org/details/thingiverse-5807626) |
| `e2_*.png` | E-2D Hawkeye | Northrop Grumman E-2 Hawkeye | IronManMX | CC0 | https://www.thingiverse.com/thing:5371937 (copia: https://archive.org/details/thingiverse-5371937) |
| `b737_*.png` | Cisternas sin modelo propio (Boeing 737 tanquero) | Boeing 707, 737 and 747 | mgg8 | CC0 | https://sketchfab.com/3d-models/e3224d0aa8c54f41a612ac74e35e045e (descarga: airmuseums.co.uk) |
| `bmp3_*.png` | Blindados sin modelo propio | BMP-3 IFV (1/100) | thommo1137 | CC BY 4.0 | https://www.thingiverse.com/thing:4087551 (copia: https://archive.org/details/thingiverse-4087551) |
| `2s19_*.png` | 2S19 Msta-S y artillería sin modelo propio | 2S19 MSTA SP Artillery | cpangracs | CC BY 4.0 | https://www.thingiverse.com/thing:4674581 (copia: https://archive.org/details/thingiverse-4674581) |
| `ural4320_*.png` | Convoyes (transporte) | Ural 4320 Truck (1/285) | Pfelpensson | CC BY 4.0 | https://www.thingiverse.com/thing:4597363 (copia: https://archive.org/details/thingiverse-4597363) |
| `ddg51_*.png` | Destructores (Arleigh Burke) | Arleigh Burke Class Destroyer | Scuderia | CC BY 4.0 | https://www.thingiverse.com/thing:4207292 (copia: https://archive.org/details/thingiverse-4207292) |
| `ffg7_*.png` | Fragatas sin modelo propio | USS Oliver Hazard Perry (FFG-7) | R_ain_D_own_ | CC BY 4.0 | https://www.thingiverse.com/thing:3581945 (copia: https://archive.org/details/thingiverse-3581945) |
| `nimitz_*.png` | Portaaviones (Nimitz) | USS Carl Vinson Nimitz Class | VinnyBoomBoom | CC BY 4.0 | https://www.thingiverse.com/thing:2104619 (copia: https://archive.org/details/thingiverse-2104619) |

CC BY 4.0: https://creativecommons.org/licenses/by/4.0/ · CC0: https://creativecommons.org/publicdomain/zero/1.0/
