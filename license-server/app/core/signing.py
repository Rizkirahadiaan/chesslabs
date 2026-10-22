import base64
import json
from datetime import timedelta

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


class GrantSigner:
    def __init__(self, settings):
        self.settings = settings
        self.key = serialization.load_pem_private_key(settings.signing_key_path.read_bytes(), password=None)
        if not isinstance(self.key, Ed25519PrivateKey):
            raise ValueError("Kunci harus Ed25519")

    def issue(self, license, activation, product, now):
        end = min(now + timedelta(seconds=self.settings.grant_seconds), license.expires_at)
        payload = dict(v=1, product=product.code, license=str(license.id),
                       activation=str(activation.id), device=activation.device_hash, status="ACTIVE",
                       edition=license.plan.name, activated=int(license.activated_at.timestamp()),
                       subscription_exp=int(license.expires_at.timestamp()),
                       iat=int(now.timestamp()), exp=int(end.timestamp()))
        header = dict(alg="EdDSA", typ="CLG", kid=self.settings.signing_key_id)
        message = b64(canonical(header)) + "." + b64(canonical(payload))
        return {"grant": message + "." + b64(self.key.sign(message.encode("ascii"))),
                "server_time": now, "status": "ACTIVE"}
