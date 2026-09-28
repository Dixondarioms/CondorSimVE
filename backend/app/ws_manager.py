from dataclasses import dataclass

from fastapi import WebSocket
from sqlalchemy.orm import Session

from app import state
from app.models.escenario import Escenario


@dataclass(eq=False)
class Conexion:
    websocket: WebSocket
    usuario_id: int
    rol: str
    vista: str | None = None  # solo instructores: "azul" | "rojo" para "ver como" ese bando

    @property
    def rol_efectivo(self) -> str:
        return self.vista or self.rol


class ConnectionManager:
    """Conexiones WebSocket agrupadas por escenario. Cada conexion recibe el
    estado filtrado segun su rol (niebla de guerra), nunca el estado completo."""

    def __init__(self) -> None:
        self._conexiones: dict[int, list[Conexion]] = {}

    def conexiones(self, escenario_id: int) -> list[Conexion]:
        return list(self._conexiones.get(escenario_id, []))

    async def conectar(self, escenario_id: int, websocket: WebSocket, usuario) -> Conexion:
        await websocket.accept()
        c = Conexion(websocket, usuario.id, usuario.rol)
        self._conexiones.setdefault(escenario_id, []).append(c)
        return c

    def desconectar(self, escenario_id: int, conexion: Conexion) -> None:
        lista = self._conexiones.get(escenario_id, [])
        if conexion in lista:
            lista.remove(conexion)

    async def enviar_estado(self, db: Session, escenario: Escenario, conexion: Conexion) -> None:
        await conexion.websocket.send_json(state.estado_para(db, escenario, conexion.rol_efectivo))

    async def difundir_estado(self, db: Session, escenario: Escenario) -> None:
        vistas: dict[str, dict] = {}
        for c in self.conexiones(escenario.id):
            rol = c.rol_efectivo
            clave = rol if state.es_bando(rol) else "completa"
            if clave not in vistas:
                vistas[clave] = state.estado_para(db, escenario, rol)
            try:
                await c.websocket.send_json(vistas[clave])
            except Exception:
                self.desconectar(escenario.id, c)

    async def difundir_grafico(self, escenario_id: int, mensaje: dict, bando: str) -> None:
        """Envia un cambio de graficos tacticos solo a quienes pueden ver los del `bando`."""
        for c in self.conexiones(escenario_id):
            if not state.grafico_visible(bando, c.rol_efectivo):
                continue
            try:
                await c.websocket.send_json(mensaje)
            except Exception:
                self.desconectar(escenario_id, c)

    async def expulsar(self, usuario_id: int) -> None:
        for escenario_id, lista in list(self._conexiones.items()):
            for c in list(lista):
                if c.usuario_id == usuario_id:
                    self.desconectar(escenario_id, c)
                    try:
                        await c.websocket.close(code=4401)
                    except Exception:
                        pass


manager = ConnectionManager()
