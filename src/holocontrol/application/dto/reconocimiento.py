from dataclasses import dataclass
from holocontrol.domain.errores import ErrorDominio
from holocontrol.domain.rules.validacion import validar_numero, validar_entero, validar_texto


@dataclass(frozen=True)
class Reconocimiento:
    """Un resultado por fotograma, incluso si no se detecta mano o gesto.

    generacion procede de iniciar_control/reanudar_control. Captured_at utiliza
    el mismo reloj monotónico del proceso. x/y son puntos normalizados crudos;
    la aplicación aplica calibración, sensibilidad y suavizado.
    """
    generacion: int
    instante_captura: float
    mano_detectada: bool
    id_gesto: str | None = None
    confianza: float = 0.0
    x: float | None = None
    y: float | None = None

    def __post_init__(self):
        validar_entero(self.generacion, "Generación", 0, 2**63 - 1)
        validar_numero(self.instante_captura, "Instante", 0, 1e15)
        validar_numero(self.confianza, "Confianza", 0, 1)
        if type(self.mano_detectada) is not bool:
            raise ErrorDominio("Detección inválida.")
        if self.id_gesto is not None:
            validar_texto(self.id_gesto, "Gesto")
        if (self.x is None) != (self.y is None):
            raise ErrorDominio("Indique ambas coordenadas.")
        if self.x is not None:
            validar_numero(self.x, "Coordenada x", 0, 1)
            validar_numero(self.y, "Coordenada y", 0, 1)
