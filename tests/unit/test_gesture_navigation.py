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
    app.seleccionar_perfil(profile.id)
    app.calibrar_perfil(Calibracion(profile.id, suavizado=.5))
    state = app.iniciar_control(camara_disponible=True, ancho_pantalla=1920, alto_pantalla=1080)
    def frame(gesture, phase=FaseGesto.INICIO, x=.5, y=.45, direction=None, confidence=.99):
        clock.ahora = round(clock() + .05, 3)
        event = EventoGesto(gesture, phase, round(clock() * 1000), 0, confidence)
        return app.procesar_reconocimiento(Reconocimiento(
            state.generacion, round(clock(), 3), True, x=x, y=y, eventos=(event,), direccion_scroll=direction))
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
        e.minimize_window()
        user32.ShowWindowAsync.assert_called_once_with(12345, 6)


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
