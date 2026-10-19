# Video de presentación de S.I.E.T.E. (4K con locución)

Genera `tools/video/salida/SIETE_presentacion_4K_locucion.mp4`: 3840×2160, 30 cuadros/s, H.264 + AAC, ~5 min.

- **Apertura** con el emblema de la DIDA (`recursos/dida_logo.jpg`) y el logotipo de S.I.E.T.E. sobre un fondo
  azul con trazas de circuito.
- **13 capítulos** sobre capturas reales de la interfaz en 4K: qué es, acceso y roles, terreno, unidades, órdenes y
  turnos, niebla de guerra, operaciones aéreas, mar y guerra electrónica, meteorología, dirección del ejercicio,
  trabajo en equipo, informe posterior (AAR) y puesta en marcha. La cámara se acerca suavemente a la parte de la
  pantalla de la que se habla. Cada capítulo lleva su rótulo numerado y el sello de la DIDA.
- **Locución** con las voces neuronales de Microsoft en español de Venezuela (`es-VE-SebastianNeural` o
  `es-VE-PaolaNeural`), gratuitas y sin cuenta (servicio de lectura en voz alta de Edge, vía `edge-tts`).
- **Subtítulos** sincronizados con cada frase de la voz y **música de fondo** generada, que baja mientras se habla.
- **Cierre** con los créditos y el lema «El infinito es el límite».

## En un clic (Windows)

Doble clic en `tools\video\generar_video.cmd` (voz femenina: `generar_video.cmd es-VE-PaolaNeural`). Requiere haber
ejecutado `instalar.cmd`, **ffmpeg** en el PATH e internet (solo para la voz). Si faltan las capturas, arranca el
servidor y las toma con Chrome. El montaje en 4K tarda unos 20–30 min según el equipo.

## Paso a paso

```
backend\venv\Scripts\python -m pip install -r tools\video\requirements.txt
backend\venv\Scripts\python tools\video\capturas_video.py        # con el servidor en marcha en el puerto 8000
backend\venv\Scripts\python tools\video\locucion.py              # --voz es-VE-PaolaNeural, --velocidad -5%
backend\venv\Scripts\python tools\video\generar_video.py         # --resolucion 1080 para un borrador rápido
```

| Archivo | Qué hace |
|---|---|
| `guion.py` | Texto de cada escena (voz y subtítulo), capítulo, capturas y movimiento de cámara; pronunciación de siglas. |
| `capturas_video.py` | Capturas 4K del arnés de pruebas reutilizando los recorridos del manual (`tools/manual/capturas_guia.py`). |
| `locucion.py` | Un MP3 por escena con los tiempos de cada frase (`salida/locucion/`, se versiona: con ella el montaje no necesita internet). Solo rehace lo que cambió. |
| `generar_video.py` | Montaje: cámara, rótulos, subtítulos, música, mezcla y codificación con ffmpeg. |

Opciones de `generar_video.py`: `--musica pista.mp3` (usa esa pista en lugar de la generada), `--sin-musica`,
`--sin-subtitulos`, `--preset slow` (archivo más chico), `--crf 18` (calidad), `--cuadro 42` (guarda solo el cuadro
de ese segundo, para revisar), `--desde/--hasta` (un tramo). Sin locución generada arma un **borrador** mudo con los
tiempos estimados y la marca «BORRADOR».

Para cambiar el texto, edite `guion.py` y vuelva a ejecutar `locucion.py` y `generar_video.py`: la duración de cada
escena la marca su locución. Si una sigla se lee mal, agréguela a `PRONUNCIACION`.

## Video tutorial paso a paso (2K con locución)

`tools\video\generar_tutorial.cmd` genera `salida/SIETE_tutorial_2K_locucion.mp4`: 2560×1440, ~10 min, con la misma
voz venezolana (un poco más rápida: `--velocidad +8%`), 15 capítulos que recorren todo el simulador en el orden en que se
usa (puesta en marcha, roles, pantalla, terreno, preparar el ejercicio, fuerzas, órdenes, aviación, defensa aérea y mar,
resolver el turno, el TIEM, la IA, trabajo en equipo e informe posterior), y además de las capturas lleva **clips del
simulador en marcha**: el vuelo sobre el terreno, una orden de mover con sus clics, la resolución del turno con las
unidades desplazándose, la planificación de una misión, el replay del informe y los documentos del TIEM.

| Archivo | Qué hace |
|---|---|
| `guion_tutorial.py` | Guion del tutorial (mismo formato que `guion.py`; una imagen `("clip_x", "clip")` reproduce un clip entero). |
| `clips_video.py` | Graba los clips sobre el arnés con el **tiempo virtual** de Chrome: cada cuadro es 1/30 s exacto, así que salen fluidos aunque la captura a 2K sea lenta. Cursor rojo que marca los clics. `salida/clips/<nombre>/00001.jpg…` + `meta.json`. |
| `capturas_video.py` | Ahora toma todas las capturas del manual (`capturas_guia.CAPTURAS`) a pantalla entera en 4K. |

Paso a paso: `capturas_video.py`, `clips_video.py` (con el servidor en el puerto 8000), `locucion.py --guion guion_tutorial
--velocidad +8%` y `generar_video.py --guion guion_tutorial --resolucion 2k`.

**Voz más natural con ElevenLabs.** `locucion.py` admite `--motor elevenlabs`: hace falta una cuenta en elevenlabs.com y su
clave de API en `backend\.env` (`ELEVENLABS_API_KEY=...`; ese archivo no se sube al repositorio y la clave nunca se muestra).
`--motor elevenlabs --listar` enumera las voces de la cuenta (agregue antes una voz en español latino desde su biblioteca a
«Mis voces») y los créditos que quedan; luego `locucion.py --guion guion_tutorial --motor elevenlabs --voz "Nombre"
[--velocidad 1.05]` regraba solo las escenas que cambiaron. Cada carácter del guion consume un crédito (el tutorial usa
unos 9 700; el plan gratuito da 10 000 al mes). El montaje es el mismo. `generar_video.py --guion guion_tutorial
--comprobar` dice qué capturas, clips o locuciones faltan. La locución queda en `salida/locucion_tutorial/` (versionada).
