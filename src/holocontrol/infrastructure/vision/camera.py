from time import monotonic_ns
from typing import Self

from holocontrol.infrastructure.vision.configuration import ConfiguracionCamara
from holocontrol.infrastructure.vision.errors import ErrorCamara
from holocontrol.ports.vision.models import Fotograma


class CamaraOpenCV:
    def __init__(self, configuracion: ConfiguracionCamara | None = None) -> None:
        self.configuracion = configuracion or ConfiguracionCamara()
        self._captura = None
        self._ultimo_instante_ms = -1

    def abrir(self) -> None:
        import cv2

        if self._captura is not None:
            return
        captura = cv2.VideoCapture(self.configuracion.indice)
        try:
            if not captura.isOpened():
                raise ErrorCamara(
                    f"No se puede abrir la cámara {self.configuracion.indice}. "
                    "Revisa los permisos y si otra aplicación la está utilizando."
                )
            # Son solicitudes al controlador; el fotograma conserva su tamaño real.
            captura.set(cv2.CAP_PROP_FRAME_WIDTH, self.configuracion.ancho)
            captura.set(cv2.CAP_PROP_FRAME_HEIGHT, self.configuracion.alto)
            captura.set(cv2.CAP_PROP_FPS, self.configuracion.fps)
            captura.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            captura.release()
            raise
        self._captura = captura

    def leer(self) -> Fotograma:
        import cv2

        if self._captura is None:
            raise ErrorCamara("La cámara no está abierta.")
        try:
            correcto, imagen = self._captura.read()
        except cv2.error as error:
            raise ErrorCamara("Falló la lectura de cámara. Reconecta el dispositivo.") from error
        if not correcto or imagen is None or imagen.size == 0:
            raise ErrorCamara("La cámara dejó de entregar imágenes. Revisa su conexión.")
        instante_ms = max(monotonic_ns() // 1_000_000, self._ultimo_instante_ms + 1)
        self._ultimo_instante_ms = instante_ms
        if self.configuracion.espejo:
            imagen = cv2.flip(imagen, 1)
        return Fotograma(imagen, instante_ms, en_espejo=self.configuracion.espejo)

    def cerrar(self) -> None:
        if self._captura is not None:
            captura, self._captura = self._captura, None
            captura.release()

    def __enter__(self) -> Self:
        self.abrir()
        return self

    def __exit__(self, *_argumentos) -> None:
        self.cerrar()
