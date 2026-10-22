"""Buat konfigurasi lokal dengan rahasia acak tanpa menimpa berkas yang ada."""
import argparse
import base64
import json
from pathlib import Path
import secrets

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def main():
    parser=argparse.ArgumentParser(description="Siapkan konfigurasi lisensi lokal")
    parser.add_argument("--env-file",type=Path,default=Path(".env"))
    parser.add_argument("--private",type=Path,default=Path("secrets/license-private.pem"))
    parser.add_argument("--public",type=Path,default=Path("licensing-public.json"))
    args=parser.parse_args()
    for path in (args.env_file,args.private,args.public):
        if path.exists():parser.error("Berkas sudah ada: "+str(path))
    key=Ed25519PrivateKey.generate()
    for path in (args.env_file,args.private,args.public):path.parent.mkdir(parents=True,exist_ok=True)
    with args.private.open("xb") as file:file.write(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    args.private.chmod(0o600)
    public=base64.urlsafe_b64encode(key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode()
    with args.public.open("x",encoding="utf-8") as file:json.dump({"api_url":"http://localhost:8080","product":"chesslab-pc","public_keys":{"ed25519-2026-01":public},"renewal_instructions":"Hubungi penjual dengan ID lisensi dan bukti pembayaran. Setelah konfirmasi manual, perbarui status lisensi."},file,indent=2)
    values={"CHESSLAB_DB_PASSWORD":secrets.token_hex(32),"CHESSLAB_RUNTIME_PASSWORD":secrets.token_hex(32),"CHESSLAB_KEY_PEPPER":secrets.token_hex(32),"CHESSLAB_SIGNING_KEY_FILE":args.private.as_posix(),"CHESSLAB_SIGNING_KEY_ID":"ed25519-2026-01","CHESSLAB_PUBLIC_ORIGIN":"http://localhost:8080","CHESSLAB_SECURE_COOKIES":"false","CHESSLAB_SITE_ADDRESS":"http://:8080"}
    with args.env_file.open("x",encoding="utf-8") as file:file.write("\n".join(k+"="+v for k,v in values.items())+"\n")
    args.env_file.chmod(0o600)
    print("Konfigurasi lokal dibuat. Tidak ada kredensial administrator bawaan. Aktifkan TLS sebelum produksi.")


if __name__=="__main__":main()
