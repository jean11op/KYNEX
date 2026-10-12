
import pyautogui

from holocontrol.ports.system_actions.action_executor import ActionExecutor


class WindowsActionExecutor(ActionExecutor):
    """Implementa acciones del ratón para Windows."""

    def __init__(self, click_cooldown: float = 0.4):
        if click_cooldown < 0:
            raise ValueError("El tiempo entre clics no puede ser negativo.")

        self._enabled = False
        self._hand_detected = False
        self._click_cooldown = click_cooldown
        self._last_click_time = float("-inf")

        # Mover el ratón a la esquina superior izquierda
        # activa el mecanismo de seguridad de PyAutoGUI.
        pyautogui.FAILSAFE = True

    def activate(self) -> None:
        """Permite ejecutar acciones cuando se detecta una mano."""
        self._enabled = True

    def pause(self) -> None:
        """Bloquea temporalmente todas las acciones."""
        self._enabled = False

    def stop(self) -> None:
        """Detiene el control hasta una activación posterior."""
        self._enabled = False
        self._hand_detected = False

    def set_hand_detected(self, detected: bool) -> None:
        """Actualiza si el sistema de visión detecta una mano."""
        self._hand_detected = detected

    def _ensure_allowed(self) -> None:
        if not self._enabled:
            raise RuntimeError("El control está pausado o detenido.")

        if not self._hand_detected:
            raise RuntimeError("No se detecta una mano.")

    def move_cursor(self, x: int, y: int) -> None:
        self._ensure_allowed()

        screen_width, screen_height = pyautogui.size()

        x = max(0, min(x, screen_width - 1))
        y = max(0, min(y, screen_height - 1))

        pyautogui.moveTo(x, y, duration=0)

    def left_click(self) -> None:
        self._ensure_allowed()
        self._click()

    def right_click(self) -> None:
        self._ensure_allowed()
        self._click(button="right")

    def _click(self, button: str = "left") -> None:
        import time

        now = time.monotonic()

        if now - self._last_click_time < self._click_cooldown:
            return

        pyautogui.click(button=button)
        self._last_click_time = now

    def scroll(self, amount: int) -> None:
        self._ensure_allowed()

        if amount != 0:
            pyautogui.scroll(amount)
