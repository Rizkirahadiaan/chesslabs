import base64
import json
import sys
import threading
import time
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from chesslab.licensing.api import LicenseAPIClient, LicenseAPIError
from chesslab.licensing.controller import LicenseStateController
from chesslab.licensing.device import DeviceIdentity
from chesslab.licensing.manager import LicenseManager
from chesslab.licensing.storage import LicenseStorage, StorageError
from chesslab.licensing.verifier import LicenseTokenVerifier, GrantError


def encoded(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


@pytest.fixture
def grant():
    key = Ed25519PrivateKey.generate()
    public = encoded(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
    now = int(time.time())
    payload = dict(v=1, product="chesslab-pc", device="a"*64, license=str(uuid4()), activation=str(uuid4()),
                   status="ACTIVE", edition="ChessLab Pro", activated=now-60, iat=now, exp=now+43200, subscription_exp=now+432000)
    def sign(changes=None, signer=key, kid="test-01"):
        header = encoded(json.dumps(dict(alg="EdDSA",typ="CLG",kid=kid),sort_keys=True,separators=(",",":")).encode())
        body = encoded(json.dumps(dict(payload, **(changes or {})),sort_keys=True,separators=(",",":")).encode())
        message = header+"."+body
        return message+"."+encoded(signer.sign(message.encode()))
    return LicenseTokenVerifier({"test-01":public},"chesslab-pc","a"*64),sign,payload


class Memory:
    def __init__(self, value=None): self.value=value or {}
    def load(self): return dict(self.value)
    def save(self,value): self.value=dict(value)
    def clear(self): self.value={}


def test_signed_grant_valid_and_rotation(grant):
    verifier, sign, p = grant
    assert verifier.verify(sign(),p["iat"])["license"] == p["license"]
    with pytest.raises(GrantError): verifier.verify(sign(kid="unknown"))


@pytest.mark.parametrize("changes", [{"product":"other"},{"device":"b"*64},{"status":"REVOKED"},{"v":2},{"exp":0},{"iat":"123"}])
def test_wrong_claims(grant,changes):
    verifier,sign,_=grant
    with pytest.raises(GrantError):verifier.verify(sign(changes))


def test_tampered_payload_forgery_and_expired(grant):
    verifier,sign,p=grant
    token=sign();header,body,sig=token.split(".")
    changed=dict(p,subscription_exp=p["subscription_exp"]+86400)
    modified=header+"."+encoded(json.dumps(changed).encode())+"."+sig
    for invalid in [modified, sign(signer=Ed25519PrivateKey.generate()),"garbage", token+"x"]:
        with pytest.raises(GrantError):verifier.verify(invalid)
    with pytest.raises(GrantError):verifier.verify(token,p["exp"])
    with pytest.raises(GrantError):verifier.verify(token,p["iat"]-121)


def test_offline_startup_and_subscription_cap(grant):
    verifier,sign,p=grant
    network=SimpleNamespace(call=lambda *a,**kw:(_ for _ in ()).throw(LicenseAPIError("Tidak ada internet")))
    cache=Memory({"grant":sign(),"activation_secret":"x"*48,"server_time":p["iat"],"last_wall":p["iat"]})
    now=[p["iat"]+1800]
    manager=LicenseManager(network,verifier,cache,wall=lambda:now[0])
    assert manager.entitled
    assert not manager.refresh() and manager.entitled
    now[0]=p["exp"]
    assert not manager.entitled
    limited=sign({"exp":p["iat"]+60,"subscription_exp":p["iat"]+60})
    manager=LicenseManager(network,verifier,Memory({"grant":limited}),wall=lambda:p["iat"]+61)
    assert not manager.entitled


def test_activation_timeout_invalid_key_and_no_first_offline_access(grant):
    verifier,sign,p=grant
    def offline(*a,**kw):raise LicenseAPIError("Jaringan tidak tersedia")
    manager=LicenseManager(SimpleNamespace(call=offline),verifier,Memory())
    assert not manager.entitled and not manager.refresh("key") and not manager.entitled
    def invalid(*a,**kw):raise LicenseAPIError("Kunci tidak valid","INVALID_KEY")
    manager.api=SimpleNamespace(call=invalid)
    assert not manager.refresh("wrong-key") and "tidak valid" in manager.message


def test_valid_activation_cache_and_revocation(grant):
    verifier,sign,p=grant
    storage=Memory()
    mono=[100.0];wall=[p["iat"]]
    manager=LicenseManager(SimpleNamespace(call=lambda *a,**kw:{"grant":sign(),"activation_secret":"secret"}),verifier,storage,wall=lambda:wall[0],monotonic=lambda:mono[0])
    assert manager.refresh("key") and manager.entitled
    assert "license_key" not in storage.value
    manager.checkpoint()
    # Pencabutan di server ketika offline baru diketahui saat validasi atau grant habis.
    def offline(*a,**kw):raise LicenseAPIError("Timeout")
    manager.api=SimpleNamespace(call=offline)
    assert not manager.refresh() and manager.entitled
    def revoked(*a,**kw):raise LicenseAPIError("Dicabut","LICENSE_REVOKED",True)
    manager.api=SimpleNamespace(call=revoked)
    assert not manager.refresh() and not manager.entitled
    assert "grant" not in storage.value


def test_clock_rollback_requires_online_then_monotonic_expiry(grant):
    verifier,sign,p=grant
    wall=[p["iat"]-600];mono=[20.0]
    manager=LicenseManager(SimpleNamespace(call=lambda *a,**kw:{"grant":sign()}),verifier,
        Memory({"grant":sign(),"activation_secret":"secret","last_wall":p["iat"]}),wall=lambda:wall[0],monotonic=lambda:mono[0])
    assert not manager.entitled
    assert manager.refresh() and manager.entitled
    mono[0]+=43201
    assert not manager.entitled
    wall[0]-=600
    assert not manager.entitled


@pytest.mark.parametrize("cache", [{"grant":"invalid"},{"grant":None}])
def test_invalid_cached_grant(grant,cache):
    verifier,_,_=grant
    assert not LicenseManager(None,verifier,Memory(cache)).entitled


def test_device_mismatch_cache(grant):
    verifier,sign,_=grant
    verifier.device="b"*64
    assert not LicenseManager(None,verifier,Memory({"grant":sign()})).entitled


def test_device_fallback_is_stable_and_product_scoped(monkeypatch):
    monkeypatch.setattr(sys,"platform","test")
    cache=Memory()
    first=DeviceIdentity(cache).get_hash()
    assert first==DeviceIdentity(cache).get_hash() and len(first)==64
    assert first!=DeviceIdentity(cache,"other-product").get_hash()


@pytest.mark.skipif(sys.platform!="win32",reason="Windows DPAPI")
def test_windows_dpapi_roundtrip_and_corruption(tmp_path):
    storage=LicenseStorage(tmp_path/"license.bin")
    storage.save({"activation_secret":"sensitive-test","last_wall":123})
    assert b"sensitive-test" not in storage.path.read_bytes()
    assert storage.load()["activation_secret"]=="sensitive-test"
    storage.path.write_bytes(b"corrupted")
    with pytest.raises(StorageError):storage.load()


def test_http_timeout_and_redirect_not_followed():
    def timeout(request):raise httpx.ReadTimeout("timeout",request=request)
    api=LicenseAPIClient("http://localhost:8000","chesslab-pc","a"*64,httpx.MockTransport(timeout))
    with pytest.raises(LicenseAPIError):api.call("activate",license_key="test")
    with pytest.raises(ValueError):LicenseAPIClient("http://untrusted.example","chesslab-pc","a"*64)


def test_network_worker_never_dispatches_tk(grant):
    verifier,sign,p=grant
    owner=threading.get_ident();queue=[];callbacks=[];started=threading.Event();release=threading.Event();worker=[]
    class Root:
        def after(self,delay,callback):
            assert threading.get_ident()==owner
            queue.append(callback)
    def request(*a,**kw):
        worker.append(threading.get_ident());started.set();release.wait(2)
        return {"grant":sign(),"activation_secret":"secret"}
    manager=LicenseManager(SimpleNamespace(call=request),verifier,Memory())
    controller=LicenseStateController(Root(),manager,lambda *args:callbacks.append((threading.get_ident(),args)))
    assert controller.refresh("key") and started.wait(1)
    queue.pop(0)()  # polling main thread tetap dapat berjalan sewaktu request tertahan.
    assert callbacks and controller.future is not None and not controller.future.done()
    release.set();controller.future.result(timeout=2)
    queue.pop(0)()
    assert all(thread==owner for thread,_ in callbacks) and worker[0]!=owner and manager.entitled
    controller.close()


def test_expired_entitlement_blocks_coach_start_and_submission():
    from chesslab.coach import Coach
    coach=Coach.__new__(Coach)
    coach.license_manager=SimpleNamespace(entitled=False)
    coach.status=SimpleNamespace(set=lambda value:None)
    coach.overlay=SimpleNamespace(hide=lambda:None)
    coach.start();coach._request_advice(None);coach._show_advice()
    assert not coach._license_allowed()
