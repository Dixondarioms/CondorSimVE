"""Locucion del video: un MP3 por escena y los tiempos de cada frase para los subtitulos, en
tools/video/salida/locucion/ (<escena>.mp3 y <escena>.json). Dos motores de voz:

  edge        (por defecto) voces neuronales de Microsoft (lectura en voz alta de Edge, gratis y sin cuenta) via `edge-tts`.
  elevenlabs  voces de ElevenLabs, mas naturales. Hace falta una cuenta y su clave de API en la variable de entorno
              ELEVENLABS_API_KEY o en backend\\.env (ELEVENLABS_API_KEY=...). La clave nunca se escribe en la linea de
              comandos ni se muestra. Cada caracter del guion consume creditos de la cuenta.

Necesita internet. Las escenas ya generadas con el mismo texto, motor, voz y velocidad no se repiten.

    python tools/video/locucion.py                                  # voz masculina de Venezuela (Edge)
    python tools/video/locucion.py --voz es-VE-PaolaNeural          # voz femenina de Venezuela (Edge)
    python tools/video/locucion.py --velocidad -5%                  # algo mas pausado (Edge: -5% ... +20%)
    python tools/video/locucion.py --listar                         # voces en espanol disponibles (Edge)
    python tools/video/locucion.py --guion guion_tutorial           # otro guion (sale en salida/locucion_tutorial/)
    python tools/video/locucion.py --motor elevenlabs --listar      # las voces de la cuenta de ElevenLabs
    python tools/video/locucion.py --guion guion_tutorial --motor elevenlabs --voz "Nombre o id de la voz"
    python tools/video/locucion.py ... --motor elevenlabs --velocidad 1.05   # ElevenLabs: 0.7 (lento) ... 1.2 (rapido)
"""

import argparse
import asyncio
import base64
import hashlib
import importlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

import edge_tts

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
sys.path.insert(0, str(AQUI))

ESCENAS: list[dict] = []
PRONUNCIACION: dict[str, str] = {}
SALIDA = AQUI / "salida" / "locucion"
VOZ = "es-VE-SebastianNeural"
ELEVEN_URL = "https://api.elevenlabs.io/v1"
ELEVEN_MODELO = "eleven_multilingual_v2"  # el de mejor calidad en espanol; 1 credito por caracter


def para_voz(texto: str) -> str:
    for escrito, dicho in PRONUNCIACION.items():
        texto = texto.replace(escrito, dicho)
    return texto


def frases(texto: str) -> list[str]:
    """Divide en frases (punto, dos puntos o punto y coma) para los subtitulos."""
    partes = re.split(r"(?<=[.:;?!])\s+(?=[A-ZÁÉÍÓÚÑ¿¡S])", texto.strip())
    return [p for p in partes if p]


def ya_hecha(escena: dict, firma: str) -> bool:
    mp3, meta = SALIDA / f"{escena['id']}.mp3", SALIDA / f"{escena['id']}.json"
    return mp3.exists() and meta.exists() and json.loads(meta.read_text(encoding="utf-8")).get("firma") == firma


def guardar(escena: dict, audio: bytes, meta: dict, limites: list[dict]) -> None:
    (SALIDA / f"{escena['id']}.mp3").write_bytes(audio)
    (SALIDA / f"{escena['id']}.json").write_text(json.dumps({**meta, "frases": limites}, ensure_ascii=False, indent=1),
                                                  encoding="utf-8")
    print(f"  {escena['id']}: {len(audio) // 1024} KB, {len(limites)} frases")


# ------------------------------------------------------------------ Edge (Microsoft)
async def sintetizar_edge(escena: dict, voz: str, velocidad: str) -> None:
    texto = para_voz(escena["texto"])
    firma = hashlib.sha1(f"{voz}|{velocidad}|{texto}".encode()).hexdigest()
    if ya_hecha(escena, firma):
        print(f"  {escena['id']}: sin cambios")
        return
    com = edge_tts.Communicate(texto, voz, rate=velocidad, boundary="SentenceBoundary")
    audio, limites = bytearray(), []
    async for trozo in com.stream():
        if trozo["type"] == "audio":
            audio += trozo["data"]
        elif trozo["type"] in ("SentenceBoundary", "WordBoundary"):
            limites.append({"inicio": trozo["offset"] / 1e7, "duracion": trozo["duration"] / 1e7, "texto": trozo["text"]})
    guardar(escena, bytes(audio), {"firma": firma, "motor": "edge", "voz": voz, "velocidad": velocidad}, limites)


async def listar_edge() -> None:
    for v in await edge_tts.list_voices():
        if v["Locale"].startswith("es-"):
            print(f"{v['ShortName']:28} {v['Gender']:7} {v['Locale']}")


# ------------------------------------------------------------------ ElevenLabs
def clave_elevenlabs() -> str:
    """La clave de API: variable de entorno ELEVENLABS_API_KEY o la linea ELEVENLABS_API_KEY=... de backend\\.env."""
    clave = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    env = RAIZ / "backend" / ".env"
    if not clave and env.exists():
        for linea in env.read_text(encoding="utf-8").splitlines():
            if linea.strip().startswith("ELEVENLABS_API_KEY="):
                clave = linea.split("=", 1)[1].strip().strip('"').strip("'")
    if not clave:
        raise SystemExit("Falta la clave de ElevenLabs: escriba ELEVENLABS_API_KEY=su_clave en backend\\.env "
                         "(ese archivo no se sube al repositorio).")
    return clave


def pedir_elevenlabs(ruta: str, datos: dict | None = None) -> dict:
    cuerpo = json.dumps(datos).encode() if datos is not None else None
    req = urllib.request.Request(f"{ELEVEN_URL}/{ruta}", data=cuerpo, method="POST" if datos is not None else "GET",
                                 headers={"xi-api-key": clave_elevenlabs(), "Content-Type": "application/json",
                                          "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", "replace")[:300]
        if e.code == 401:
            raise SystemExit("ElevenLabs rechazo la clave de API (401): revise ELEVENLABS_API_KEY en backend\\.env.") from None
        raise SystemExit(f"ElevenLabs respondio {e.code}: {detalle}") from None


def voces_elevenlabs() -> list[dict]:
    return pedir_elevenlabs("voices").get("voices", [])


def listar_elevenlabs() -> None:
    for v in sorted(voces_elevenlabs(), key=lambda v: v["name"].lower()):
        et = v.get("labels") or {}
        print(f"{v['voice_id']:24} {v['name']:24} {et.get('language', ''):6} {et.get('accent', ''):18} {et.get('gender', ''):8} "
              f"{et.get('description', '') or et.get('use_case', '')}")
    try:
        sub = pedir_elevenlabs("user/subscription")
        print(f"\nCreditos: {sub.get('character_count', '?')} usados de {sub.get('character_limit', '?')} este periodo.")
    except SystemExit:
        pass


def id_voz_elevenlabs(voz: str) -> str:
    """Admite el id de la voz o su nombre (sin distinguir mayusculas)."""
    if re.fullmatch(r"[A-Za-z0-9]{20}", voz):
        return voz
    for v in voces_elevenlabs():
        if v["name"].lower() == voz.lower():
            return v["voice_id"]
    raise SystemExit(f"No hay una voz llamada «{voz}» en la cuenta: vea --motor elevenlabs --listar (o agreguela desde "
                     "la biblioteca de voces de ElevenLabs a «Mis voces»).")


def limites_desde_alineacion(texto: str, alineacion: dict) -> list[dict]:
    """Tiempos de cada frase a partir de la alineacion por caracter que devuelve ElevenLabs."""
    chars = alineacion.get("characters", [])
    ini = alineacion.get("character_start_times_seconds", [])
    fin = alineacion.get("character_end_times_seconds", [])
    if not chars or len(chars) != len(ini):
        return []
    limites, pos = [], 0
    devuelto = "".join(chars)
    for f in frases(texto):
        k = devuelto.find(f, pos)
        if k < 0:  # pequeñas diferencias de normalizacion: se avanza por longitud
            k = pos
        j = min(len(chars) - 1, k + len(f) - 1)
        limites.append({"inicio": ini[k], "duracion": max(0.05, fin[j] - ini[k]), "texto": f})
        pos = j + 1
    return limites


def sintetizar_elevenlabs(escena: dict, voz_id: str, voz: str, velocidad: float) -> None:
    texto = para_voz(escena["texto"])
    firma = hashlib.sha1(f"elevenlabs|{voz_id}|{velocidad}|{ELEVEN_MODELO}|{texto}".encode()).hexdigest()
    if ya_hecha(escena, firma):
        print(f"  {escena['id']}: sin cambios")
        return
    r = pedir_elevenlabs(f"text-to-speech/{voz_id}/with-timestamps?output_format=mp3_44100_128", {
        "text": texto, "model_id": ELEVEN_MODELO,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.8, "style": 0.15, "use_speaker_boost": True,
                           "speed": velocidad},
    })
    audio = base64.b64decode(r["audio_base64"])
    limites = limites_desde_alineacion(texto, r.get("alignment") or r.get("normalized_alignment") or {})
    guardar(escena, audio, {"firma": firma, "motor": "elevenlabs", "voz": voz, "voz_id": voz_id, "velocidad": velocidad,
                            "modelo": ELEVEN_MODELO}, limites)


# ------------------------------------------------------------------ principal
async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--motor", choices=["edge", "elevenlabs"], default="edge", help="motor de voz (por defecto edge)")
    ap.add_argument("--voz", help=f"voz: nombre de Edge (por defecto {VOZ}) o nombre/id de ElevenLabs")
    ap.add_argument("--velocidad", help="Edge: p. ej. -5%% o +8%% (por defecto +0%%); ElevenLabs: 0.7 a 1.2 (por defecto 1.0)")
    ap.add_argument("--listar", action="store_true", help="lista las voces disponibles y termina")
    ap.add_argument("--guion", default="guion", help="modulo del guion: guion (presentacion) o guion_tutorial")
    ap.add_argument("escenas", nargs="*", help="solo estas escenas (por id)")
    a = ap.parse_args()
    if a.listar:
        return listar_elevenlabs() if a.motor == "elevenlabs" else await listar_edge()
    global ESCENAS, PRONUNCIACION, SALIDA
    mod = importlib.import_module(a.guion)
    ESCENAS, PRONUNCIACION = mod.ESCENAS, mod.PRONUNCIACION
    if a.guion != "guion":
        SALIDA = AQUI / "salida" / ("locucion_" + a.guion.removeprefix("guion_"))
    SALIDA.mkdir(parents=True, exist_ok=True)
    escenas = [e for e in ESCENAS if not a.escenas or e["id"] in a.escenas]

    if a.motor == "elevenlabs":
        if not a.voz:
            raise SystemExit("Con --motor elevenlabs indique la voz: --voz \"nombre o id\" (vea --motor elevenlabs --listar).")
        velocidad = float(a.velocidad) if a.velocidad else 1.0
        if not 0.7 <= velocidad <= 1.2:
            raise SystemExit("La velocidad de ElevenLabs va de 0.7 a 1.2.")
        voz_id = id_voz_elevenlabs(a.voz)
        caracteres = sum(len(para_voz(e["texto"])) for e in escenas)
        print(f"ElevenLabs, voz {a.voz} ({voz_id}), velocidad {velocidad}, modelo {ELEVEN_MODELO}: "
              f"hasta {caracteres} caracteres (creditos) si todas las escenas cambiaron")
        for escena in escenas:
            sintetizar_elevenlabs(escena, voz_id, a.voz, velocidad)
        return

    voz, velocidad = a.voz or VOZ, a.velocidad or "+0%"
    print(f"Voz {voz}, velocidad {velocidad}")
    for escena in escenas:
        for intento in range(4):
            try:
                await sintetizar_edge(escena, voz, velocidad)
                break
            except Exception as e:  # noqa: BLE001 (cortes de red: se reintenta)
                if intento == 3:
                    raise
                print(f"  {escena['id']}: {e}; reintentando...")
                await asyncio.sleep(2 ** (intento + 1))


if __name__ == "__main__":
    asyncio.run(main())
