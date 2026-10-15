from typing import Protocol, runtime_checkable

from holocontrol.ports.vision.models import (
    DeteccionManos,
    EstadoVision,
    Fotograma,
    MuestraPostura,
    PlantillaGesto,
    ResultadoVision,
)


class FuenteCamara(Protocol):
    def abrir(self) -> None: ...

    def leer(self) -> Fotograma: ...

    def cerrar(self) -> None: ...


class DetectorManos(Protocol):
    def detectar(self, fotograma: Fotograma) -> DeteccionManos: ...

    def cerrar(self) -> None: ...


@runtime_checkable
class ProveedorVision(Protocol):
    """Un consumidor obtiene el estado reciente y drena los eventos pendientes en orden.

    Los eventos se entregan una vez, incluso al perder la mano o cerrar. El consumidor
    valida vigencia, estado del control y asignaciones antes de autorizar acciones.
    """

    @property
    def estado(self) -> EstadoVision: ...

    @property
    def en_ejecucion(self) -> bool: ...

    @property
    def camara_disponible(self) -> bool: ...

    def iniciar(self) -> None: ...

    def obtener_resultado(self, espera_s: float = 0.0) -> ResultadoVision | None:
        """Devuelve None si no hay novedades; espera_s=0 no espera datos de cámara."""
        ...

    def activar_vista_previa(self, activa: bool) -> None: ...

    def obtener_fotograma(self) -> Fotograma | None: ...

    def detener(self, espera_s: float = 2.0) -> bool: ...


class EntrenadorVision(Protocol):
    @property
    def muestras(self) -> tuple[MuestraPostura, ...]: ...

    def registrar(self, deteccion: DeteccionManos) -> MuestraPostura: ...

    def finalizar(self, nombre: str, umbral_similitud: float = 0.8) -> PlantillaGesto: ...

    def reiniciar(self) -> None: ...
