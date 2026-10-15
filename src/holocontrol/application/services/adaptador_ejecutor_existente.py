from typing import Protocol


class ContratoEjecutorExistente(Protocol):
    """Se mantienen para compatibilidad."""
    def activate(self) -> None: ...
    def pause(self) -> None: ...
    def stop(self) -> None: ...
    def set_hand_detected(self, detected: bool) -> None: ...
    def move_cursor(self, x: int, y: int) -> None: ...
    def left_click(self) -> None: ...
    def right_click(self) -> None: ...
    def scroll(self, amount: int) -> None: ...


class AdaptadorEjecutorExistente:
    """Conecta nuestro contrato en español sin modificar el ejecutor recibido."""

    def __init__(self, ejecutor: ContratoEjecutorExistente):
        self._ejecutor = ejecutor

    def activar(self) -> None:
        self._ejecutor.activate()

    def pausar(self) -> None:
        self._ejecutor.pause()

    def detener(self) -> None:
        self._ejecutor.stop()

    def establecer_mano_detectada(self, detectado: bool) -> None:
        self._ejecutor.set_hand_detected(detectado)

    def mover_cursor(self, x: int, y: int) -> None:
        self._ejecutor.move_cursor(x, y)

    def clic_izquierdo(self) -> None:
        self._ejecutor.left_click()

    def clic_derecho(self) -> None:
        self._ejecutor.right_click()

    def desplazar(self, cantidad: int) -> None:
        self._ejecutor.scroll(cantidad)
