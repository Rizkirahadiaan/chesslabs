"""Build on Windows using the current config and its active templates/engine."""
from __future__ import annotations

import argparse
from importlib import metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument("--license-config", type=Path, default=ROOT / "licensing-public.json")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "licensed")
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("Build EXE ini harus dijalankan di Windows.")
    config = args.config.resolve()
    raw = json.loads(config.read_text(encoding="utf-8"))
    from chesslab.licensing.api import LicenseAPIClient
    from chesslab.licensing.verifier import decode
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    public = json.loads(args.license_config.read_text(encoding="utf-8"))
    if set(public) - {"api_url", "product", "public_keys", "renewal_instructions"} or not public.get("public_keys"):
        parser.error("Konfigurasi publik wajib berisi kunci verifikasi dan tidak boleh berisi rahasia.")
    LicenseAPIClient(public["api_url"], public.get("product", "chesslab-pc"), "0"*64)
    for value in public["public_keys"].values(): Ed25519PublicKey.from_public_bytes(decode(value))
    from chesslab.config import Settings
    from dataclasses import fields
    allowed = {field.name for field in fields(Settings)}
    raw = {key: value for key, value in raw.items() if key in allowed}
    engine = (config.parent / raw["stockfish_path"]).resolve()
    templates = (config.parent / raw.get("templates_dir", "templates")).resolve()
    if not engine.is_file():
        parser.error(f"Stockfish tidak ditemukan: {engine}")
    if not list(templates.glob("*/*.png")):
        parser.error(f"Template aktif tidak ditemukan: {templates}")
    work = ROOT / "work" / "portable-build"
    work.mkdir(parents=True, exist_ok=True)
    seed = Path(tempfile.mkdtemp(prefix="seed-", dir=work))
    (seed / "engine").mkdir()
    shutil.copy2(engine, seed / "engine" / "stockfish.exe")
    shutil.copytree(templates, seed / "templates", ignore=shutil.ignore_patterns("coach-*", "__pycache__"))
    raw.update(stockfish_path="engine/stockfish.exe", templates_dir="templates", runtime_dir="runtime")
    (seed / "config.json").write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")

    licenses = seed / "licenses"
    licenses.mkdir()
    # Preserve notices and the matching Stockfish sources supplied with the engine.
    for name in ("Copying.txt", "AUTHORS", "README.md"):
        source = engine.parent / name
        if source.exists():
            shutil.copy2(source, licenses / ("Stockfish-" + name))
    if (engine.parent / "src").is_dir():
        with zipfile.ZipFile(licenses / "Stockfish-source.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for source in (engine.parent / "src").rglob("*"):
                if source.is_file():
                    archive.write(source, source.relative_to(engine.parent))
    for package in ("chess", "python-chess", "numpy", "opencv-python", "Pillow", "PyInstaller"):
        distribution = metadata.distribution(package)
        for entry in distribution.files or ():
            if ".dist-info" in str(entry) and any(word in str(entry).lower()
                                                   for word in ("license", "copying", "notice")):
                source = Path(distribution.locate_file(entry))
                if source.is_file():
                    target = licenses / package / Path(*entry.parts[1:])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
    (licenses / "versions.json").write_text(json.dumps({package: metadata.version(package) for package in
        ("chess", "python-chess", "numpy", "opencv-python", "Pillow", "PyInstaller")}, indent=2), encoding="utf-8")
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.exists():
        shutil.copy2(python_license, licenses / "Python-LICENSE.txt")

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    public_bundle = seed / "licensing-public.json"
    public_bundle.write_text(json.dumps(public, indent=2), encoding="utf-8")
    build_info = {"version": metadata.version("chesslab"), "public_key_ids": sorted(public["public_keys"]),
                  "api_url": public["api_url"], "python": sys.version,
                  "dependencies": {name: metadata.version(name) for name in ("cryptography", "httpx", "PyInstaller")}}
    (seed / "build-info.json").write_text(json.dumps(build_info, indent=2), encoding="utf-8")
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                    "--onefile", "--windowed", "--noupx", "--name", "ChessLab-Coach",
                    "--paths", str(ROOT / "src"), "--distpath", str(output),
                    "--workpath", str(work / "pyinstaller"), "--specpath", str(work),
                    "--add-data", f"{seed};portable", "--add-data", f"{public_bundle};.",
                    "--add-data", f"{seed / 'build-info.json'};.", str(ROOT / "packaging" / "portable_entry.py")],
                   cwd=ROOT, check=True)
    shutil.copy2(ROOT / "packaging" / "BACA-DULU.txt", output / "BACA-DULU.txt")
    (output / "build-info.json").write_text(json.dumps(build_info, indent=2), encoding="utf-8")
    print(f"\nSelesai: {output / 'ChessLab-Coach.exe'}")


if __name__ == "__main__":
    main()
