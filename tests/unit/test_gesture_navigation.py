from unittest.mock import Mock, patch

import pytest

from holocontrol.application.dto.reconocimiento import Reconocimiento
from holocontrol.application.services.adaptador_ejecutor_existente import AdaptadorEjecutorExistente
from holocontrol.application.use_cases import AplicacionControl
from holocontrol.domain.entities import Calibracion
from holocontrol.infrastructure.windows.windows_action_executor import WindowsActionExecutor
from holocontrol.ports.vision.models import EventoGesto, FaseGesto
from tests.soporte import RepositorioPerfilesMemoria, RelojSimulado


@pytest.fixture
def control():
    clock = RelojSimulado()
    executor = Mock()
    app = AplicacionControl(RepositorioPerfilesMemoria(), AdaptadorEjecutorExistente(executor), clock)
    profile = app.crear_perfil("Test")
    app.configurar_gesto(profile.id, "dos_dedos", "desplazar_vertical", reemplazar_existente=True)
    app.seleccionar_perfil(profile.id)
    app.calibrar_perfil(Calibracion(profile.id, suavizado=.5))
    state = app.iniciar_control(camara_disponible=True, ancho_pantalla=1920, alto_pantalla=1080)
    def frame(gesture, phase=FaseGesto.INICIO, x=.5, y=.45, direction=None, confidence=.99, separation=None, palm=None, arrow=None):
        clock.ahora = round(clock() + .05, 3)
        event = EventoGesto(gesture, phase, round(clock() * 1000), 0, confidence)
        return app.procesar_reconocimiento(Reconocimiento(
            state.generacion, round(clock(), 3), True, x=x, y=y, eventos=(event,), direccion_scroll=direction, direccion_flechas=arrow, separacion_dedos=separation, centro_palma=palm))
    return app, executor, frame, clock


def test_two_fingers_already_high_scroll_without_initial_motion(control):
    _, executor, frame, _ = control
    frame('dos_dedos', y=.2)
    assert executor.scroll.call_args.args[0] > 0
    executor.scroll.reset_mock()
    frame('dos_dedos', FaseGesto.MANTENIMIENTO, y=.45)
    executor.scroll.assert_not_called()
    frame('dos_dedos', FaseGesto.MANTENIMIENTO, y=.7)
    assert executor.scroll.call_args.args[0] < 0


def test_cursor_reaches_edges_inside_camera_even_with_smoothing(control):
    _, executor, frame, _ = control
    frame('indice')
    frame('indice', FaseGesto.MANTENIMIENTO, x=.8, y=.75)
    executor.move_cursor.assert_called_with(1919, 1079)
    frame('indice', FaseGesto.MANTENIMIENTO, x=.2, y=.15)
    executor.move_cursor.assert_called_with(0, 0)


def test_fist_minimizes_only_once_per_hold(control):
    _, executor, frame, _ = control
    frame('puno')
    frame('puno', FaseGesto.MANTENIMIENTO)
    executor.minimize_window.assert_called_once()


def test_recognized_fist_minimizes_even_immediately_after_click(control):
    _, executor, frame, _ = control
    frame('pulgar')
    frame('pulgar', FaseGesto.FIN)
    frame('puno', confidence=.65)
    frame('puno', FaseGesto.MANTENIMIENTO, confidence=.65)
    executor.left_click.assert_called_once()
    executor.minimize_window.assert_called_once()
    frame('puno', FaseGesto.FIN)
    frame('puno', confidence=.65)
    assert executor.minimize_window.call_count == 2


def test_switch_window_lifecycle(control):
    _, executor, frame, _ = control
    frame('tres_dedos', x=.4)
    frame('tres_dedos', FaseGesto.MANTENIMIENTO, x=.6)
    frame('tres_dedos', FaseGesto.FIN)
    executor.begin_window_switch.assert_called_once_with(.4)
    executor.update_window_switch.assert_called_once_with(.6)
    executor.end_window_switch.assert_called_once_with(cancel=False)


def test_alt_tab_selection_and_release():
    e = WindowsActionExecutor()
    e.activate()
    e.set_hand_detected(True)
    with patch('holocontrol.infrastructure.windows.windows_action_executor.pyautogui') as api:
        e.begin_window_switch(.5)
        e.update_window_switch(.52)
        e.update_window_switch(.6)
        e.update_window_switch(.5)
        e.end_window_switch()
        assert [c.args[0] for c in api.press.call_args_list] == ['tab', 'right', 'left']
        api.keyDown.assert_called_once_with('alt', _pause=False)
        api.keyUp.assert_called_once_with('alt', _pause=False)


@pytest.mark.parametrize('stop', ['pause', 'stop', 'lost'])
def test_alt_released_when_tracking_ends(stop):
    e = WindowsActionExecutor()
    e.activate()
    e.set_hand_detected(True)
    with patch('holocontrol.infrastructure.windows.windows_action_executor.pyautogui') as api:
        e.begin_window_switch(.5)
        if stop == 'lost':
            e.set_hand_detected(False)
        else:
            getattr(e, stop)()
        api.press.assert_called_with('esc', _pause=False)
        api.keyUp.assert_called_once_with('alt', _pause=False)


def test_minimize_targets_foreground_window():
    e = WindowsActionExecutor()
    e.activate()
    e.set_hand_detected(True)
    with patch('ctypes.windll.user32') as user32:
        user32.GetForegroundWindow.return_value = 12345
        user32.GetAncestor.return_value = 67890
        e.minimize_window()
        user32.GetAncestor.assert_called_once_with(12345, 3)
        user32.ShowWindowAsync.assert_called_once_with(67890, 6)


def test_alt_released_even_at_failsafe_corner():
    import pyautogui
    e = WindowsActionExecutor()
    e.activate()
    e.set_hand_detected(True)
    with (patch.object(pyautogui, 'keyDown'), patch.object(pyautogui, 'press'),
          patch.object(pyautogui, 'keyUp', side_effect=pyautogui.FailSafeException),
          patch.object(pyautogui.platformModule, '_keyUp') as release):
        e.begin_window_switch(.5)
        e.end_window_switch(cancel=True)
        release.assert_called_once_with('alt')


@pytest.mark.parametrize('direction', [-1, 1])
def test_scroll_follows_finger_direction_even_at_same_camera_position(control, direction):
    _, executor, frame, _ = control
    frame('dos_dedos', y=.45, direction=direction, confidence=.65)
    for _ in range(3):
        frame('dos_dedos', FaseGesto.MANTENIMIENTO, y=.45, direction=direction, confidence=.65)
    assert executor.scroll.called
    assert all(call.args[0] * direction > 0 for call in executor.scroll.call_args_list)


@pytest.mark.parametrize('amount', [-2, 2])
def test_native_windows_receives_full_wheel_notches(amount):
    import pyautogui
    e = WindowsActionExecutor()
    e.activate()
    e.set_hand_detected(True)
    with (patch.object(pyautogui, 'failSafeCheck'),
          patch.object(pyautogui.platformModule, '_sendMouseEvent') as send):
        e.scroll(amount)
    assert send.call_args.kwargs['dwData'] == amount * 120


def test_thumb_click_does_not_move_or_drag_cursor(control):
    _, executor, frame, _ = control
    frame('indice', x=.5, y=.45)
    executor.reset_mock()
    frame('pulgar', x=.52, y=.47)
    frame('pulgar', FaseGesto.FIN, x=.52, y=.47)
    executor.left_click.assert_called_once()
    executor.move_cursor.assert_not_called()
    executor.begin_pinch.assert_not_called()
    executor.update_pinch.assert_not_called()


def test_old_default_pinch_no_longer_clicks(control):
    _, executor, frame, _ = control
    frame('pellizco')
    frame('pellizco', FaseGesto.FIN)
    executor.left_click.assert_not_called()
    executor.begin_pinch.assert_not_called()


def test_zoom_expands_and_contracts_without_cursor_or_click(control):
    _, executor, frame, _ = control
    frame('dos_dedos', separation=.4)
    frame('dos_dedos', FaseGesto.FIN, separation=.7)
    executor.reset_mock()
    frame('zoom', separation=.7)
    assert executor.zoom.call_args.args[0] > 0
    frame('zoom', FaseGesto.MANTENIMIENTO, separation=.3)
    assert executor.zoom.call_args.args[0] < 0
    executor.move_cursor.assert_not_called()
    executor.left_click.assert_not_called()
    frame('zoom', FaseGesto.FIN)
    executor.reset_mock()
    frame('zoom', separation=.9)
    executor.zoom.assert_not_called()


def test_like_toggle_once_per_raise(control):
    _, executor, frame, clock = control
    frame('like')
    for _ in range(10):
        frame('like', FaseGesto.MANTENIMIENTO)
    executor.toggle_dictation.assert_called_once()
    frame('like', FaseGesto.FIN)
    frame('like')
    assert executor.toggle_dictation.call_count == 2


def test_drawing_follows_palm_not_wobbling_index(control):
    _, executor, frame, _ = control
    frame('pellizco', palm=(.5,.5))
    x,y=executor.begin_drag.call_args.args
    frame('pellizco',FaseGesto.MANTENIMIENTO,x=.7,y=.7,palm=(.5,.5))
    executor.update_pinch.assert_called_with(x,y)
    frame('pellizco',FaseGesto.FIN)
    executor.end_pinch.assert_called_once_with(cancel=False)
    executor.left_click.assert_not_called()


@pytest.mark.parametrize('gesture,key', [('menique','enter'), ('cuernos','esc'),
    ('deslizamiento_derecha','volumeup'), ('deslizamiento_izquierda','volumedown')])
def test_keyboard_actions_once_per_gesture(control, gesture, key):
    _, executor, frame, clock = control
    frame(gesture)
    for _ in range(12):
        frame(gesture, FaseGesto.MANTENIMIENTO)
    executor.press_key.assert_called_once_with(key)
    frame(gesture, FaseGesto.FIN)
    frame(gesture)
    assert executor.press_key.call_count == 2


@pytest.mark.parametrize('direction', ['up', 'down', 'left', 'right'])
def test_arrow_keys_repeat_and_stop_on_release(control, direction):
    app, executor, frame, clock = control
    app.detener_control()
    app.configurar_gesto(app.estado_actual().id_perfil_seleccionado, 'dos_dedos', 'flechas', reemplazar_existente=True)
    state = app.iniciar_control(camara_disponible=True, ancho_pantalla=1920, alto_pantalla=1080)
    # Config changes create a new generation; exercise the current session directly.
    def send(phase, time, arrow):
        clock.ahora = time
        event = EventoGesto('dos_dedos', phase, round(time*1000), 0, .99)
        return app.procesar_reconocimiento(Reconocimiento(state.generacion, time, True,
            eventos=(event,), direccion_flechas=arrow))
    start = clock() + .1
    send(FaseGesto.INICIO, start, direction)
    send(FaseGesto.MANTENIMIENTO, start+.1, direction)
    assert executor.press_key.call_count == 1
    send(FaseGesto.MANTENIMIENTO, start+.5, direction)
    assert executor.press_key.call_count == 2
    send(FaseGesto.FIN, start+.6, direction)
    executor.press_key.assert_called_with(direction)
    executor.scroll.assert_not_called()


def test_thumb_down_backspace_then_clear_once_and_rearm(control):
    _, executor, frame, _ = control
    frame('pulgar_abajo')
    executor.press_key.assert_called_once_with('backspace')
    for _ in range(50):
        frame('pulgar_abajo', FaseGesto.MANTENIMIENTO)
    assert [c.args[0] for c in executor.press_key.call_args_list] == ['backspace', 'borrar_todo']
    frame('pulgar_abajo', FaseGesto.FIN)
    frame('pulgar_abajo')
    assert [c.args[0] for c in executor.press_key.call_args_list] == ['backspace', 'borrar_todo', 'backspace']


def test_releasing_or_losing_hand_cancels_pending_clear(control):
    app, executor, frame, clock = control
    frame('pulgar_abajo')
    frame('pulgar_abajo', FaseGesto.FIN)
    clock.ahora += 3
    frame('pulgar_abajo', FaseGesto.MANTENIMIENTO)
    assert executor.press_key.call_count == 1
    frame('pulgar_abajo')
    clock.ahora += .05
    app.procesar_reconocimiento(Reconocimiento(app.estado_actual().generacion, clock(), False))
    clock.ahora += 3
    frame('pulgar_abajo', FaseGesto.MANTENIMIENTO)
    assert [c.args[0] for c in executor.press_key.call_args_list] == ['backspace', 'backspace']
