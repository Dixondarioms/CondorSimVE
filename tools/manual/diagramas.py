# Genera los esquemas del manual como HTML (SVG) y los captura con Chrome headless a PNG.
import subprocess
from pathlib import Path

AQUI = Path(__file__).resolve().parent / "salida"  # PNG/JPG generados (no se versionan)
AQUI.mkdir(exist_ok=True)
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

CSS = """
<style>
  body { margin:0; background:#fff; font-family: 'Segoe UI', Arial, sans-serif; }
  svg { display:block; }
  .caja { fill:#f4f6f9; stroke:#3a4a5c; stroke-width:1.6; rx:10; }
  .azul { fill:#e6efff; stroke:#3A86FF; }
  .rojo { fill:#fde8eb; stroke:#EF233C; }
  .verde { fill:#e9f5ea; stroke:#2f8f4e; }
  .gris { fill:#eef0f3; stroke:#7a8794; }
  .amar { fill:#fff7dc; stroke:#c9a227; }
  .t { font-size:15px; fill:#1c2530; }
  .tb { font-size:16px; font-weight:700; fill:#1c2530; }
  .ts { font-size:12.5px; fill:#3d4a57; }
  .fl { stroke:#3a4a5c; stroke-width:1.8; fill:none; marker-end:url(#p); }
  .fl2 { stroke:#3a4a5c; stroke-width:1.8; fill:none; marker-end:url(#p); marker-start:url(#p0); }
  .n { font-size:13px; font-weight:700; fill:#fff; }
</style>
<defs>
  <marker id="p" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#3a4a5c"/></marker>
  <marker id="p0" markerWidth="10" markerHeight="10" refX="1" refY="5" orient="auto"><path d="M10,0 L0,5 L10,10 z" fill="#3a4a5c"/></marker>
</defs>
"""


def caja(x, y, w, h, titulo, lineas=(), clase="caja", desde=46):
    out = [f'<rect class="caja {clase}" x="{x}" y="{y}" width="{w}" height="{h}" rx="10"/>',
           f'<text class="tb" x="{x + w / 2}" y="{y + 24}" text-anchor="middle">{titulo}</text>']
    if not titulo:
        desde = 60
    for i, l in enumerate(lineas):
        out.append(f'<text class="ts" x="{x + w / 2}" y="{y + desde + i * 17}" text-anchor="middle">{l}</text>')
    return "\n".join(out)


def arquitectura():
    s = ['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="720" viewBox="0 0 1200 720">', CSS]
    s.append('<text class="tb" x="600" y="34" text-anchor="middle" style="font-size:20px">Arquitectura del Simulador Fénix (aula en red local, sin internet)</text>')
    # clientes
    s.append(caja(40, 70, 1120, 150, "Estaciones del aula (solo un navegador web: Chrome, Edge o Firefox)"))
    cl = [("Instructor / Director", ["ojo de dios, reloj, clima,", "eventos, ajustes, informe"], "amar"),
          ("Bando Azul", ["puestos EM · A2 · A3 · A4 · A5", "órdenes, misiones, gráficos, chat"], "azul"),
          ("Bando Rojo", ["puestos EM · A2 · A3 · A4 · A5", "órdenes, misiones, gráficos, chat"], "rojo"),
          ("Observador", ["solo lectura", "informe AAR"], "gris"),
          ("Videowall", ["pantalla del centro", "de operaciones"], "gris")]
    for i, (t, ls, c) in enumerate(cl):
        s.append(caja(60 + i * 220, 108, 200, 96, t, ls, c))
    # flecha
    s.append('<path class="fl2" d="M600,222 L600,290"/>')
    s.append('<text class="ts" x="612" y="262">HTTP (REST, JSON) + WebSocket (estado en vivo, chat)</text>')
    # servidor
    s.append(caja(40, 292, 1120, 240, "Servidor (un equipo del aula): FastAPI + Uvicorn, Python"))
    sv = [("API REST", ["escenarios, unidades, órdenes,", "misiones, usuarios, informe"]),
          ("WebSocket", ["difunde el estado a cada", "cliente, filtrado por bando"]),
          ("Motor de simulación", ["catálogo, movimiento, visión,", "combate, aeronaves, misiles,", "GE, logística, objetivos"]),
          ("Reloj y turnos", ["fase de decisión →", "resolución por fases", "temporizador opcional"]),
          ("Seguridad", ["sesiones, contraseñas PBKDF2,", "puestos y roles (403),", "CSP sin recursos externos"])]
    for i, (t, ls) in enumerate(sv):
        s.append(caja(60 + i * 220, 330, 200, 110, t, ls, "verde"))
    s.append(caja(60, 452, 1080, 66, "Datos que se sirven desde el propio servidor",
                  ["teselas satelitales y de relieve · fronteras, ríos, ciudades · planos de los aeródromos (OSM) · catálogo · miniaturas 3D · librerías (Leaflet, milsymbol)"]))
    # bd
    s.append('<path class="fl2" d="M600,534 L600,590"/>')
    s.append(caja(300, 592, 600, 96, "Base de datos", ["SQLite (un archivo, respaldo automático) o PostgreSQL (varias aulas)",
                                                      "migraciones Alembic al arrancar · instantánea de cada turno para el informe"], "gris"))
    s.append("</svg>")
    return "\n".join(s)


def ciclo():
    s = ['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="640" viewBox="0 0 1200 640">', CSS]
    s.append('<text class="tb" x="600" y="34" text-anchor="middle" style="font-size:20px">Ciclo de un turno (1 turno = 1 hora simulada)</text>')
    s.append(caja(40, 70, 1120, 120, "Fase de DECISIÓN (planificación)",
                  ["Cada bando emite sus órdenes (una por unidad y turno): mover, atacar, apoyar, construir, patrullar, aterrizar, despegar, interferir, lanzar…",
                   "y planifica misiones aéreas. El mapa previsualiza dónde terminaría cada unidad. Cada bando pulsa «Estoy listo».",
                   "El turno se resuelve cuando lo pide el instructor, cuando ambos están listos (opción) o al agotarse el tiempo."], "azul"))
    s.append('<path class="fl" d="M600,192 L600,228"/>')
    s.append('<text class="tb" x="600" y="252" text-anchor="middle">Fase de RESOLUCIÓN (el motor, en este orden)</text>')
    fases = [("0", "Despegues y lanzamientos", ["grupos que salen de bases", "y portaaviones; salvas", "de misiles; misiones"]),
             ("0b", "Guerra electrónica", ["zonas de interferencia", "del turno; el emisor", "queda delatado"]),
             ("1", "Movimiento y vuelo", ["terreno, ríos, clima, peso;", "patrullas, aterrizajes;", "misiles guiados; obras"]),
             ("2", "Apoyos e intercepción", ["apoyos registrados;", "patrullas CAP y antiaérea", "automática eligen blanco"]),
             ("3", "Combates simultáneos", ["primero el fuego contra", "misiles en vuelo; luego", "todos a la vez"]),
             ("4", "Logística", ["consumo, reabastecimiento,", "existencias, emergencias,", "objetivos y puntaje"])]
    for i, (n, t, ls) in enumerate(fases):
        x = 40 + i * 190
        s.append(caja(x, 268, 176, 130, "", ls, "verde").replace('y="292"', 'y="304"'))
        s.append(f'<text class="tb" x="{x + 88}" y="{268 + 34}" text-anchor="middle" style="font-size:14.5px">{t}</text>')
        s.append(f'<circle cx="{x + 88}" cy="268" r="14" fill="#2f8f4e"/><text class="n" x="{x + 88}" y="273" text-anchor="middle">{n}</text>')
        if i < len(fases) - 1:
            s.append(f'<path class="fl" d="M{x + 176},333 L{x + 190},333"/>')
    s.append('<path class="fl" d="M600,400 L600,436"/>')
    s.append(caja(40, 438, 1120, 96, "Difusión del nuevo estado por WebSocket",
                  ["Cada cliente recibe solo lo que su bando ve (niebla de guerra): sus unidades, los enemigos detectados y los últimos contactos.",
                   "Se guarda una instantánea del turno y cada combate para el informe posterior (AAR). Empieza la decisión del turno siguiente."], "amar"))
    s.append('<path class="fl" d="M1160,486 L1185,486 L1185,130 L1162,130"/>')
    s.append('<text class="ts" x="1188" y="310" transform="rotate(90 1188 310)" text-anchor="middle">siguiente turno</text>')
    s.append("</svg>")
    return "\n".join(s)


def puestos():
    s = ['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="560" viewBox="0 0 1200 560">', CSS]
    s.append('<text class="tb" x="600" y="34" text-anchor="middle" style="font-size:20px">Roles y puestos de un ejercicio</text>')
    s.append(caja(40, 60, 240, 130, "Instructor", ["Director del ejercicio: crea el", "escenario, ubica unidades, fija el", "clima, inyecta eventos, resuelve", "turnos, evalúa (informe AAR)"], "amar"))
    s.append(caja(920, 60, 240, 130, "Observador", ["Ve todo, no emite órdenes.", "Útil para evaluadores", "y visitantes"], "gris"))
    s.append(caja(300, 60, 600, 130, "Bando (Azul o Rojo) — un estado mayor de aula",
                  ["Todos los puestos comparten la misma vista del bando (niebla, contactos, gráficos, chat).", "Lo que cambia es qué órdenes puede emitir cada uno. El servidor rechaza lo que no corresponde al puesto."], "azul"))
    ps = [("EM · Estado Mayor", ["Todo (por defecto para", "un solo alumno por bando).", "Confirma LISTO"]),
          ("A2 · Inteligencia", ["Radares (encender/apagar),", "guerra electrónica terrestre,", "contactos, gráficos de blancos"]),
          ("A3 · Operaciones", ["Aeronaves ya en el aire o", "en pista: rutas, patrullas,", "ataques, aterrizajes, misiones"]),
          ("A4 · Logística", ["Ingenieros (puentes, vados)", "y convoyes de", "abastecimiento"]),
          ("A5 · Planificación", ["Unidades terrestres y navales,", "antiaérea, misiles, envío de", "grupos desde bases. LISTO"])]
    for i, (t, ls) in enumerate(ps):
        x = 40 + i * 228
        s.append(f'<path class="fl" d="M{x + 104},192 L{x + 104},228"/>' if i in (1, 2, 3) else f'<path class="fl" d="M{600 if i == 0 else 600},192 L{x + 104},228"/>')
        s.append(caja(x, 230, 208, 120, t, ls, "azul" if i else "verde"))
    s.append(caja(40, 380, 1120, 150, "Acceso y seguridad",
                  ["Cada usuario entra con contraseña (mínimo 8 caracteres, 5 intentos); las sesiones duran 12 h y el instructor puede revocarlas.",
                   "Alumnos y observadores solo ven los escenarios que el instructor les asigna. El instructor puede «ver como» un bando para mostrar en clase",
                   "lo que ese bando conoce. Usuario y puesto: python -m app.crear_usuario <nombre> --rol azul --puesto planificacion"], "gris"))
    s.append("</svg>")
    return "\n".join(s)


def capturar(nombre, html, w, h):
    f = AQUI / f"{nombre}.html"
    f.write_text(f"<!doctype html><html><head><meta charset='utf-8'></head><body>{html}</body></html>", encoding="utf-8")
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                    f"--user-data-dir={AQUI / 'perfil'}", f"--window-size={w},{h}", "--virtual-time-budget=2000",
                    f"--screenshot={AQUI / (nombre + '.png')}", f.as_uri()], capture_output=True)
    print(nombre, (AQUI / f"{nombre}.png").stat().st_size)


capturar("diag_arquitectura", arquitectura(), 1200, 720)
capturar("diag_ciclo", ciclo(), 1200, 640)
capturar("diag_puestos", puestos(), 1200, 560)
