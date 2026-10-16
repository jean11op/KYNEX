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
def test_canva_scroll_does_not_reposition_cursor(amount):
    e=active()
    with patch('holocontrol.infrastructure.windows.window_context.canva_canvas_point', return_value=(900,500)), patch('holocontrol.infrastructure.windows.window_context.scroll_canva_canvas') as wheel, patch('holocontrol.infrastructure.windows.windows_action_executor.pyautogui') as api:
        api.size.return_value=(1920,1080)
        e.scroll(amount)
        api.moveTo.assert_not_called()
        wheel.assert_not_called()
        api.scroll.assert_called_once_with(amount * 120, _pause=False)
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


def test_scroll_reversal_targets_same_child_without_focus_or_pointer_change():
    from holocontrol.infrastructure.windows.window_context import scroll_at_point
    with patch('ctypes.windll.user32') as api:
        api.WindowFromPoint.return_value = 42
        api.SendMessageTimeoutW.return_value = 1
        scroll_at_point((-300, 500), 1)
        scroll_at_point((-300, 500), -1)
        calls = api.SendMessageTimeoutW.call_args_list
        assert [c.args[0] for c in calls] == [42, 42]
        assert [c.args[2] for c in calls] == [120 << 16, 0xff88 << 16]
        assert all(c.args[3] == (0xfed4 | (500 << 16)) for c in calls)
        api.SetFocus.assert_not_called()
        api.SetCursorPos.assert_not_called()


def test_scroll_error_does_not_fall_back_to_duplicate_input():
    e = active()
    with (patch('holocontrol.infrastructure.windows.window_context.canva_canvas_point', return_value=None),
          patch('holocontrol.infrastructure.windows.window_context.scroll_at_point', side_effect=RuntimeError('timeout')),
          patch('holocontrol.infrastructure.windows.windows_action_executor.pyautogui') as api):
        api.position.return_value = (800, 500)
        api.scroll.side_effect = RuntimeError('timeout')
        with pytest.raises(RuntimeError, match='timeout'):
            e.scroll(-1)
        api.scroll.assert_called_once_with(-120, _pause=False)
        api.click.assert_not_called()


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
        e._clock = Mock(return_value=0.0)
        e.begin_drag(500,500)
        e._clock.return_value = 1/30
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


@pytest.mark.parametrize('fps', [20, 30, 60])
def test_drawing_filters_tremor_but_tracks_deliberate_strokes(fps):
    e = active()
    e._clock = Mock(return_value=0.0)
    with patch('holocontrol.infrastructure.windows.windows_action_executor.pyautogui') as api:
        api.position.return_value = (500, 500)
        api.size.return_value = (1920, 1080)
        e.begin_drag(0, 0)
        for frame in range(1, fps + 1):
            e._clock.return_value = frame / fps
            e.update_pinch(2 if frame % 2 else -2, 0)
            assert abs(e._drag_position[0] - 500) < 1.5
        for frame in range(1, fps + 1):
            e._clock.return_value = 1 + frame / fps
            e.update_pinch(round(150 * frame / fps), 0)
        assert 640 < e._drag_position[0] <= 650
        api.mouseDown.assert_called_once()
        e.set_hand_detected(False)
        api.mouseUp.assert_called_once()
        api.click.assert_not_called()


@pytest.mark.parametrize('key', ['up', 'down', 'left', 'right', 'backspace'])
def test_navigation_and_delete_keys_are_single_presses(key):
    e = active()
    with patch('holocontrol.infrastructure.windows.windows_action_executor.pyautogui') as api:
        e.press_key(key)
        api.press.assert_called_once_with(key, _pause=False)
        api.hotkey.assert_not_called()


def test_clear_field_selects_all_then_deletes():
    e = active()
    with patch('holocontrol.infrastructure.windows.windows_action_executor.pyautogui') as api:
        e.press_key('borrar_todo')
        assert [c[0] for c in api.mock_calls] == ['hotkey', 'press']
        api.hotkey.assert_called_once_with('ctrl', 'a', _pause=False)
        api.press.assert_called_once_with('backspace', _pause=False)
