import json
import os
from pathlib import Path
import sys
import threading
import time

from .api import LicenseAPIClient, LicenseAPIError
from .device import DeviceIdentity
from .storage import LicenseStorage, StorageError
from .verifier import LicenseTokenVerifier, GrantError


class LicenseManager:
    def __init__(self, api, verifier, storage, wall=time.time, monotonic=time.monotonic):
        self.api, self.verifier, self.storage = api, verifier, storage
        self.wall, self.monotonic = wall, monotonic
        self.lock = threading.RLock()
        self.anchor = None
        self.message = "Aktivasi online diperlukan untuk memakai ChessLab Pro."
        try:
            self.cache = storage.load()
        except StorageError as exc:
            self.cache = {}; self.message = str(exc)
        self.last_check = 0.0
        self._wall_high = max(self.wall(), self.cache.get("last_wall", 0))
        self._rollback = self.wall() + 120 < self._wall_high

    @property
    def payload(self):
        with self.lock:
            token = self.cache.get("grant")
            if not token or self._rollback:
                return None
            try:
                wall = self.wall()
                if wall + 120 < self._wall_high:
                    self._rollback = True
                    self.message = "Jam sistem mundur. Validasi online diperlukan."
                    return None
                self._wall_high = max(self._wall_high, wall)
                now = self.anchor[0] + self.monotonic() - self.anchor[1] if self.anchor else max(wall, self.cache.get("server_time", 0))
                payload = self.verifier.verify(token, now)
                return payload
            except GrantError as exc:
                self.message = str(exc)
                return None

    @property
    def entitled(self):
        return self.payload is not None

    def checkpoint(self):
        with self.lock:
            if self.cache:
                self.cache["last_wall"] = max(self._wall_high, self.wall())
                if self.anchor:
                    self.cache["server_time"] = self.anchor[0] + self.monotonic() - self.anchor[1]
                self.storage.save(self.cache)

    def refresh(self, key=None):
        # Seluruh metode ini dijalankan worker; tidak ada panggilan Tk.
        with self.lock:
            secret = self.cache.get("activation_secret")
        if not key and not secret:
            return False
        try:
            result = self.api.call("activate" if key else "validate", secret=secret, license_key=key)
            payload = self.verifier.payload(result["grant"])
            # iat ditandatangani; server_time JSON tidak dijadikan jangkar tepercaya.
            self.verifier.verify(result["grant"], payload["iat"])
            with self.lock:
                candidate = dict(grant=result["grant"], activation_secret=result.get("activation_secret", secret),
                                 server_time=payload["iat"], last_wall=self.wall())
                self.storage.save(candidate)
                self.cache = candidate
                self.anchor = (payload["iat"], self.monotonic())
                self._wall_high = self.wall(); self._rollback = False
                self.last_check = self.monotonic()
                self.message = "Lisensi aktif dan telah divalidasi."
            return True
        except LicenseAPIError as exc:
            with self.lock:
                if exc.authoritative:
                    self.cache.pop("grant", None)
                    self.anchor = None
                    self.storage.save(self.cache)
                self.message = str(exc)
            return False
        except (GrantError, StorageError, KeyError, TypeError) as exc:
            with self.lock:
                self.cache.pop("grant", None)
                self.message = "Validasi gagal: " + (str(exc) if not isinstance(exc, (KeyError, TypeError)) else "Respons server tidak valid.")
            return False

    def deactivate(self):
        with self.lock:
            secret = self.cache.get("activation_secret")
        if secret:
            self.api.call("deactivate", secret=secret)
        with self.lock:
            self.storage.clear(); self.cache = {}; self.anchor = None


def load_public_config():
    if getattr(sys, "frozen", False):
        path = Path(sys._MEIPASS) / "licensing-public.json"
    else:
        path = Path(os.environ.get("CHESSLAB_LICENSE_CONFIG", Path(__file__).resolve().parents[3] / "licensing-public.json"))
    raw = json.loads(path.read_text(encoding="utf-8"))
    if set(raw) - {"api_url", "product", "public_keys", "renewal_instructions"}:
        raise ValueError("Konfigurasi publik mengandung kolom yang tidak diizinkan.")
    return raw


def default_manager():
    config = load_public_config()
    product = config.get("product", "chesslab-pc")
    directory = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ChessLab" / "licensing"
    # Nama produk dari konfigurasi tepercaya tidak boleh menjadi path arbitrer.
    import re
    if not re.fullmatch(r"[a-z0-9-]{2,64}", product):
        raise ValueError("Kode produk tidak valid.")
    device = DeviceIdentity(LicenseStorage(directory / (product + "-device.bin")), product).get_hash()
    manager = LicenseManager(LicenseAPIClient(config["api_url"], product, device),
        LicenseTokenVerifier(config["public_keys"], product, device), LicenseStorage(directory / (product + ".bin")))
    manager.renewal_instructions = config.get("renewal_instructions", "Hubungi penjual dan sertakan ID lisensi. Pembayaran dikonfirmasi manual oleh administrator.")
    return manager
