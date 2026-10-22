"""Uji jendela Tk nyata; membutuhkan desktop Windows interaktif."""
import threading
import time
import tkinter as tk
from types import SimpleNamespace

import pytest

from chesslab.licensing.controller import LicenseStateController


def test_tk_heartbeat_remains_responsive_during_network_timeout():
    try: root=tk.Tk()
    except tk.TclError as exc:pytest.skip("Desktop Tk tidak tersedia: "+str(exc))
    root.withdraw()
    heartbeats=[];callbacks=[];owner=threading.get_ident()
    class Manager:
        entitled=False
        message="Menunggu validasi"
        def refresh(self,key=None):
            assert threading.get_ident()!=owner
            time.sleep(.35)
            self.message="Koneksi melewati batas waktu"
            return False
        def checkpoint(self):pass
    controller=LicenseStateController(root,Manager(),lambda *args:callbacks.append(threading.get_ident()))
    controller.refresh("uji")
    def beat():
        heartbeats.append(time.monotonic())
        root.after(15,beat)
    root.after(0,beat)
    root.after(650,root.quit)
    try:
        root.mainloop()
        assert len(heartbeats)>=12
        assert all(thread==owner for thread in callbacks)
        assert controller.future is None
    finally:
        controller.close();root.destroy()
