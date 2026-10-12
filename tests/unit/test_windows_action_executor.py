
from unittest.mock import patch

import pytest

from holocontrol.infrastructure.windows.windows_action_executor import (
    WindowsActionExecutor,
)


def create_active_executor():
    executor = WindowsActionExecutor()
    executor.activate()
    executor.set_hand_detected(True)
    return executor


def test_move_cursor_calls_pyautogui():
    executor = create_active_executor()

    with (
        patch("holocontrol.infrastructure.windows.windows_action_executor.pyautogui.size",
              return_value=(1920, 1080)),
        patch("holocontrol.infrastructure.windows.windows_action_executor.pyautogui.moveTo")
        as move_to,
    ):
        executor.move_cursor(500, 300)

    move_to.assert_called_once_with(500, 300, duration=0)


def test_paused_executor_rejects_actions():
    executor = create_active_executor()
    executor.pause()

    with patch(
        "holocontrol.infrastructure.windows.windows_action_executor.pyautogui.moveTo"
    ) as move_to:
        with pytest.raises(RuntimeError):
            executor.move_cursor(500, 300)

    move_to.assert_not_called()


def test_executor_rejects_actions_when_hand_is_lost():
    executor = create_active_executor()
    executor.set_hand_detected(False)

    with patch(
        "holocontrol.infrastructure.windows.windows_action_executor.pyautogui.click"
    ) as click:
        with pytest.raises(RuntimeError):
            executor.left_click()

    click.assert_not_called()


def test_stop_disables_actions():
    executor = create_active_executor()
    executor.stop()

    with pytest.raises(RuntimeError):
        executor.scroll(3)
