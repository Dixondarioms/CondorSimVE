"""Locucion del video con las voces neuronales de Microsoft (servicio de lectura en voz alta de Edge, gratuito y sin
cuenta) por medio de `edge-tts`. Genera un MP3 por escena y los tiempos de cada frase para los subtitulos en
tools/video/salida/locucion/ (<escena>.mp3 y <escena>.json).

Necesita internet (speech.platform.bing.com). Las escenas ya generadas con el mismo texto y voz no se repiten.

    python tools/video/locucion.py                                  # voz masculina de Venezuela
    python tools/video/locucion.py --voz es-VE-PaolaNeural          # voz femenina de Venezuela
    python tools/video/locucion.py --velocidad -5%                  # algo mas pausado
    python tools/video/locucion.py --listar                         # voces en espanol disponibles
"""

import argparse
import asyncio
import hashlib
import json
import re
import sys
from pathlib import Path

import edge_tts

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from guion import ESCENAS, PRONUNCIACION  # noqa: E402

SALIDA = AQUI / "salida" / "locucion"
VOZ = "es-VE-SebastianNeural"


def para_voz(texto: str) -> str:
    for escrito, dicho in PRONUNCIACION.items():
        texto = texto.replace(escrito, dicho)
    return texto


def frases(texto: str) -> list[str]:
    """Divide en frases (punto, dos puntos o punto y coma) para los subtitulos."""
    partes = re.split(r"(?<=[.:;?!])\s+(?=[A-ZÁÉÍÓÚÑ¿¡S])", texto.strip())
    return [p for p in partes if p]


async def sintetizar(escena: dict, voz: str, velocidad: str) -> None:
    texto = para_voz(escena["texto"])
    firma = hashlib.sha1(f"{voz}|{velocidad}|{texto}".encode()).hexdigest()
    mp3, meta = SALIDA / f"{escena['id']}.mp3", SALIDA / f"{escena['id']}.json"
    if mp3.exists() and meta.exists() and json.loads(meta.read_text(encoding="utf-8")).get("firma") == firma:
        print(f"  {escena['id']}: sin cambios")
        return
    com = edge_tts.Communicate(texto, voz, rate=velocidad, boundary="SentenceBoundary")
    audio, limites = bytearray(), []
    async for trozo in com.stream():
        if trozo["type"] == "audio":
            audio += trozo["data"]
        elif trozo["type"] in ("SentenceBoundary", "WordBoundary"):
            limites.append({"inicio": trozo["offset"] / 1e7, "duracion": trozo["duration"] / 1e7, "texto": trozo["text"]})
    mp3.write_bytes(bytes(audio))
    meta.write_text(json.dumps({"firma": firma, "voz": voz, "velocidad": velocidad, "frases": limites},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  {escena['id']}: {len(audio) // 1024} KB, {len(limites)} frases")


async def listar() -> None:
    for v in await edge_tts.list_voices():
        if v["Locale"].startswith("es-"):
            print(f"{v['ShortName']:28} {v['Gender']:7} {v['Locale']}")


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--voz", default=VOZ, help=f"voz neuronal (por defecto {VOZ})")
    ap.add_argument("--velocidad", default="+0%", help="ritmo de lectura, p. ej. -5%% o +8%%")
    ap.add_argument("--listar", action="store_true", help="lista las voces en espanol y termina")
    ap.add_argument("escenas", nargs="*", help="solo estas escenas (por id)")
    a = ap.parse_args()
    if a.listar:
        return await listar()
    SALIDA.mkdir(parents=True, exist_ok=True)
    print(f"Voz {a.voz}, velocidad {a.velocidad}")
    for escena in ESCENAS:
        if not a.escenas or escena["id"] in a.escenas:
            for intento in range(4):
                try:
                    await sintetizar(escena, a.voz, a.velocidad)
                    break
                except Exception as e:  # noqa: BLE001 (cortes de red: se reintenta)
                    if intento == 3:
                        raise
                    print(f"  {escena['id']}: {e}; reintentando...")
                    await asyncio.sleep(2 ** (intento + 1))


if __name__ == "__main__":
    asyncio.run(main())
