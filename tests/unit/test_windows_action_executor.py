
from unittest.mock import patch

import pytest

from holocontrol.domain.value_objects.control_state import ControlState
from holocontrol.infrastructure.windows.windows_action_executor import (
    WindowsActionExecutor,
)


def create_active_executor():
    executor = WindowsActionExecutor()
    executor.activate()
    executor.set_hand_detected(True)
    return executor


def test_real_pyautogui_wrappers_do_not_sleep_after_gesture_actions():
    import pyautogui as api
    executor = create_active_executor()
    with (patch.object(api, 'failSafeCheck') as safety,
          patch.object(api, '_mouseMoveDrag'),
          patch.object(api.platformModule, '_click'),
          patch.object(api.platformModule, '_scroll'),
          patch.object(api.time, 'sleep') as sleep):
        executor.move_cursor(300, 300)
        executor.left_click()
        executor.scroll(1)
    assert safety.call_count >= 3
    assert not any(call.args[0] > 0 for call in sleep.call_args_list)
    assert api.FAILSAFE is True


def test_immediate_actions_still_honor_pyautogui_failsafe():
    import pyautogui as api
    executor = create_active_executor()
    with patch.object(api, 'failSafeCheck', side_effect=api.FailSafeException):
        with pytest.raises(api.FailSafeException):
            executor.move_cursor(300, 300)


def test_move_cursor_calls_pyautogui():
    executor = create_active_executor()

    with (
        patch("holocontrol.infrastructure.windows.windows_action_executor.pyautogui.size",
            return_value=(1920, 1080)),
        patch("holocontrol.infrastructure.windows.windows_action_executor.pyautogui.moveTo")
        as move_to,
    ):
        executor.move_cursor(500, 300)

    move_to.assert_called_once_with(500, 300, duration=0, _pause=False)


@pytest.mark.parametrize("button,method", [("left", "left_click"), ("right", "right_click")])
def test_authorized_click_calls_pyautogui(button, method):
    executor = create_active_executor()

    with patch(
        "holocontrol.infrastructure.windows.windows_action_executor.pyautogui.click"
    ) as click:
        getattr(executor, method)()

    click.assert_called_once_with(button=button, _pause=False)


def test_paused_executor_rejects_actions():
    executor = create_active_executor()
    executor.pause()

    with patch(
        "holocontrol.infrastructure.windows.windows_action_executor.pyautogui.moveTo"
    ) as move_to, pytest.raises(RuntimeError):
        executor.move_cursor(500, 300)

    move_to.assert_not_called()


def test_executor_rejects_actions_when_hand_is_lost():
    executor = create_active_executor()
    executor.set_hand_detected(False)

    with patch(
        "holocontrol.infrastructure.windows.windows_action_executor.pyautogui.click"
    ) as click, pytest.raises(RuntimeError):
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

    click.assert_called_once_with(button="left", _pause=False)


def test_new_left_click_gesture_allows_another_click():
    executor = WindowsActionExecutor(click_cooldown=0)
    executor.activate()
    executor.set_hand_detected(True)

    with patch(
        "holocontrol.infrastructure.windows.windows_action_executor.pyautogui.click"
    ) as click:
        executor.handle_left_click_gesture(True)
        executor.handle_left_click_gesture(False)
        executor.handle_left_click_gesture(True)

    assert click.call_count == 2


def test_click_cooldown_is_applied_to_new_gestures():
    now = [10.0]
    executor = WindowsActionExecutor(click_cooldown=0.5, clock=lambda: now[0])
    executor.activate()
    executor.set_hand_detected(True)

    with patch(
        "holocontrol.infrastructure.windows.windows_action_executor.pyautogui.click"
    ) as click:
        executor.handle_left_click_gesture(True)
        executor.handle_left_click_gesture(False)
        now[0] = 10.49
        executor.handle_left_click_gesture(True)
        executor.handle_left_click_gesture(False)
        now[0] = 10.5
        executor.handle_left_click_gesture(True)

    assert click.call_count == 2


def test_held_right_click_gesture_clicks_only_once():
    executor = create_active_executor()

    with patch(
        "holocontrol.infrastructure.windows.windows_action_executor.pyautogui.click"
    ) as click:
        executor.handle_right_click_gesture(True)
        executor.handle_right_click_gesture(True)

    click.assert_called_once_with(button="right", _pause=False)


def test_left_and_right_gestures_have_independent_state():
    executor = WindowsActionExecutor(click_cooldown=0)
    executor.activate()
    executor.set_hand_detected(True)

    with patch(
        "holocontrol.infrastructure.windows.windows_action_executor.pyautogui.click"
    ) as click:
        executor.handle_left_click_gesture(True)
        executor.handle_right_click_gesture(True)
        executor.handle_left_click_gesture(True)
        executor.handle_right_click_gesture(True)

    assert click.call_args_list == [
        ((), {"button": "left", "_pause": False}),
        ((), {"button": "right", "_pause": False}),
    ]


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


@pytest.mark.parametrize("transition", ["pause", "stop"])
def test_pause_and_stop_reset_click_gesture(transition):
    executor = WindowsActionExecutor(click_cooldown=0)
    executor.activate()
    executor.set_hand_detected(True)

    with patch(
        "holocontrol.infrastructure.windows.windows_action_executor.pyautogui.click"
    ) as click:
        executor.handle_left_click_gesture(True)
        getattr(executor, transition)()
        executor.activate()
        executor.set_hand_detected(True)
        executor.handle_left_click_gesture(True)

    assert click.call_count == 2

def test_executor_starts_stopped():
    executor = WindowsActionExecutor()

    assert executor._state is ControlState.STOPPED


def test_activate_without_hand_does_not_allow_actions():
    executor = WindowsActionExecutor()
    executor.activate()

    with pytest.raises(RuntimeError):
        executor.move_cursor(100, 100)


def test_pause_changes_state():
    executor = create_active_executor()

    executor.pause()

    assert executor._state is ControlState.PAUSED


def test_stop_changes_state_and_loses_hand():
    executor = create_active_executor()

    executor.stop()

    assert executor._state is ControlState.STOPPED
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

    move_to.assert_called_once_with(1918, 1, duration=0, _pause=False)


def test_scroll_uses_normal_wheel_input():
    executor = create_active_executor()

    with (patch('pyautogui.position', return_value=(300, 300)),
          patch('holocontrol.infrastructure.windows.window_context.canva_canvas_point', return_value=None),
          patch('pyautogui.scroll') as scroll):
        executor.scroll(3)

    scroll.assert_called_once_with(360, _pause=False)


@pytest.mark.parametrize("amount", [4, -4])
def test_scroll_passes_positive_and_negative_amounts(amount):
    executor = create_active_executor()

    with (patch('pyautogui.position', return_value=(300, 300)),
          patch('holocontrol.infrastructure.windows.window_context.canva_canvas_point', return_value=None),
          patch('pyautogui.scroll') as scroll):
        executor.scroll(amount)

    scroll.assert_called_once_with(amount * 120, _pause=False)


def test_click_cooldown_must_be_finite_and_nonnegative():
    for cooldown in (-0.1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            WindowsActionExecutor(click_cooldown=cooldown)


def test_invalid_screen_dimensions_are_rejected():
    executor = create_active_executor()

    with patch(
        "holocontrol.infrastructure.windows.windows_action_executor.pyautogui.size",
        return_value=(0, 1080),
    ), patch(
        "holocontrol.infrastructure.windows.windows_action_executor.pyautogui.moveTo"
    ) as move_to, pytest.raises(RuntimeError):
        executor.move_cursor(20, 30)

    move_to.assert_not_called()


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
    ) as scroll, pytest.raises(RuntimeError):
        executor.scroll(3)

    scroll.assert_not_called()


def test_scroll_is_blocked_when_hand_is_lost():
    executor = create_active_executor()
    executor.set_hand_detected(False)

    with patch(
        "holocontrol.infrastructure.windows.windows_action_executor.pyautogui.scroll"
    ) as scroll, pytest.raises(RuntimeError):
        executor.scroll(3)

    scroll.assert_not_called()
