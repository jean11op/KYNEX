import ctypes
from unittest.mock import Mock

from holocontrol.infrastructure.windows.background_execution import BackgroundExecution, PowerThrottlingState


def test_background_policy_preserves_other_flags_and_restores(monkeypatch):
    kernel = Mock()
    written = []
    def read(process, info, pointer, size):
        state = ctypes.cast(pointer, ctypes.POINTER(PowerThrottlingState)).contents
        state.ControlMask, state.StateMask = 2, 2
        return True
    def write(process, info, pointer, size):
        state = ctypes.cast(pointer, ctypes.POINTER(PowerThrottlingState)).contents
        written.append((state.Version, state.ControlMask, state.StateMask))
        return True
    kernel.GetProcessInformation.side_effect = read
    kernel.SetProcessInformation.side_effect = write
    monkeypatch.setattr(ctypes, 'WinDLL', lambda *a, **kw: kernel)
    policy = BackgroundExecution()
    policy.acquire()
    policy.acquire()
    policy.release()
    policy.release()
    assert written == [(1, 7, 2), (1, 2, 2)]


def test_failed_policy_does_not_claim_to_be_acquired(monkeypatch):
    kernel = Mock()
    kernel.GetProcessInformation.return_value = False
    monkeypatch.setattr(ctypes, 'WinDLL', lambda *a, **kw: kernel)
    policy = BackgroundExecution()
    policy.acquire()
    assert policy._previous is None
    policy.release()
    kernel.SetProcessInformation.assert_not_called()


def test_executor_policy_lasts_through_window_switch_and_hand_loss(monkeypatch):
    from holocontrol.infrastructure.windows import windows_action_executor as module
    policy = Mock()
    monkeypatch.setattr(module, 'BackgroundExecution', lambda: policy)
    monkeypatch.setattr(module.pyautogui, 'keyDown', Mock())
    monkeypatch.setattr(module.pyautogui, 'keyUp', Mock())
    monkeypatch.setattr(module.pyautogui, 'press', Mock())
    executor = module.WindowsActionExecutor()
    executor.activate()
    executor.set_hand_detected(True)
    executor.begin_window_switch(.5)
    executor.end_window_switch()
    executor.set_hand_detected(False)
    policy.acquire.assert_called_once()
    policy.release.assert_not_called()
    executor.pause()
    policy.release.assert_called_once()
