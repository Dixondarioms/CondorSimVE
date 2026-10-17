import secrets
from datetime import datetime, timezone

from sqlalchemy import false, true, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _ahora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Escenario(Base):
    __tablename__ = "escenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200))
    turno_actual: Mapped[int] = mapped_column(Integer, default=1)
    # fase: "decision" (los alumnos emiten ordenes) | "resolucion" (el motor resuelve)
    fase: Mapped[str] = mapped_column(String(20), default="decision")
    # estado: "activo" | "pausado" | "finalizado"
    estado: Mapped[str] = mapped_column(String(20), default="activo")
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=_ahora)

    # clima: "despejado" | "nublado" | "lluvia" | "tormenta"
    clima: Mapped[str] = mapped_column(String(20), default="despejado")
    # azar: los combates incluyen variacion aleatoria reproducible (semilla + turno + unidades)
    azar: Mapped[bool] = mapped_column(Boolean, default=False)
    semilla: Mapped[int] = mapped_column(Integer, default=lambda: secrets.randbelow(2**31))

    # mecanica de turnos
    auto_resolver: Mapped[bool] = mapped_column(Boolean, default=False)
    limite_decision_seg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decision_termina_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    listo_azul: Mapped[bool] = mapped_column(Boolean, default=False)
    listo_rojo: Mapped[bool] = mapped_column(Boolean, default=False)

    archivado: Mapped[bool] = mapped_column(Boolean, default=False)

    # comunicaciones simuladas (chat): demora base, variacion y probabilidad de perdida por interferencia
    com_latencia_ms: Mapped[int] = mapped_column(Integer, default=0)
    com_jitter_ms: Mapped[int] = mapped_column(Integer, default=0)
    com_perdida_pct: Mapped[int] = mapped_column(Integer, default=0)
    # % de ordenes que no llegan a tiempo y se cumplen el turno siguiente (+40 dentro de una interferencia enemiga)
    com_ordenes_pct: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # hora simulada del turno 1, en minutos desde medianoche (cada turno dura 1 h)
    hora_inicio_min: Mapped[int] = mapped_column(Integer, default=360)

    # interruptores del motor (herramientas de direccion): niebla de guerra, consumo/reabastecimiento, efectos del
    # clima y fuego automatico (patrullas y antiaerea). Apagarlos simplifica el ejercicio para fines didacticos.
    niebla: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    logistica: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    efectos_clima: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    fuego_automatico: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    # adversario automatico: el simulador da las ordenes de ese bando al abrirse cada turno (ver app/adversario.py)
    ia_azul: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    ia_rojo: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # prudente | normal | agresiva: cuanto riesgo toma el adversario automatico (ver app/adversario.py)
    ia_nivel: Mapped[str] = mapped_column(String(10), default="normal", server_default="normal")
    # ciclo de dia y noche: de noche se detecta menos a simple vista (ver engine/clima.py, periodo_del_dia)
    dia_noche: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # disponibilidad y fallas de las aeronaves (engine/disponibilidad.py), plantilla de personal de cada bando
    # (engine/toe.py: cobertura, reservas activas, milicianos, tripulaciones por aeronave) y esfuerzo aereo
    fallas: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    personal_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    derribados_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # engine/rescate.py
    esfuerzo_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # identidad nacional de cada bando (ver engine/naciones.py); "" = sin especificar (se muestra "Azul"/"Rojo")
    nacion_azul: Mapped[str] = mapped_column(String(20), default="venezuela")
    nacion_rojo: Mapped[str] = mapped_column(String(20), default="")

    # quien conduce cada bando (a eleccion del instructor): "alumnos" | "instructor"; el adversario automatico se
    # enciende aparte con ia_azul / ia_rojo y tiene prioridad (ver la propiedad `conduccion`)
    conduce_azul: Mapped[str] = mapped_column(String(12), default="alumnos", server_default="alumnos")
    conduce_rojo: Mapped[str] = mapped_column(String(12), default="alumnos", server_default="alumnos")

    # calendario de la operacion (TIEM, ver engine/calendario.py): fecha del turno 1 ("AAAA-MM-DD"), turno en que
    # cae la hora H (el dia D es la fecha de ese turno), ultimo turno previsto y fases de la operacion
    # [{"nombre", "desde", "hasta"}] en turnos. Todo opcional: sin fecha no se muestra el calendario.
    fecha_inicio: Mapped[str | None] = mapped_column(String(10), nullable=True)
    turno_h: Mapped[int | None] = mapped_column(Integer, nullable=True)
    turno_final: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fases_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # juego de guerra (TIEM): esta es la copia de ensayo de una F/A del escenario `ensayo_de`, para el bando
    # `ensayo_bando`, creada en el turno `ensayo_desde` (ver app/ensayos.py)
    ensayo_de: Mapped[int | None] = mapped_column(ForeignKey("escenarios.id"), nullable=True)
    ensayo_bando: Mapped[str | None] = mapped_column(String(10), nullable=True)
    ensayo_fa: Mapped[str] = mapped_column(String(300), default="", server_default="")
    ensayo_desde: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def conduccion(self, bando: str) -> str:
        """alumnos | instructor | ia: quien da las ordenes de ese bando."""
        if getattr(self, f"ia_{bando}", False):
            return "ia"
        return "instructor" if getattr(self, f"conduce_{bando}", "") == "instructor" else "alumnos"

    @property
    def personal(self) -> dict:
        """Configuracion de personal de cada bando (engine/toe.py)."""
        from app.engine import toe

        return {b: toe.config(self, b) for b in ("azul", "rojo")}

    @property
    def periodo(self) -> str:
        """dia | crepusculo | noche del turno en curso ("dia" si el ciclo de dia y noche esta apagado)."""
        from app.engine.clima import periodo_de  # importacion tardia: el motor importa los modelos

        return periodo_de(self)

    @property
    def conduccion_azul(self) -> str:
        return self.conduccion("azul")

    @property
    def conduccion_rojo(self) -> str:
        return self.conduccion("rojo")

    @property
    def calendario(self) -> dict | None:
        """Dia D, hora H, fases y referencia del turno en curso (ver engine/calendario.py); None si no hay."""
        from app.engine.calendario import resumen  # importacion tardia: el motor importa los modelos

        return resumen(self)
