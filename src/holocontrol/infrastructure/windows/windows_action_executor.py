
import math
import time
from collections.abc import Callable

import pyautogui

from holocontrol.application.services.click_controller import ClickController
from holocontrol.infrastructure.windows.background_execution import BackgroundExecution
from holocontrol.domain.value_objects.control_state import ControlState
from holocontrol.ports.system_actions.action_executor import ActionExecutor


class WindowsActionExecutor(ActionExecutor):
    """Implementa acciones controladas del ratón para Windows."""

    def __init__(
        self,
        click_cooldown: float = 0.4,
        clock: Callable[[], float] = time.monotonic,
    ):
        if not math.isfinite(click_cooldown) or click_cooldown < 0:
            raise ValueError("El tiempo entre clics debe ser finito y no negativo.")
        if not callable(clock):
            raise TypeError("clock debe ser una función que devuelva el tiempo monotónico.")

        self._background = BackgroundExecution()
        self._state = ControlState.STOPPED
        self._hand_detected = False
        self._click_cooldown = click_cooldown
        self._clock = clock
        self._last_click_time = float("-inf")
        self._pinch_started = None
        self._dragging = False
        self._switching = False
        self._switch_anchor = 0.0

        # Cada tipo de clic tiene su propio control de gesto.
        self._left_click_controller = ClickController()
        self._right_click_controller = ClickController()

        # Mecanismo de seguridad de PyAutoGUI.
        pyautogui.FAILSAFE = True

    def activate(self) -> None:
        """Activa el control; requiere detectar una mano."""
        self._background.acquire()
        self._state = ControlState.ACTIVE

    def pause(self) -> None:
        """Pausa temporalmente el control."""
        self.end_window_switch(cancel=True)
        self.end_pinch(cancel=True)
        self._background.release()
        self._state = ControlState.PAUSED
        self._reset_click_gestures()

    def stop(self) -> None:
        """Detiene el control y elimina la detección de mano."""
        self.end_window_switch(cancel=True)
        self.end_pinch(cancel=True)
        self._background.release()
        self._state = ControlState.STOPPED
        self._hand_detected = False
        self._reset_click_gestures()
        self._last_click_time = float("-inf")

    def set_hand_detected(self, detected: bool) -> None:
        """Actualiza la detección de la mano."""
        self._hand_detected = detected

        if not detected:
            self.end_window_switch(cancel=True)
            self.end_pinch(cancel=True)
            self._reset_click_gestures()
            self._last_click_time = float("-inf")

    def _reset_click_gestures(self) -> None:
        self._left_click_controller.reset()
        self._right_click_controller.reset()

    def _ensure_allowed(self) -> None:
        if self._state is not ControlState.ACTIVE:
            raise RuntimeError("El control no está activo.")

        if not self._hand_detected:
            raise RuntimeError("No se detecta una mano.")

    def move_cursor(self, x: int, y: int) -> None:
        self._ensure_allowed()

        screen_width, screen_height = pyautogui.size()
        if screen_width <= 0 or screen_height <= 0:
            raise RuntimeError("PyAutoGUI devolvió dimensiones de pantalla inválidas.")

        # Do not drive the cursor into FAILSAFE corners ourselves. Moving the
        # physical mouse to a corner still triggers PyAutoGUI's safety check.
        x = max(1, min(x, screen_width - 2)) if screen_width > 2 else 0
        y = max(1, min(y, screen_height - 2)) if screen_height > 2 else 0

        # Gesture timing is handled by the application; PyAutoGUI's default
        # 100 ms post-action sleep would throttle every frame. Keep FAILSAFE.
        pyautogui.moveTo(x, y, duration=0, _pause=False)

    def begin_pinch(self, x: int, y: int) -> None:
        self._ensure_allowed()
        if self._pinch_started is None:
            self._pinch_started = self._clock()
            self._pinch_anchor = (x, y)
            self._pointer_anchor = pyautogui.position()

    def update_pinch(self, x: int, y: int) -> None:
        self._ensure_allowed()
        if self._pinch_started is None:
            return
        if not self._dragging and self._clock() - self._pinch_started >= 0.3:
            pyautogui.mouseDown(button='left', _pause=False)
            self._dragging = True
        if self._dragging:
            self.move_cursor(self._pointer_anchor[0] + x - self._pinch_anchor[0],
                             self._pointer_anchor[1] + y - self._pinch_anchor[1])

    def end_pinch(self, cancel=False) -> None:
        if self._dragging:
            # Always release an owned button, even at a FAILSAFE corner. The
            # private Windows release primitive bypasses only that release check.
            try:
                pyautogui.mouseUp(button='left', _pause=False)
            except pyautogui.FailSafeException:
                x, y = pyautogui.position()
                pyautogui.platformModule._mouseUp(x, y, 'left')
            self._dragging = False
        elif self._pinch_started is not None and not cancel:
            self.left_click()
        self._pinch_started = None

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

        if self._left_click_controller.should_click(detected):
            self._click(button="left")

    def handle_right_click_gesture(self, detected: bool) -> None:
        """Ejecuta un clic por cada nuevo gesto derecho."""
        self._ensure_allowed()

        if self._right_click_controller.should_click(detected):
            self._click(button="right")

    def _click(self, button: str = "left") -> None:
        now = self._clock()

        if now - self._last_click_time < self._click_cooldown:
            return

        pyautogui.click(button=button, _pause=False)
        self._last_click_time = now


    def scroll(self, amount: int) -> None:
        self._ensure_allowed()

        if amount != 0:
            # The installed Windows backend passes raw wheel units to mouse_event.
            # WHEEL_DELTA is 120 units per wheel notch.
            pyautogui.scroll(amount * 120, _pause=False)

    def minimize_window(self) -> None:
        self._ensure_allowed()
        # SW_MINIMIZE works even when the foreground window is maximized.
        import ctypes
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        user32.ShowWindowAsync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        window = user32.GetForegroundWindow()
        if window:
            user32.ShowWindowAsync(window, 6)

    def begin_window_switch(self, x: float) -> None:
        self._ensure_allowed()
        if self._switching:
            return
        self._switch_anchor = x
        self._switching = True
        try:
            pyautogui.keyDown('alt', _pause=False)
            pyautogui.press('tab', _pause=False)
        except Exception:
            self.end_window_switch(cancel=True)
            raise

    def update_window_switch(self, x: float) -> None:
        self._ensure_allowed()
        if self._switching and abs(x - self._switch_anchor) >= .07:
            steps = int((abs(x - self._switch_anchor) + 1e-9) / .07)
            direction = 1 if x > self._switch_anchor else -1
            for _ in range(steps):
                pyautogui.press('right' if direction > 0 else 'left', _pause=False)
            self._switch_anchor += direction * steps * .07

    def end_window_switch(self, cancel: bool = False) -> None:
        if not self._switching:
            return
        try:
            if cancel:
                pyautogui.press('esc', _pause=False)
        finally:
            try:
                pyautogui.keyUp('alt', _pause=False)
            except pyautogui.FailSafeException:
                pyautogui.platformModule._keyUp('alt')
            self._switching = False
