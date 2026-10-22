"""Periksa allowlist konfigurasi dan ketiadaan rahasia pada arsip PyInstaller."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile
from io import BytesIO
from PyInstaller.archive.readers import CArchiveReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_support import forbidden_name, validate_public


def audit_payload(archive, expected_public):
    """Tambahan audit manifest, isi ZIP, dan kecocokan nilai kunci target."""
    normalized = {name.replace("\\", "/"): name for name in archive.toc}
    for name, original in normalized.items():
        if forbidden_name(name) and name.lower() != "certifi/cacert.pem":
            raise ValueError("Berkas terlarang dalam paket: " + name)
        if name.startswith("portable/") or name in {"licensing-public.json", "build-info.json", "certifi/cacert.pem"}:
            content = archive.extract(original)
            if re.search(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----", content):
                raise ValueError("Materi kunci privat ditemukan dalam payload.")
            if name.endswith(".zip"):
                with zipfile.ZipFile(BytesIO(content)) as nested:
                    for item in nested.infolist():
                        if forbidden_name(item.filename) or re.search(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----", nested.read(item)):
                            raise ValueError("Sumber ZIP mengandung input rahasia/terlarang.")
    public = json.loads(archive.extract(normalized["licensing-public.json"]))
    if public != validate_public(expected_public):
        raise ValueError("Konfigurasi publik dalam EXE berbeda dari konfigurasi target.")
    info = json.loads(archive.extract(normalized["build-info.json"]))
    if sorted(public["public_keys"]) != info["public_key_ids"] or public["api_url"] != info["api_url"]:
        raise ValueError("Metadata lisensi berbeda dari isi bundle.")
    if archive.extract(normalized["portable/licensing-public.json"]) != archive.extract(normalized["licensing-public.json"]):
        raise ValueError("Dua salinan konfigurasi publik berbeda.")
    expected = info["payload_sha256"]
    actual = {name.removeprefix("portable/") for name in normalized if name.startswith("portable/") and name != "portable/build-info.json"}
    if actual != set(expected):
        raise ValueError("Daftar payload berbeda dari manifest allowlist.")
    for name, checksum in expected.items():
        if hashlib.sha256(archive.extract(normalized["portable/" + name])).hexdigest() != checksum:
            raise ValueError("Integritas payload gagal: " + name)
    config = json.loads(archive.extract(normalized["portable/config.json"]))
    if any(config[key] != value for key, value in {"stockfish_path": "engine/stockfish.exe", "templates_dir": "templates", "runtime_dir": "runtime"}.items()):
        raise ValueError("Konfigurasi bundle masih memuat path mesin pengembang.")


def main():
    parser=argparse.ArgumentParser(description="Periksa keamanan paket lisensi")
    parser.add_argument("exe",type=Path)
    parser.add_argument("--expected-public",type=Path,default=ROOT / "licensing-public.json")
    args=parser.parse_args()
    archive=CArchiveReader(str(args.exe))
    names=list(archive.toc)
    for name in names:
        normalized=name.replace("\\","/").lower()
        if any(part in normalized.split("/") for part in (".env","license-server","secrets","admin-dashboard")) or (normalized.endswith((".pem",".key")) and normalized != "certifi/cacert.pem"):
            raise RuntimeError("Berkas terlarang dalam paket: "+name)
    public=json.loads(archive.extract("licensing-public.json"))
    assert set(public)<= {"api_url","product","public_keys","renewal_instructions"}
    assert public["public_keys"]
    info=json.loads(archive.extract("build-info.json"))
    assert sorted(public["public_keys"])==info["public_key_ids"]
    audit_payload(archive, args.expected_public)
    for name in names:
        if name.lower().endswith(".pyz"):
            modules=archive.open_embedded_archive(name).toc
            assert "chesslab.licensing.verifier" in modules
            assert not any(m.startswith(("app.core.signing","app.models","sqlalchemy","psycopg","argon2")) for m in modules)
    print(json.dumps({"ok":True,"jumlah_entri":len(names),"id_kunci_publik":info["public_key_ids"],"versi":info["version"]},indent=2))


if __name__=="__main__":main()
