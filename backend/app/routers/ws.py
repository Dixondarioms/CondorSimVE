import json

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app import auth, comunicaciones
from app.db import get_db
from app.ws_manager import manager

router = APIRouter()


@router.websocket("/ws/{escenario_id}")
async def websocket_escenario(
    websocket: WebSocket, escenario_id: int, db: Session = Depends(get_db)
):
    usuario = auth.usuario_ws(websocket, db)
    if usuario is None:
        await websocket.close(code=4401)
        return
    try:
        escenario = auth.escenario_accesible(db, escenario_id, usuario)
    except HTTPException:
        await websocket.close(code=4404)
        return

    conexion = await manager.conectar(escenario_id, websocket, usuario)
    try:
        await manager.enviar_estado(db, escenario, conexion)
        await websocket.send_json({"tipo": "chat_historial", "mensajes": comunicaciones.historial_para(db, escenario, usuario)})
        while True:
            texto = await websocket.receive_text()
            if not texto.startswith("{"):
                continue  # keep-alive
            try:
                datos = json.loads(texto)
            except ValueError:
                continue
            if not isinstance(datos, dict):
                continue
            db.expire_all()
            if datos.get("tipo") == "chat":
                error = await comunicaciones.procesar(manager, db, escenario, usuario, datos)
                if error:
                    await websocket.send_json({"tipo": "chat_error", "detalle": error})
            elif usuario.rol == "instructor" and "vista" in datos:
                # "Ver como": el instructor elige que bando quiere ver (o la vista completa).
                if datos["vista"] in ("azul", "rojo", "completa"):
                    conexion.vista = None if datos["vista"] == "completa" else datos["vista"]
                    await manager.enviar_estado(db, escenario, conexion)
    except WebSocketDisconnect:
        pass
    finally:
        manager.desconectar(escenario_id, conexion)
