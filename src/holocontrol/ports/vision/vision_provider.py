from typing import Protocol

from holocontrol.ports.vision.models import (
    DeteccionManos,
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


class ProveedorVision(Protocol):
    """El consumidor valida vigencia, estado del control y asignaciones antes de actuar."""

    def iniciar(self) -> None: ...

    def obtener_resultado(self, espera_s: float = 0.0) -> ResultadoVision | None: ...

    def activar_vista_previa(self, activa: bool) -> None: ...

    def obtener_fotograma(self) -> Fotograma | None: ...

    def detener(self, espera_s: float = 2.0) -> bool: ...


class EntrenadorVision(Protocol):
    @property
    def muestras(self) -> tuple[MuestraPostura, ...]: ...

    def registrar(self, deteccion: DeteccionManos) -> MuestraPostura: ...

    def finalizar(self, nombre: str, umbral_similitud: float = 0.8) -> PlantillaGesto: ...

    def reiniciar(self) -> None: ...
