"""Pemeriksaan read-only server UAT; output hanya identitas dan fingerprint publik."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess

from build_support import ROOT, validate_public


def verify_pair(public: dict, private_path: Path, key_id: str):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    if key_id not in public["public_keys"]:
        raise ValueError("ID signing key lokal tidak ada dalam konfigurasi publik; jangan melakukan rotasi otomatis.")
    try:
        private = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
        if not isinstance(private, Ed25519PrivateKey):
            raise ValueError()
        value = public["public_keys"][key_id]
        raw_public = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        # Challenge lokal tidak berformat grant dan tidak memberikan entitlement.
        challenge = b"ChessLab build key-pair verification; not a license grant."
        Ed25519PublicKey.from_public_bytes(raw_public).verify(private.sign(challenge), challenge)
    except Exception as exc:
        raise ValueError("Kunci privat lokal tidak terbaca/bukan pasangan kunci publik. Kunci tidak diubah.") from exc
    return hashlib.sha256(raw_public).hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Validasi read-only pasangan kunci dan server lokal")
    parser.add_argument("--license-config", type=Path, default=ROOT / "licensing-public.json")
    parser.add_argument("--private-key", type=Path, default=ROOT / "secrets/license-private.pem")
    parser.add_argument("--key-id", help="Wajib jika konfigurasi publik memiliki beberapa ID")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    results = []

    def record(name, operation):
        try:
            value = operation()
            results.append({"check": name, "status": "PASS", "public": value})
            print(f"PASS {name}")
            return value
        except Exception as exc:
            message = str(exc) if isinstance(exc, ValueError) else f"{type(exc).__name__}; periksa layanan/path lokal."
            results.append({"check": name, "status": "FAIL", "message": message})
            print(f"FAIL {name}: {message}")

    public = record("Konfigurasi publik", lambda: validate_public(args.license_config))
    if public:
        key_id = args.key_id or (next(iter(public["public_keys"])) if len(public["public_keys"]) == 1 else None)
        local_hash = record("Pasangan signing key lokal", lambda: verify_pair(public, args.private_key, key_id))

        def health():
            import httpx
            response = httpx.get(public["api_url"].rstrip("/") + "/healthz", timeout=5, trust_env=False, follow_redirects=False)
            if response.status_code != 200:
                raise ValueError("Endpoint /healthz tidak mengembalikan HTTP 200.")
            return {"api_url": public["api_url"], "http_status": response.status_code}

        record("Endpoint UAT aktif", health)

        def container():
            # Tidak mengambil environment Docker atau isi PEM keluar dari container.
            code = ("import json,hashlib; from app.core.config import get_settings; "
                    "from app.core.signing import GrantSigner; from cryptography.hazmat.primitives import serialization; "
                    "s=get_settings(); k=GrantSigner(s).key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw); "
                    "print(json.dumps(dict(key_id=s.signing_key_id,sha256=hashlib.sha256(k).hexdigest(),origin=s.public_origin)))")
            process = subprocess.run(["docker", "compose", "exec", "-T", "api", "python", "-c", code], cwd=ROOT,
                                     capture_output=True, text=True, timeout=30)
            if process.returncode:
                raise ValueError("Tidak dapat memeriksa key container. Pastikan Docker Compose api berjalan; stderr tidak dicetak untuk melindungi rahasia.")
            try:
                value = json.loads(process.stdout)
            except ValueError as exc:
                raise ValueError("Respons pemeriksaan container tidak valid.") from exc
            if value.get("key_id") != key_id or value.get("sha256") != local_hash or value.get("origin", "").rstrip("/") != public["api_url"].rstrip("/"):
                raise ValueError("ID/key/origin container berbeda dari konfigurasi lokal. Dilaporkan tanpa merotasi kunci.")
            return value

        record("Signing key dan origin container cocok", container)
    ok = bool(results) and all(item["status"] == "PASS" for item in results)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({"ok": ok, "checks": results}, indent=2), encoding="utf-8")
    return int(not ok)


if __name__ == "__main__":
    raise SystemExit(main())
