"""Small, dependency-free Windows desktop primitives used by local-test mode."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import time

from PIL import ImageGrab


if os.name != "nt":
    raise OSError("ChessLab desktop capture/control is supported on Windows only")

user32 = ctypes.windll.user32
try:
    user32.SetProcessDPIAware()  # Keep physical pixels aligned with screenshots.
except AttributeError:
    pass


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


def cursor_position() -> tuple[int, int]:
    point = POINT()
    if not user32.GetCursorPos(ctypes.byref(point)):
        raise ctypes.WinError()
    return point.x, point.y


def active_window_title() -> str:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def screenshot(left: int, top: int, right: int, bottom: int):
    return ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True)


def click(x: float, y: float) -> None:
    """Click with a fail-safe at the top-left physical pixel."""
    if cursor_position() == (0, 0):
        raise RuntimeError("Fail-safe: mouse is at top-left; refusing to click.")
    if not user32.SetCursorPos(round(x), round(y)):
        raise ctypes.WinError()
    time.sleep(0.12)
    user32.mouse_event(0x0002, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
    user32.mouse_event(0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP
