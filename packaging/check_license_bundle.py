"""Periksa allowlist konfigurasi dan ketiadaan rahasia pada arsip PyInstaller."""
import argparse
import json
from pathlib import Path
from PyInstaller.archive.readers import CArchiveReader


def main():
    parser=argparse.ArgumentParser(description="Periksa keamanan paket lisensi")
    parser.add_argument("exe",type=Path)
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
    for name in names:
        if name.lower().endswith(".pyz"):
            modules=archive.open_embedded_archive(name).toc
            assert "chesslab.licensing.verifier" in modules
            assert not any(m.startswith(("app.core.signing","app.models","sqlalchemy","psycopg","argon2")) for m in modules)
    print(json.dumps({"ok":True,"jumlah_entri":len(names),"id_kunci_publik":info["public_key_ids"],"versi":info["version"]},indent=2))


if __name__=="__main__":main()
