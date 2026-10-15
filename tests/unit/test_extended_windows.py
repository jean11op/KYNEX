from unittest.mock import Mock, patch
import pytest
from holocontrol.infrastructure.windows.windows_action_executor import WindowsActionExecutor


def active():
    e=WindowsActionExecutor()
    e.activate()
    e.set_hand_detected(True)
    return e


def test_zoom_releases_ctrl_even_on_scroll_failure():
    e=active()
    with patch.object(e,'_target_canva_canvas'), patch('holocontrol.infrastructure.windows.windows_action_executor.pyautogui') as api:
        api.scroll.side_effect=OSError('wheel failed')
        with pytest.raises(OSError):
            e.zoom(2)
        api.keyDown.assert_called_once_with('ctrl',_pause=False)
        api.keyUp.assert_called_once_with('ctrl',_pause=False)
        api.scroll.assert_called_once_with(240,_pause=False)


@pytest.mark.parametrize('amount', [-2, 2])
def test_canva_scroll_targets_canvas_without_clicking(amount):
    e=active()
    with patch('holocontrol.infrastructure.windows.window_context.canva_canvas_point', return_value=(900,500)), patch('holocontrol.infrastructure.windows.window_context.scroll_canva_canvas') as wheel, patch('holocontrol.infrastructure.windows.windows_action_executor.pyautogui') as api:
        api.size.return_value=(1920,1080)
        e.scroll(amount)
        api.moveTo.assert_called_once_with(900,500,duration=0,_pause=False)
        wheel.assert_called_once_with((900,500), amount)
        api.scroll.assert_not_called()
        api.click.assert_not_called()
        api.press.assert_not_called()


@pytest.mark.parametrize('amount,delta', [(-2, 0xff88), (2, 120)])
def test_canva_wheel_message_reaches_native_child_with_correct_direction(amount, delta):
    from holocontrol.infrastructure.windows.window_context import scroll_canva_canvas
    with patch('ctypes.windll.user32') as api:
        api.WindowFromPoint.return_value = 42
        api.SendMessageTimeoutW.return_value = 1
        scroll_canva_canvas((900, 500), amount)
        assert api.SendMessageTimeoutW.call_count == 2
        args = api.SendMessageTimeoutW.call_args.args
        assert args[:6] == (42, 0x020A, delta << 16, 900 | (500 << 16), 2, 50)


def test_minimize_failure_is_reported():
    e = active()
    with patch('ctypes.windll.user32') as api:
        api.GetForegroundWindow.return_value = 42
        api.GetAncestor.return_value = 42
        api.ShowWindowAsync.return_value = 0
        with pytest.raises(RuntimeError, match='minimizar'):
            e.minimize_window()


def test_canva_timeout_is_reported_without_duplicate_wheel():
    from holocontrol.infrastructure.windows.window_context import scroll_canva_canvas
    with patch('ctypes.windll.user32') as api:
        api.WindowFromPoint.return_value = 42
        api.SendMessageTimeoutW.return_value = 0
        with pytest.raises(RuntimeError, match='Canva'):
            scroll_canva_canvas((900, 500), -2)
        assert api.SendMessageTimeoutW.call_count == 1


def test_voice_toggle_and_stop_preserve_text_focus():
    e=active()
    with patch('holocontrol.infrastructure.windows.windows_action_executor.pyautogui') as api:
        e.toggle_dictation()
        api.hotkey.assert_called_once_with('win','h',_pause=False)
        api.click.assert_not_called()
        e.toggle_dictation()
        api.hotkey.assert_called_with('win','alt','h',_pause=False)
        api.press.assert_called_once_with('esc',_pause=False)
        e.stop()
        assert api.press.call_count == 1


def test_drag_uses_continuous_button_and_intermediate_points():
    e=active()
    with patch('holocontrol.infrastructure.windows.windows_action_executor.pyautogui') as api:
        api.position.return_value=(200,200)
        api.size.return_value=(1920,1080)
        e.begin_drag(500,500)
        e.update_pinch(550,520)
        assert api.moveTo.call_count > 2
        api.mouseDown.assert_called_once_with(button='left',_pause=False)
        api.click.assert_not_called()
        e.end_pinch()
        api.mouseUp.assert_called_once_with(button='left',_pause=False)
        api.click.assert_not_called()


@pytest.mark.parametrize('key', ['enter', 'esc', 'volumeup', 'volumedown'])
def test_keyboard_execution(key):
    e = active()
    with patch('holocontrol.infrastructure.windows.windows_action_executor.pyautogui') as api:
        e.press_key(key)
        api.press.assert_called_once_with(key, _pause=False)
        e.pause()
        with pytest.raises(RuntimeError):
            e.press_key(key)
        assert api.press.call_count == 1
