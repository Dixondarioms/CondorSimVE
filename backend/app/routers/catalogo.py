from fastapi import APIRouter, Depends, HTTPException

from app import auth, state
from app.engine import catalogo, clima, misiones
from app.engine import modelos_usuario
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
    }


@router.post("/catalogo/modelos")
def guardar_tipo_propio(payload: dict, _: Usuario = Depends(auth.requiere_roles("instructor"))):
    """Crea o reemplaza (mismo id) un tipo de unidad del catalogo propio; queda disponible al instante."""
    try:
        m = modelos_usuario.guardar(payload)
    except modelos_usuario.TipoInvalido as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    return catalogo.modelo_dict(m)


@router.delete("/catalogo/modelos/{modelo_id}")
def eliminar_tipo_propio(modelo_id: str, _: Usuario = Depends(auth.requiere_roles("instructor"))):
    """Quita un tipo propio. Las unidades que ya lo usan siguen con sus valores y la clase de siempre."""
    if not modelo_id.startswith(modelos_usuario.PREFIJO) or not modelos_usuario.eliminar(modelo_id):
        raise HTTPException(status_code=404, detail="Tipo propio no encontrado")
    return {"ok": True}
