import base64
import json
import math
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


class GrantError(Exception):
    pass


def decode(value):
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)


class LicenseTokenVerifier:
    def __init__(self, keys, product, device):
        self.keys, self.product, self.device = keys, product, device

    def payload(self, token):
        try:
            if not isinstance(token, str) or len(token) > 16384:
                raise ValueError()
            header64, payload64, signature = token.split(".")
            header = json.loads(decode(header64))
            if header.get("alg") != "EdDSA" or header.get("typ") != "CLG":
                raise ValueError()
            key = Ed25519PublicKey.from_public_bytes(decode(self.keys[header["kid"]]))
            key.verify(decode(signature), (header64 + "." + payload64).encode("ascii"))
            payload = json.loads(decode(payload64))
            if (payload["v"] != 1 or payload["product"] != self.product or
                    payload["device"] != self.device or payload["status"] != "ACTIVE"):
                raise ValueError()
            for field in ("iat", "exp", "subscription_exp", "activated"):
                if type(payload[field]) is not int:
                    raise ValueError()
            if not (payload["activated"] <= payload["iat"] < payload["exp"] <= payload["subscription_exp"] and
                    payload["exp"] - payload["iat"] <= 43200):
                raise ValueError()
            from uuid import UUID
            UUID(payload["license"]); UUID(payload["activation"])
            return payload
        except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, InvalidSignature) as exc:
            raise GrantError("Grant lisensi tidak valid, telah diubah, atau tidak sesuai perangkat/produk.") from exc

    def verify(self, token, now=None):
        payload = self.payload(token)
        now = time.time() if now is None else now
        if not math.isfinite(now) or now + 120 < payload["iat"]:
            raise GrantError("Jam sistem mundur. Hubungkan internet untuk validasi ulang.")
        if now >= min(payload["exp"], payload["subscription_exp"]):
            raise GrantError("Masa berlaku grant atau langganan telah habis. Validasi atau perpanjang lisensi.")
        return payload
