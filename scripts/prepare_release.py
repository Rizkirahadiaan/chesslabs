"""Bentuk arsip distribusi allowlist dari EXE yang telah diaudit dan diuji."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib
from urllib.parse import urlsplit
import zipfile

from build_support import ROOT, read_json, sha256


def validate_tag(tag: str, version: str):
    if not re.fullmatch(r"v\d+\.\d+\.\d+(?:-(?:rc|beta|alpha)\.\d+)?", tag) or tag.removeprefix("v").split("-")[0] != version:
        raise ValueError("Tag harus v<versi-pyproject> atau v<versi>-rc.N/-beta.N/-alpha.N.")
    return tag.removeprefix("v")


def validate_build(executable: Path, info: dict, root=ROOT):
    if info.get("validation") != {"archive": "PASS", "portable_smoke": "PASS"}:
        raise ValueError("EXE belum memiliki hasil audit dan smoke test PASS.")
    if not executable.is_file() or sha256(executable) != info.get("exe_sha256"):
        raise ValueError("Checksum EXE berbeda dari build-info.json.")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    if info.get("git_commit") != commit:
        raise ValueError("EXE dibangun dari commit berbeda. Build ulang setelah commit rilis dibuat.")
    if not info.get("source_sha256") or any(not (root / name).resolve().is_relative_to(root.resolve()) or sha256(root / name) != checksum for name, checksum in info["source_sha256"].items()):
        raise ValueError("Sumber berubah sesudah build; ulangi build sebelum menyiapkan rilis.")
    paths = ["src", "scripts", "packaging", "templates", "pyproject.toml", "requirements-build.txt", "requirements-windows.lock", "config.example.json"]
    changed = subprocess.run(["git", "diff", "--name-only", "HEAD", "--", *paths], cwd=root, capture_output=True, text=True, check=True).stdout
    untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "--", *paths], cwd=root, capture_output=True, text=True, check=True).stdout
    if changed.strip() or untracked.strip():
        raise ValueError("Input build masih memiliki perubahan yang belum di-commit.")


def create_archive(executable: Path, info: dict, notice: Path, tag: str, destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    name = f"ChessLab-Coach-{tag}-windows-x64"
    archive_path = destination / (name + ".zip")
    if archive_path.exists():
        raise ValueError("Arsip rilis sudah ada; gunakan direktori baru agar tidak menimpa rilis sebelumnya.")
    packaged_info = dict(info, executable="ChessLab-Coach.exe", release_tag=tag)
    with zipfile.ZipFile(archive_path, "x", zipfile.ZIP_DEFLATED) as archive:
        archive.write(executable, name + "/ChessLab-Coach.exe")
        archive.write(notice, name + "/BACA-DULU.txt")
        archive.writestr(name + "/build-info.json", json.dumps(packaged_info, indent=2, sort_keys=True))
    checksum = destination / "SHA256SUMS.txt"
    with checksum.open("x", encoding="utf-8") as stream:
        stream.write(f"{sha256(archive_path)}  {archive_path.name}\n")
    return archive_path


def main():
    parser = argparse.ArgumentParser(description="Siapkan ZIP Windows dan SHA256SUMS untuk GitHub Releases")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--exe", type=Path, default=ROOT / "outputs/licensed/ChessLab-Coach.exe")
    parser.add_argument("--build-info", type=Path, default=ROOT / "outputs/licensed/build-info.json")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/releases")
    args = parser.parse_args()
    try:
        version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
        validate_tag(args.tag, version)
        info = read_json(args.build_info)
        validate_build(args.exe, info)
        if "-" not in args.tag and urlsplit(info["api_url"]).hostname in {"localhost", "127.0.0.1"}:
            raise ValueError("Endpoint localhost hanya boleh diterbitkan sebagai prerelease UAT.")
        subprocess.run([sys.executable, "-E", "-s", str(ROOT / "packaging/check_license_bundle.py"), str(args.exe),
                        "--expected-public", str(ROOT / "licensing-public.json")], cwd=ROOT, check=True)
        archive = create_archive(args.exe, info, ROOT / "packaging/BACA-DULU.txt", args.tag, args.output)
        print(f"PASS Arsip rilis: {archive}")
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print("FAIL Persiapan rilis: " + (str(exc) if isinstance(exc, ValueError) else type(exc).__name__))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
