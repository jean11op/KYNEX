
class ClickController:
    """Evita repetir un clic mientras se mantiene el mismo gesto."""

    def __init__(self):
        self._gesture_active = False

    def deberia_click(self, gesture_detected: bool) -> bool:
        """Devuelve True únicamente al comenzar un gesto."""

        if gesture_detected and not self._gesture_active:
            self._gesture_active = True
            return True

        if not gesture_detected:
            self._gesture_active = False

        return False

    def resetear(self) -> None:
        """Reinicia el estado del gesto."""
        self._gesture_active = False
