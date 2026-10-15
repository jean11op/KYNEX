"""Apply the same background policy to an already-running HoloControl instance."""
import ctypes
import sys
from ctypes import wintypes
from holocontrol.infrastructure.windows.background_execution import PowerThrottlingState

kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel.OpenProcess.restype = wintypes.HANDLE
kernel.CloseHandle.argtypes = [wintypes.HANDLE]
for name in ('GetProcessInformation', 'SetProcessInformation'):
    function = getattr(kernel, name)
    function.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    function.restype = wintypes.BOOL
handle = kernel.OpenProcess(0x0200 | 0x1000, False, int(sys.argv[1]))
if not handle:
    raise ctypes.WinError(ctypes.get_last_error())
try:
    state = PowerThrottlingState(1, 0, 0)
    if not kernel.GetProcessInformation(handle, 4, ctypes.byref(state), ctypes.sizeof(state)):
        raise ctypes.WinError(ctypes.get_last_error())
    print('Previous policy:', state.ControlMask, state.StateMask)
    state.ControlMask |= 5
    state.StateMask &= ~5
    if not kernel.SetProcessInformation(handle, 4, ctypes.byref(state), ctypes.sizeof(state)):
        raise ctypes.WinError(ctypes.get_last_error())
    print('Interactive background execution enabled for PID', sys.argv[1])
finally:
    kernel.CloseHandle(handle)
