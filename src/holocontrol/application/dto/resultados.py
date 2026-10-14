from dataclasses import dataclass
from holocontrol.domain.value_objects.estado_control import EstadoControl

@dataclass(frozen=True)
class EstadoActualControl:
    estado: EstadoControl
    id_perfil_seleccionado: str | None
    generacion: int
    mano_detectada: bool
    camara_disponible: bool
    error: str | None


@dataclass(frozen=True)
class ResultadoGesto:
    ejecutado: bool
    motivo: str
    id_accion: str | None = None
