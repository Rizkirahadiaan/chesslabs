"""Provision aset rilis dari sumber resmi terpin; tidak membuat signing key."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import urllib.request
import zipfile

from build_support import ROOT, sha256, validate_public
from init_chesslab_config import initialize


def safe_members(archive: zipfile.ZipFile):
    members = archive.infolist()
    if len({item.filename.casefold().rstrip("/") for item in members}) != len(members):
        raise ValueError("Nama duplikat pada arsip aset tidak diizinkan.")
    if sum(item.file_size for item in members) > 1024**3:
        raise ValueError("Arsip aset melebihi batas ekstraksi 1 GiB.")
    for item in members:
        path = PurePosixPath(item.filename)
        if path.is_absolute() or ".." in path.parts or "\\" in item.filename or ":" in item.filename or stat.S_ISLNK(item.external_attr >> 16):
            raise ValueError("Path/symlink tidak aman pada arsip aset.")
    return members


def download_asset(url: str, checksum: str, cache: Path):
    if not url.startswith("https://github.com/official-stockfish/Stockfish/releases/download/"):
        raise ValueError("URL engine harus rilis resmi Stockfish melalui HTTPS.")
    if cache.exists():
        if sha256(cache) != checksum:
            raise ValueError("Checksum cache engine berbeda; hapus cache unduhan tersebut secara eksplisit lalu ulangi.")
        return cache
    cache.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache.with_suffix(".downloading")
    created = False
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "ChessLab-release"})
        with temporary.open("xb") as target:
            created = True
            with urllib.request.urlopen(request, timeout=120) as source:
                shutil.copyfileobj(source, target)
        if sha256(temporary) != checksum:
            raise ValueError("Checksum unduhan Stockfish tidak sesuai manifest resmi.")
        temporary.rename(cache)
    finally:
        if created:
            temporary.unlink(missing_ok=True)
    return cache


def extract_engine(archive_path: Path, destination: Path, executable: str):
    with zipfile.ZipFile(archive_path) as archive:
        members = safe_members(archive)
        engines = [item for item in members if PurePosixPath(item.filename).name == executable]
        if len(engines) != 1:
            raise ValueError("Arsip harus berisi tepat satu executable Stockfish yang diharapkan.")
        if destination.exists():
            # Idempotensi hanya menerima pohon yang tetap identik; tidak overwrite aset lokal.
            for item in members:
                target = destination.joinpath(*PurePosixPath(item.filename).parts)
                if not item.is_dir() and (not target.is_file() or target.is_symlink() or sha256(target) != hashlib.sha256(archive.read(item)).hexdigest()):
                    raise ValueError("Aset yang sudah ada berbeda dari arsip; folder tidak ditimpa.")
        else:
            destination.mkdir(parents=True)
            for item in members:
                target = destination.joinpath(*PurePosixPath(item.filename).parts)
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(item) as source, target.open("xb") as output:
                        shutil.copyfileobj(source, output)
        return destination.joinpath(*PurePosixPath(engines[0].filename).parts)


def provision_public(config: Path, value: str):
    if not value.strip():
        raise ValueError("Repository variable CHESSLAB_LICENSE_PUBLIC_JSON belum diisi; gunakan hanya konfigurasi PUBLIK, bukan .env/private key.")
    (ROOT / "work").mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", dir=ROOT / "work", encoding="utf-8", delete=False) as stream:
        candidate = Path(stream.name)
        stream.write(value)
    try:
        public = validate_public(candidate)
        if config.exists():
            if validate_public(config) != public:
                raise ValueError("Konfigurasi publik lokal berbeda; tidak ditimpa.")
        else:
            with config.open("x", encoding="utf-8") as stream:
                json.dump(public, stream, indent=2)
    finally:
        candidate.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Provision engine resmi dan konfigurasi publik untuk CI/rilis")
    parser.add_argument("--stockfish-only", action="store_true")
    parser.add_argument("--github-env", action="store_true")
    args = parser.parse_args()
    try:
        asset = json.loads((ROOT / "packaging/windows-assets.json").read_text(encoding="utf-8"))["stockfish"]
        cached = download_asset(asset["url"], asset["sha256"], ROOT / "work/downloads/stockfish-19-windows-x64.zip")
        engine = extract_engine(cached, ROOT / "engine/release-stockfish-19", asset["executable"])
        if not args.stockfish_only:
            provision_public(ROOT / "licensing-public.json", os.environ.get("CHESSLAB_LICENSE_PUBLIC_JSON", ""))
            initialize(ROOT / "config.json", ROOT / "licensing-public.json", engine, ROOT / "templates")
        if args.github_env:
            with Path(os.environ["GITHUB_ENV"]).open("a", encoding="utf-8") as stream:
                stream.write(f"CHESSLAB_TEST_ENGINE={engine}\n")
        print("PASS Stockfish resmi dengan checksum terpin tersedia; tidak ada signing key dibuat.")
        return 0
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as exc:
        detail = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        print("FAIL Provision aset rilis: " + detail)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
