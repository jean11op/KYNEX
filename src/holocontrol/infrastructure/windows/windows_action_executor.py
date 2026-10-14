
import pyautogui

from holocontrol.application.services.controlador_click import ClickController
from holocontrol.ports.system_actions.ejecutor_control import EjecutorControl
from holocontrol.domain.value_objects.estado_control import EstadoControl

class WindowsActionExecutor(EjecutorControl):
    """Implementa acciones controladas del ratón para Windows."""

    def __init__(self, click_cooldown: float = 0.4):
        if click_cooldown < 0:
            raise ValueError("El tiempo entre clics no puede ser negativo.")

        self._state = EstadoControl.STOPPED
        self._hand_detected = False
        self._click_cooldown = click_cooldown
        self._last_click_time = float("-inf")

        # Cada tipo de clic tiene su propio control de gesto.
        self._left_click_controller = ClickController()
        self._right_click_controller = ClickController()

        # Mecanismo de seguridad de PyAutoGUI.
        pyautogui.FAILSAFE = True

    def activate(self) -> None:
        """Activa el control; requiere detectar una mano."""
        self._state = EstadoControl.ACTIVE

    def pause(self) -> None:
        """Pausa temporalmente el control."""
        self._state = EstadoControl.PAUSED
        self._reset_click_gestures()

    def stop(self) -> None:
        """Detiene el control y elimina la detección de mano."""
        self._state = EstadoControl.STOPPED
        self._hand_detected = False
        self._reset_click_gestures()
        self._last_click_time = float("-inf")

    def set_hand_detected(self, detected: bool) -> None:
        """Actualiza la detección de la mano."""
        self._hand_detected = detected

        if not detected:
            self._reset_click_gestures()
            self._last_click_time = float("-inf")

    def _reset_click_gestures(self) -> None:
        
        self._left_click_controller.resetear
        self._right_click_controller.resetear

    def _ensure_allowed(self) -> None:
        if self._state is not EstadoControl.ACTIVE:
            raise RuntimeError("El control no está activo.")

        if not self._hand_detected:
            raise RuntimeError("No se detecta una mano.")

    def move_cursor(self, x: int, y: int) -> None:
        self._ensure_allowed()

        screen_width, screen_height = pyautogui.size()

        x = max(0, min(x, screen_width - 1))
        y = max(0, min(y, screen_height - 1))

        pyautogui.moveTo(x, y, duration=0)

    def left_click(self) -> None:
        """Ejecuta un clic izquierdo autorizado."""
        self._ensure_allowed()
        self._click(button="left")

    def right_click(self) -> None:
        """Ejecuta un clic derecho autorizado."""
        self._ensure_allowed()
        self._click(button="right")

    
    def handle_left_click_gesture(self, detected: bool) -> None:
        """Ejecuta un clic por cada nuevo gesto izquierdo."""
        self._ensure_allowed()

        if self._left_click_controller.deberia_click(detected):
            self._click(button="left", new_gesture=True)

    def handle_right_click_gesture(self, detected: bool) -> None:
        """Ejecuta un clic por cada nuevo gesto derecho."""
        self._ensure_allowed()

        if self._right_click_controller.deveria_click(detected):
            self._click(button="right", new_gesture=True)

    def _click(
        self,
        button: str = "left",
        new_gesture: bool = False,
    ) -> None:
        import time

        now = time.monotonic()

        if (
            not new_gesture
            and now - self._last_click_time < self._click_cooldown
        ):
            return

        pyautogui.click(button=button)
        self._last_click_time = now


    def scroll(self, amount: int) -> None:
        self._ensure_allowed()

        if amount != 0:
            pyautogui.scroll(amount)
