
from abc import ABC, abstractmethod


class ActionExecutor(ABC):
    """Contrato para ejecutar acciones sobre el sistema operativo."""

    @abstractmethod
    def move_cursor(self, x: int, y: int) -> None:
        """Mueve el cursor a las coordenadas indicadas."""
        raise NotImplementedError

    @abstractmethod
    def left_click(self) -> None:
        """Ejecuta un clic izquierdo."""
        raise NotImplementedError

    @abstractmethod
    def right_click(self) -> None:
        """Ejecuta un clic derecho."""
        raise NotImplementedError

    @abstractmethod
    def scroll(self, amount: float) -> None:
        """Desplaza el contenido de la ventana activa."""
        raise NotImplementedError
