"""Keep interactive camera control responsive when Windows occludes its window."""

import ctypes
import logging
from ctypes import wintypes


class PowerThrottlingState(ctypes.Structure):
    _fields_ = [("Version", wintypes.ULONG), ("ControlMask", wintypes.ULONG),
                ("StateMask", wintypes.ULONG)]


class BackgroundExecution:
    # PROCESS_INFORMATION_CLASS.ProcessPowerThrottling
    INFORMATION_CLASS = 4
    EXECUTION_SPEED = 1
    IGNORE_TIMER_RESOLUTION = 4

    def __init__(self):
        self._previous = None
        self._kernel = None
        self._process = None

    def acquire(self):
        if self._previous is not None:
            return
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        for name in ('GetProcessInformation', 'SetProcessInformation'):
            function = getattr(kernel, name)
            function.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
            function.restype = wintypes.BOOL
        process = kernel.GetCurrentProcess()
        previous = PowerThrottlingState(1, 0, 0)
        if not kernel.GetProcessInformation(process, self.INFORMATION_CLASS,
                                            ctypes.byref(previous), ctypes.sizeof(previous)):
            logging.getLogger(__name__).warning('Cannot read background execution policy: %s', ctypes.get_last_error())
            return
        current = PowerThrottlingState(1, previous.ControlMask | 5, previous.StateMask & ~5)
        if not kernel.SetProcessInformation(process, self.INFORMATION_CLASS,
                                            ctypes.byref(current), ctypes.sizeof(current)):
            logging.getLogger(__name__).warning('Cannot set background execution policy: %s', ctypes.get_last_error())
            return
        self._kernel, self._process, self._previous = kernel, process, previous

    def release(self):
        if self._previous is None:
            return
        previous = self._previous
        if self._kernel.SetProcessInformation(self._process, self.INFORMATION_CLASS,
                                              ctypes.byref(previous), ctypes.sizeof(previous)):
            self._previous = None
        else:
            logging.getLogger(__name__).warning('Cannot restore background execution policy: %s', ctypes.get_last_error())
