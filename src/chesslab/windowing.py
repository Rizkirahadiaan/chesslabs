"""Window geometry checks; no mouse/keyboard injection."""
import ctypes
from ctypes import wintypes

u = ctypes.windll.user32
u.GetForegroundWindow.restype = wintypes.HWND
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u.IsIconic.argtypes = [wintypes.HWND]


def foreground():
    return u.GetForegroundWindow()


def rect(hwnd):
    r = wintypes.RECT()
    if not hwnd or not u.GetWindowRect(hwnd, ctypes.byref(r)):
        return None
    return r.left, r.top, r.right, r.bottom


def overlaps(a, b):
    return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])


def board_visible(target, coach, box, panel_rect):
    if not target or u.IsIconic(target):
        return False
    current = foreground()
    if current == target:
        return True
    if current == coach:
        return not overlaps(panel_rect, (box.left, box.top, box.right, box.bottom))
    return False
