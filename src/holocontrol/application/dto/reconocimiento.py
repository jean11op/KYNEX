from dataclasses import dataclass

from holocontrol.domain.errores import ErrorDominio
from holocontrol.domain.rules.validacion import validar_entero, validar_numero, validar_texto
from holocontrol.ports.vision.models import EstadoVision, EventoGesto, ResultadoVision


@dataclass(frozen=True)
class Reconocimiento:
    """Un resultado por fotograma, incluso si no se detecta mano o gesto.

    generacion procede de iniciar_control/reanudar_control. instante_captura utiliza
    el mismo reloj monotónico del proceso. x/y son puntos normalizados crudos;
    la aplicación aplica calibración, sensibilidad y suavizado.
    Los eventos tienen tiempos propios en milisegundos y se conservan en orden.
    id_gesto/confianza permiten consumir el contrato anterior de un solo gesto.
    """
    generacion: int
    instante_captura: float
    mano_detectada: bool
    id_gesto: str | None = None
    confianza: float = 0.0
    x: float | None = None
    y: float | None = None


    eventos: tuple[EventoGesto, ...] = ()
    desplazamiento_vertical: float = 0.0
    estado_vision: EstadoVision | None = None
    mensaje: str = ""


    @classmethod
    def desde_vision(cls, resultado: ResultadoVision, generacion: int) -> "Reconocimiento":
        """La generación es la del trabajador que produjo el resultado.

        Nunca etiquetar resultados pendientes con la generación de una nueva sesión.
        Convierte milisegundos a segundos y conserva el orden del proveedor.
        """
        punto_indice = resultado.mano.puntos[8] if resultado.es_valido else None
        desplazamiento = resultado.desplazamiento_indice

        return cls(
            generacion=generacion,
            instante_captura=resultado.instante_ms / 1000,
            mano_detectada=resultado.es_valido,
            x=punto_indice.x if punto_indice else None,
            y=punto_indice.y if punto_indice else None,
            eventos=resultado.eventos,
            desplazamiento_vertical=desplazamiento[1] if desplazamiento else 0.0,
            estado_vision=resultado.estado,
            mensaje=resultado.mensaje,
        )

    def __post_init__(self):

        object.__setattr__(self, "eventos", tuple(self.eventos))

        if any(not isinstance(evento, EventoGesto) for evento in self.eventos):
            raise ErrorDominio("Los eventos deben cumplir el contrato de visión.")

        if self.estado_vision is not None and not isinstance(self.estado_vision, EstadoVision):
            raise ErrorDominio("Estado de visión inválido.")

        validar_numero(
            self.desplazamiento_vertical,
            "Desplazamiento vertical",
            -1,
            1,
        )

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
