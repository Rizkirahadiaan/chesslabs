"""Click-through move recommendations: small dots or red square shadows."""
import ctypes
from ctypes import wintypes
import tkinter as tk

from .board import grid_cell


def marker_rect(square, box, diameter):
    """Place a marker inside the upper-right corner of its displayed square."""
    x, y = grid_cell(square, box)
    width, height = (box.right-box.left)/8, (box.bottom-box.top)/8
    extent = diameter + 2
    inset = max(2, min(6, round(min(width, height) * .08)))
    return round(x+width/2)-inset-extent, round(y-height/2)+inset, extent, extent


class ShadowOverlay:
    def __init__(self, root, diameter=5, opacity=.45, style="dots"):
        if style not in ("dots", "shadow"):
            raise ValueError("Unknown overlay style")
        self.style = style
        self.opacity = opacity
        self.windows = []
        self.handles = []
        self.canvases = []
        self.diameter = max(3, min(10, int(diameter)))
        self.last_position = None
        self.capture_excluded = True
        self.visible = False
        u = ctypes.windll.user32
        u.GetParent.argtypes = [wintypes.HWND]
        u.GetParent.restype = wintypes.HWND
        u.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        u.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
        u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        for index in range(2):
            window = tk.Toplevel(root)
            window.withdraw()
            window.overrideredirect(True)
            window.configure(bg="#ff00ff")
            window.attributes("-transparentcolor", "#ff00ff")
            window.attributes("-alpha", opacity)
            window.attributes("-topmost", True)
            canvas = tk.Canvas(window, bg="#ff00ff", highlightthickness=0,
                               borderwidth=0, width=self.diameter+2, height=self.diameter+2)
            canvas.pack(fill="both", expand=True)
            self.canvases.append(canvas)
            window.update_idletasks()
            hwnd = u.GetParent(window.winfo_id()) or window.winfo_id()
            style = u.GetWindowLongW(hwnd, -20)
            # Layered + transparent + no activate + tool window.
            u.SetWindowLongW(hwnd, -20, style | 0x80000 | 0x20 | 0x08000000 | 0x80)
            self.windows.append(window)
            self.handles.append(hwnd)
            try:
                u.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
                self.capture_excluded &= bool(u.SetWindowDisplayAffinity(hwnd, 0x11))
            except AttributeError:
                self.capture_excluded = False
        self._draw()

    def _draw(self):
        for index, (window, canvas) in enumerate(zip(self.windows, self.canvases)):
            canvas.delete("all")
            background = "#ff2020" if self.style == "shadow" else "#ff00ff"
            window.configure(bg=background)
            canvas.configure(bg=background, width=self.diameter+2, height=self.diameter+2)
            if self.style == "dots":
                canvas.create_oval(1, 1, self.diameter, self.diameter,
                                   outline="#626262", fill="#626262" if index else "", width=1)
        self.set_opacity(self.opacity)

    def set_style(self, style):
        if style not in ("dots", "shadow"):
            raise ValueError("Unknown overlay style")
        was_visible = self.visible
        self.hide()
        self.style = style
        self._draw()
        if was_visible and self.last_position:
            self.show(*self.last_position)

    def set_size(self, diameter):
        self.diameter = max(3, min(10, int(diameter)))
        self._draw()
        if self.visible and self.last_position:
            self.show(*self.last_position)

    def show(self, move, box):
        self.visible = True
        self.last_position = (move, box)
        u = ctypes.windll.user32
        for window, hwnd, square in zip(self.windows, self.handles, (move.from_square, move.to_square)):
            if self.style == "shadow":
                center_x, center_y = grid_cell(square, box)
                cell_width = (box.right-box.left)/8
                cell_height = (box.bottom-box.top)/8
                x, y = round(center_x-cell_width/2)+2, round(center_y-cell_height/2)+2
                width, height = round(cell_width)-4, round(cell_height)-4
            else:
                x, y, width, height = marker_rect(square, box, self.diameter)
            # SWP_NOACTIVATE | SWP_SHOWWINDOW, HWND_TOPMOST.
            u.SetWindowPos(hwnd, wintypes.HWND(-1), x, y, width, height, 0x10 | 0x40)

    def hide(self):
        self.visible = False
        for hwnd in self.handles:
            ctypes.windll.user32.ShowWindow(wintypes.HWND(hwnd), 0)

    def set_opacity(self, opacity):
        self.opacity = max(.15, min(.80, opacity))
        for index, window in enumerate(self.windows):
            factor = .6 if self.style == "shadow" and index == 0 else 1.0
            window.attributes("-alpha", self.opacity * factor)

    def close(self):
        self.hide()
        for window in self.windows:
            window.destroy()
