"""Deliver wheel input to the pointed control without changing keyboard focus."""
import ctypes
from ctypes import wintypes


def canva_canvas_point():
    api = ctypes.windll.user32
    api.GetForegroundWindow.restype = wintypes.HWND
    api.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    api.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    api.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    window = api.GetForegroundWindow()
    title = ctypes.create_unicode_buffer(512)
    api.GetWindowTextW(window, title, len(title))
    if 'canva' not in title.value.casefold():
        return None
    rect = wintypes.RECT()
    if not api.GetClientRect(window, ctypes.byref(rect)):
        return None
    point = wintypes.POINT(round(rect.right*.65), round(rect.bottom*.55))
    if rect.right < 200 or rect.bottom < 200 or not api.ClientToScreen(window, ctypes.byref(point)):
        return None
    return point.x, point.y


def scroll_canva_canvas(point, amount):
    scroll_at_point(point, amount, 'Canva')


def scroll_at_point(point, amount, target='El control bajo el puntero'):
    """Deliver wheel input to the editor's native child window, not keyboard focus."""
    api = ctypes.windll.user32
    api.WindowFromPoint.argtypes = [wintypes.POINT]
    api.WindowFromPoint.restype = wintypes.HWND
    api.SendMessageTimeoutW.argtypes = [
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
        wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t),
    ]
    api.SendMessageTimeoutW.restype = ctypes.c_ssize_t
    x, y = point
    window = api.WindowFromPoint(wintypes.POINT(x, y))
    if not window:
        raise RuntimeError(f"{target}: no se pudo localizar la ventana.")
    # WM_MOUSEWHEEL: signed delta in high word; screen coordinates in lParam.
    # No modifiers: Ctrl/Shift would change zoom or scroll direction.
    position = (x & 0xffff) | ((y & 0xffff) << 16)
    result = ctypes.c_size_t()
    for _ in range(abs(amount)):
        delta = 120 if amount > 0 else -120
        if not api.SendMessageTimeoutW(window, 0x020A, (delta & 0xffff) << 16,
                                      position, 0x0002, 50, ctypes.byref(result)):
            raise RuntimeError(f"{target} no respondió al desplazamiento.")
