import hashlib
import secrets
import sys


class DeviceIdentity:
    def __init__(self, storage, product="chesslab-pc"):
        self.storage, self.product = storage, product

    def get_hash(self):
        identity = None
        if sys.platform == "win32":
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
                                    winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
                    identity = winreg.QueryValueEx(key, "MachineGuid")[0]
            except OSError:
                pass
        if not identity or not isinstance(identity, str):
            cache = self.storage.load()
            identity = cache.get("installation_id")
            if not identity:
                identity = secrets.token_hex(32)
                self.storage.save({"installation_id": identity})
        return hashlib.sha256(("chesslab-device-v1:" + self.product + ":" + identity.strip().lower()).encode()).hexdigest()
