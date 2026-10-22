import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys
import tempfile


class StorageError(Exception):
    pass


class Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def dpapi(value, decrypt=False):
    if sys.platform != "win32":
        raise StorageError("Penyimpanan lisensi membutuhkan Windows DPAPI.")
    source_buffer = ctypes.create_string_buffer(value)
    source = Blob(len(value), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise StorageError("Cache lisensi tidak dapat dilindungi atau dibaca oleh akun Windows ini.")
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        kernel.LocalFree(target.pbData)


class LicenseStorage:
    def __init__(self, path: Path, protect=dpapi, unprotect=None):
        self.path = Path(path)
        self.protect = protect
        self.unprotect = unprotect or (lambda value: dpapi(value, decrypt=True))

    def load(self):
        if not self.path.exists():
            return {}
        try:
            if self.path.stat().st_size > 65536:
                raise ValueError()
            result = json.loads(self.unprotect(self.path.read_bytes()))
            if not isinstance(result, dict):
                raise ValueError()
            return result
        except (OSError, ValueError, StorageError) as exc:
            raise StorageError("Cache lisensi rusak atau milik akun/perangkat lain.") from exc

    def save(self, value):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        encrypted = self.protect(json.dumps(value, sort_keys=True).encode())
        fd, temporary = tempfile.mkstemp(prefix="license-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "wb") as file:
                file.write(encrypted); file.flush(); os.fsync(file.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)

    def clear(self):
        self.path.unlink(missing_ok=True)
