import base64
import json
from uuid import UUID

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core.signing import canonical


def decode(value):return base64.urlsafe_b64decode(value+"="*(-len(value)%4))


def test_real_server_grant_signature_canonicalization_and_expiry_cap(issued):
    _,client,ids,key=issued
    response=client.post("/api/v1/licenses/activate",json={"product_code":"chesslab-pc","device_hash":"a"*64,"license_key":ids["license_key"]})
    assert response.status_code==200
    header,body,signature=response.json()["grant"].split(".")
    payload=json.loads(decode(body))
    assert canonical(payload)==decode(body)
    assert payload["exp"]-payload["iat"]<=43200
    assert payload["exp"]<=payload["subscription_exp"]
    assert payload["subscription_exp"]-payload["activated"]==432000
    message=(header+"."+body).encode()
    key.public_key().verify(decode(signature),message)
    with pytest.raises(InvalidSignature):key.public_key().verify(decode(signature),message+b"x")
    with pytest.raises(InvalidSignature):Ed25519PrivateKey.generate().public_key().verify(decode(signature),message)
