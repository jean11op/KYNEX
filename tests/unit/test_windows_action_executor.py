
from unittest.mock import patch

import pytest

from holocontrol.infrastructure.windows.windows_action_executor import (
    WindowsActionExecutor,
)
from holocontrol.domain.value_objects.estado_control import EstadoControl

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

def test_held_left_click_gesture_clicks_only_once():
    executor = create_active_executor()

    with patch(
        "holocontrol.infrastructure.windows.windows_action_executor.pyautogui.click"
    ) as click:
        executor.handle_left_click_gesture(True)
        executor.handle_left_click_gesture(True)
        executor.handle_left_click_gesture(True)

    click.assert_called_once_with(button="left")


def test_new_left_click_gesture_allows_another_click():
    executor = create_active_executor()

    with patch(
        "holocontrol.infrastructure.windows.windows_action_executor.pyautogui.click"
    ) as click:
        executor.handle_left_click_gesture(True)
        executor.handle_left_click_gesture(False)
        executor.handle_left_click_gesture(True)

    assert click.call_count == 2


def test_held_right_click_gesture_clicks_only_once():
    executor = create_active_executor()

    with patch(
        "holocontrol.infrastructure.windows.windows_action_executor.pyautogui.click"
    ) as click:
        executor.handle_right_click_gesture(True)
        executor.handle_right_click_gesture(True)

    click.assert_called_once_with(button="right")


def test_hand_loss_resets_click_gesture():
    executor = create_active_executor()

    with patch(
        "holocontrol.infrastructure.windows.windows_action_executor.pyautogui.click"
    ) as click:
        executor.handle_left_click_gesture(True)
        executor.set_hand_detected(False)

        executor.set_hand_detected(True)
        executor.handle_left_click_gesture(True)

    assert click.call_count == 2
    
def test_executor_starts_stopped():
    executor = WindowsActionExecutor()

    assert executor._state is EstadoControl.STOPPED


def test_activate_without_hand_does_not_allow_actions():
    executor = WindowsActionExecutor()
    executor.activate()

    with pytest.raises(RuntimeError):
        executor.move_cursor(100, 100)


def test_pause_changes_state():
    executor = create_active_executor()

    executor.pause()

    assert executor._state is EstadoControl.PAUSED


def test_stop_changes_state_and_loses_hand():
    executor = create_active_executor()

    executor.stop()

    assert executor._state is EstadoControl.STOPPED
    assert executor._hand_detected is False
    
def test_move_cursor_clamps_coordinates_to_screen():
    executor = create_active_executor()

    with (
        patch(
            "holocontrol.infrastructure.windows.windows_action_executor.pyautogui.size",
            return_value=(1920, 1080),
        ),
        patch(
            "holocontrol.infrastructure.windows.windows_action_executor.pyautogui.moveTo"
        ) as move_to,
    ):
        executor.move_cursor(2500, -100)

    move_to.assert_called_once_with(1919, 0, duration=0)


def test_scroll_calls_pyautogui():
    executor = create_active_executor()

    with patch(
        "holocontrol.infrastructure.windows.windows_action_executor.pyautogui.scroll"
    ) as scroll:
        executor.scroll(3)

    scroll.assert_called_once_with(3)


def test_zero_scroll_does_not_call_pyautogui():
    executor = create_active_executor()

    with patch(
        "holocontrol.infrastructure.windows.windows_action_executor.pyautogui.scroll"
    ) as scroll:
        executor.scroll(0)

    scroll.assert_not_called()


def test_scroll_is_blocked_when_paused():
    executor = create_active_executor()
    executor.pause()

    with patch(
        "holocontrol.infrastructure.windows.windows_action_executor.pyautogui.scroll"
    ) as scroll:
        with pytest.raises(RuntimeError):
            executor.scroll(3)

    scroll.assert_not_called()


def test_scroll_is_blocked_when_hand_is_lost():
    executor = create_active_executor()
    executor.set_hand_detected(False)

    with patch(
        "holocontrol.infrastructure.windows.windows_action_executor.pyautogui.scroll"
    ) as scroll:
        with pytest.raises(RuntimeError):
            executor.scroll(3)

    scroll.assert_not_called()
