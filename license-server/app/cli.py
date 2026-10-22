"""Perintah bootstrap, kunci, dan pemeliharaan lokal."""
import argparse
import getpass
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import TypeAdapter, EmailStr
from sqlalchemy import select, delete

from .core.config import get_settings
from .core.security import password_hasher
from .db import session_factory, utcnow
from .models import Administrator, Product, Plan, License, AdminSession, RateBucket
from .services import audit, expire


def main():
    parser = argparse.ArgumentParser(description="Administrasi lokal lisensi ChessLab")
    parser.add_argument("command", choices=["keygen", "bootstrap", "maintenance"])
    parser.add_argument("--private", type=Path)
    parser.add_argument("--public", type=Path)
    parser.add_argument("--kid", default="ed25519-2026-01")
    parser.add_argument("--role", choices=["admin", "operator", "viewer"], default="admin")
    args = parser.parse_args()
    if args.command == "keygen":
        if not args.private or not args.public:
            parser.error("Isi --private dan --public; berkas lama tidak akan ditimpa.")
        key = Ed25519PrivateKey.generate()
        args.private.parent.mkdir(parents=True, exist_ok=True)
        args.public.parent.mkdir(parents=True, exist_ok=True)
        with args.private.open("xb") as file:
            file.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        args.private.chmod(0o600)
        raw = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        import base64
        with args.public.open("x", encoding="utf-8") as file:
            json.dump({args.kid: base64.urlsafe_b64encode(raw).decode()}, file, indent=2)
        print("Kunci dibuat. Lindungi kunci privat dan distribusikan hanya berkas publik.")
        return
    settings = get_settings()
    engine, sessions = session_factory(settings.database_url)
    try:
        with sessions.begin() as db:
            if args.command == "maintenance":
                for item in db.scalars(select(License).where(License.status == "ACTIVE", License.expires_at <= utcnow()).with_for_update()):
                    expire(db, item, utcnow())
                db.execute(delete(AdminSession).where(AdminSession.expires_at <= utcnow()))
                import time
                db.execute(delete(RateBucket).where(RateBucket.window < int(time.time()) - 1800))
                print("Pemeliharaan selesai.")
                return
            email = TypeAdapter(EmailStr).validate_python(os.environ.get("CHESSLAB_BOOTSTRAP_EMAIL") or input("Email admin: ")).lower()
            password = os.environ.pop("CHESSLAB_BOOTSTRAP_PASSWORD", None) or getpass.getpass("Kata sandi (minimal 14 karakter): ")
            if len(password) < 14 or len(password) > 256:
                parser.error("Kata sandi harus 14–256 karakter.")
            if db.scalar(select(Administrator).where(Administrator.email == email)):
                parser.error("Administrator sudah ada; bootstrap tidak mengganti kredensial.")
            admin = Administrator(email=email, password_hash=password_hasher.hash(password), role=args.role)
            db.add(admin); db.flush(); audit(db, "admin.bootstrap", admin, admin.id)
            if not db.scalar(select(Product).where(Product.code == "chesslab-pc")):
                product = Product(code="chesslab-pc", name="ChessLab PC")
                db.add(product); db.flush()
                db.add(Plan(product_id=product.id, name="ChessLab Pro", duration_seconds=432000, price_idr=50000, max_devices=1))
        print("Bootstrap selesai. Tidak ada kata sandi bawaan.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
