from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app import auth, schemas, state
from app.engine import armas, catalogo, clima, misiones, ota
from app.engine import defensa_aerea
from app.engine import fotos_usuario, modelos_usuario
from app.models.usuario import Usuario

router = APIRouter(prefix="/api", tags=["catalogo"])


@router.get("/catalogo")
def obtener_catalogo(_: Usuario = Depends(auth.usuario_actual)):
    return {
        "clases": state.catalogo_publico(),
        "modelos": state.modelos_publicos(),
        "aeronaves": {"max_grupo": catalogo.MAX_AERONAVES_GRUPO, "max_bando": catalogo.MAX_AERONAVES_BANDO,
                      "max_drones": catalogo.MAX_DRONES_BANDO},
        "escalones": [e for e in catalogo.ESCALONES if e],
        "climas": list(clima.CLIMAS),
        "misiones": misiones.roles_publicos(),
        "ota": ota.armamento_publico(),
        # cargas de armamento por modelo y datos de cada arma (engine/armas.py)
        "armas": armas.publico(),
        "cargas": {m: armas.cargas_de(m) for m in catalogo.MODELOS if catalogo.CLASES[catalogo.MODELOS[m].clase].tipo == "aerea"},
        "nombres_carga": armas.NOMBRES_CARGA,
        "sistemas_da": {k: defensa_aerea.sistema_dict(v) for k, v in defensa_aerea.SISTEMAS.items()},
    }


@router.post("/catalogo/modelos")
def guardar_tipo_propio(payload: dict, _: Usuario = Depends(auth.requiere_roles("instructor"))):
    """Crea o reemplaza (mismo id) un tipo de unidad del catalogo propio; queda disponible al instante."""
    try:
        m = modelos_usuario.guardar(payload)
    except modelos_usuario.TipoInvalido as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    return catalogo.modelo_dict(m)


@router.post("/catalogo/fotos")
def cargar_foto(payload: schemas.FotoIn, _: Usuario = Depends(auth.requiere_roles("instructor"))):
    """El instructor sube la foto de un tipo de unidad o de una clase; el simulador la recorta y la encuadra en el
    formato de las demas (720 x 405 sobre el fondo comun) y la pone al instante."""
    try:
        return fotos_usuario.guardar(payload.seccion, payload.id, payload.imagen, payload.autor, payload.fuente,
                                     payload.recortar)
    except fotos_usuario.FotoInvalida as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.delete("/catalogo/fotos/{seccion}/{id_}")
def quitar_foto(seccion: str, id_: str, _: Usuario = Depends(auth.requiere_roles("instructor"))):
    """Quita la foto del instructor: vuelve la foto de referencia o la ilustracion."""
    if not fotos_usuario.quitar(seccion, id_):
        raise HTTPException(status_code=404, detail="Ese tipo no tiene una foto cargada por el instructor")
    return {"ok": True}


@router.get("/catalogo/fotos/archivo/{nombre}")
def ver_foto(nombre: str, _: Usuario = Depends(auth.usuario_actual)):
    ruta = fotos_usuario.archivo(nombre)
    if ruta is None:
        raise HTTPException(status_code=404, detail="Foto no encontrada")
    return FileResponse(ruta, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=31536000"})


@router.delete("/catalogo/modelos/{modelo_id}")
def eliminar_tipo_propio(modelo_id: str, _: Usuario = Depends(auth.requiere_roles("instructor"))):
    """Quita un tipo propio. Las unidades que ya lo usan siguen con sus valores y la clase de siempre."""
    if not modelo_id.startswith(modelos_usuario.PREFIJO) or not modelos_usuario.eliminar(modelo_id):
        raise HTTPException(status_code=404, detail="Tipo propio no encontrado")
    fotos_usuario.quitar("modelos", modelo_id)  # su foto, si tenia
    return {"ok": True}
