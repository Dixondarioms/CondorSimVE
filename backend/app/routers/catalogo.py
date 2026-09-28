from fastapi import APIRouter, Depends

from app import auth, state
from app.engine import catalogo, clima
from app.models.usuario import Usuario

router = APIRouter(prefix="/api", tags=["catalogo"])


@router.get("/catalogo")
def obtener_catalogo(_: Usuario = Depends(auth.usuario_actual)):
    return {
        "clases": state.catalogo_publico(),
        "modelos": state.modelos_publicos(),
        "aeronaves": {"max_grupo": catalogo.MAX_AERONAVES_GRUPO, "max_bando": catalogo.MAX_AERONAVES_BANDO},
        "escalones": [e for e in catalogo.ESCALONES if e],
        "climas": list(clima.CLIMAS),
    }
