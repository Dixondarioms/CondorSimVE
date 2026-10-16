import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import auth as auth_mod
from app import respaldo, turnos
from app.db import SessionLocal, init_db
from app.routers import auth, catalogo, clima, escenarios, evaluacion, graficos, misiones, naciones, objetivos, ordenes, plantillas, pmo, tiem, terreno, unidades, usuarios, ws
from app.terreno import get_terreno

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
log = logging.getLogger("uvicorn.error")

# Todo se sirve desde el mismo origen (sin CDN): la CSP bloquea cualquier recurso externo.
CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; connect-src 'self' ws: wss:; media-src 'self' blob:; frame-ancestors 'none'; "
    "base-uri 'none'; form-action 'none'"
)
# media-src blob: el video del aguila de acceso se carga entero en memoria (js/aguila.js) para poder repetirlo.
# form-action 'none': ningun formulario se envia sin JavaScript (si se pulsa Ingresar antes de que cargue la pagina,
# el navegador no manda usuario y contrasena en la direccion); los dialogos (method="dialog") no navegan y siguen igual.


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with SessionLocal() as db:
        if auth_mod.crear_admin_si_no_hay_usuarios(db):
            log.warning(
                "Base sin usuarios: se creo el administrador '%s' con la contrasena inicial '%s'. "
                "Se pedira cambiarla al entrar por primera vez.",
                auth_mod.ADMIN_INICIAL, auth_mod.CLAVE_INICIAL,
            )
    if not get_terreno().disponible:
        log.warning("Sin datos de terreno: ejecute tools/preparar_terreno.py (todo sera 'llano').")

    tareas = [asyncio.create_task(turnos.vigilar_plazos())]
    horas = float(os.environ.get("SIMULADOR_RESPALDO_HORAS", "6"))
    if horas > 0:
        await asyncio.to_thread(respaldo.hacer_respaldo_configurado)
        tareas.append(asyncio.create_task(respaldo.respaldar_periodicamente(horas)))
    try:
        yield
    finally:
        for t in tareas:
            t.cancel()
        await asyncio.gather(*tareas, return_exceptions=True)


# La aplicacion se sirve desde el mismo origen que el frontend: no se habilita CORS.
app = FastAPI(title="Simulador de Conduccion Militar (estilo Fenix)", lifespan=lifespan)


@app.middleware("http")
async def cabeceras_de_seguridad(request: Request, call_next):
    respuesta = await call_next(request)
    respuesta.headers["Content-Security-Policy"] = CSP
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["X-Frame-Options"] = "DENY"
    respuesta.headers["Referrer-Policy"] = "no-referrer"
    ruta = request.url.path
    if ruta.startswith("/api/"):
        respuesta.headers["Cache-Control"] = "no-store"
    elif ruta == "/" or ruta.endswith((".js", ".css", ".html")):
        # el codigo de la interfaz se revalida siempre (ETag -> 304): tras actualizar el servidor nadie queda
        # con JavaScript viejo en cache. Las teselas e imagenes mantienen la cache normal del navegador.
        respuesta.headers["Cache-Control"] = "no-cache"
    if request.url.scheme == "https":
        respuesta.headers["Strict-Transport-Security"] = "max-age=31536000"
    return respuesta


app.include_router(auth.router)
app.include_router(usuarios.router)
app.include_router(escenarios.router)
app.include_router(clima.router)
app.include_router(unidades.router)
app.include_router(ordenes.router)
app.include_router(misiones.router)
app.include_router(terreno.router)
app.include_router(graficos.router)
app.include_router(objetivos.router)
app.include_router(pmo.router)
app.include_router(tiem.router)
app.include_router(naciones.router)
app.include_router(plantillas.router)
app.include_router(catalogo.router)
app.include_router(evaluacion.router)
app.include_router(ws.router)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")
