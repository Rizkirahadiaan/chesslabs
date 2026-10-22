"""Windows registered shortcuts on an owned message thread; no keyboard hook."""
import ctypes
from ctypes import wintypes
from queue import Queue, Empty
from threading import Thread, Event


SHORTCUTS = {1: ("pause", "Ctrl+Alt+P", ord("P")),
             2: ("shadow", "Ctrl+Alt+H", ord("H")),
             3: ("rescan", "Ctrl+Alt+R", ord("R"))}


class GlobalHotkeys:
    def __init__(self):
        self.events = Queue()
        self.stop = Event()
        self.ready = Event()
        self.registered = []
        self.thread_id = None
        self.thread = Thread(target=self._run, daemon=True, name="chesslab-hotkeys")
        self.thread.start()

    def _run(self):
        u = ctypes.windll.user32
        self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        u.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        u.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
        try:
            for ident, (action, label, key) in SHORTCUTS.items():
                if u.RegisterHotKey(None, ident, 0x4000 | 0x2 | 0x1, key):
                    self.registered.append(ident)
                else:
                    self.events.put(("error", f"{label} dipakai aplikasi lain; tombol panel tetap tersedia."))
            self.ready.set()
            msg = wintypes.MSG()
            while not self.stop.is_set():
                while u.PeekMessageW(ctypes.byref(msg), None, 0x0312, 0x0312, 1):
                    ident = int(msg.wParam)
                    if ident in self.registered:
                        self.events.put((SHORTCUTS[ident][0], ""))
                self.stop.wait(.02)
        finally:
            for ident in self.registered:
                u.UnregisterHotKey(None, ident)
            self.ready.set()

    def poll(self):
        messages = []
        while True:
            try:
                messages.append(self.events.get_nowait())
            except Empty:
                return messages

    def close(self):
        self.stop.set()
        self.thread.join(timeout=1)
