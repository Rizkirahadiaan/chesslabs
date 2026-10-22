from concurrent.futures import ThreadPoolExecutor
import time


class LicenseStateController:
    """Dispatch melalui polling main thread; worker tidak memanggil root.after."""
    def __init__(self, root, manager, on_change):
        self.root, self.manager, self.on_change = root, manager, on_change
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="license-network")
        self.future = None
        self.closed = False
        self.next_validation = 0
        self.next_checkpoint = time.monotonic() + 60
        self.previous = None
        self.root.after(0, self.tick)

    def refresh(self, key=None):
        if self.closed or self.future is not None:
            return False
        self.future = self.pool.submit(self.manager.refresh, key)
        return True

    def tick(self):
        if self.closed:
            return
        now = time.monotonic()
        busy = self.future is not None
        if self.future is not None and self.future.done():
            try:
                success = self.future.result()
            except Exception:
                success = False
                self.manager.message = "Validasi belum selesai. Silakan coba kembali."
            self.future = None
            self.next_validation = now + (1800 if success else 60)
            busy = False
            self.previous = None
        entitled = self.manager.entitled
        state = (entitled, busy, self.manager.message)
        if state != self.previous:
            self.previous = state
            self.on_change(entitled, busy, self.manager.message)
        if now >= self.next_validation and self.future is None:
            self.refresh()
        if now >= self.next_checkpoint:
            try: self.manager.checkpoint()
            except Exception: self.manager.message = "Cache lisensi belum dapat disimpan."
            self.next_checkpoint = now + 60
        self.root.after(250, self.tick)

    def close(self):
        self.closed = True
        self.pool.shutdown(wait=False, cancel_futures=True)
        try: self.manager.checkpoint()
        except Exception: pass
