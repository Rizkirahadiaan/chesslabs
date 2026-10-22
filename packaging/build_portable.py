"""Build Windows: checkout aktif, input allowlist, preflight dan smoke test wajib."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from importlib import metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_support import (validate_config, validate_public, validate_templates,
                           stockfish_notices, sha256, check_input_file)
from preflight_build import run_checks


def collect_licenses(licenses: Path, engine: Path):
    licenses.mkdir()
    stockfish = stockfish_notices(engine)
    for name in ("Copying.txt", "AUTHORS", "README.md"):
        shutil.copy2(engine.parent / name, licenses / ("Stockfish-" + name))
    with zipfile.ZipFile(licenses / "Stockfish-source.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for source in stockfish:
            archive.write(source, source.relative_to(engine.parent))
    versions = {}
    for distribution in metadata.distributions():
        package = distribution.metadata["Name"]
        if package == "chesslab":
            continue
        versions[package] = distribution.version
        for entry in distribution.files or ():
            if ".dist-info" not in str(entry) or not any(word in str(entry).lower() for word in ("license", "copying", "notice", "authors")):
                continue
            source = Path(distribution.locate_file(entry))
            if source.is_file():
                check_input_file(source)
                target = licenses / package / Path(*entry.parts[1:])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    (licenses / "versions.json").write_text(json.dumps(versions, indent=2, sort_keys=True), encoding="utf-8")
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        raise ValueError("LICENSE.txt Python tidak tersedia pada interpreter build.")
    shutil.copy2(python_license, licenses / "Python-LICENSE.txt")
    return versions


def build_seed(seed: Path, config: Path, public_path: Path) -> dict:
    raw, settings = validate_config(config)
    public = validate_public(public_path)
    (seed / "engine").mkdir()
    shutil.copy2(settings.stockfish_path, seed / "engine/stockfish.exe")
    for source in validate_templates(settings.templates_dir):
        target = seed / "templates" / source.relative_to(settings.templates_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    raw.update(stockfish_path="engine/stockfish.exe", templates_dir="templates", runtime_dir="runtime")
    (seed / "config.json").write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    (seed / "licensing-public.json").write_text(json.dumps(public, indent=2) + "\n", encoding="utf-8")
    versions = collect_licenses(seed / "licenses", settings.stockfish_path)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip())
    source_files = sorted((ROOT / "src/chesslab").rglob("*.py")) + sorted((ROOT / "scripts").glob("*.py")) + sorted((ROOT / "scripts").glob("*.ps1")) + sorted((ROOT / "packaging").glob("*.py"))
    info = {"version": metadata.version("chesslab"), "built_at_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": commit, "git_dirty": dirty, "python": sys.version.split()[0],
            "public_key_ids": sorted(public["public_keys"]), "api_url": public["api_url"],
            "dependencies": versions, "lock_sha256": sha256(ROOT / "requirements-windows.lock"),
            "source_sha256": {p.relative_to(ROOT).as_posix(): sha256(p) for p in source_files},
            "payload_sha256": {p.relative_to(seed).as_posix(): sha256(p) for p in sorted(seed.rglob("*")) if p.is_file()}}
    (seed / "build-info.json").write_text(json.dumps(info, indent=2, sort_keys=True), encoding="utf-8")
    return info


def main():
    parser = argparse.ArgumentParser(description="Build EXE ChessLab berlisensi dari .venv proyek.")
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument("--license-config", type=Path, default=ROOT / "licensing-public.json")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/licensed")
    args = parser.parse_args()
    checks = run_checks(args.config.resolve(), args.license_config.resolve(), args.output)
    for item in checks:
        print(f"{item['status']:7} {item['check']}: {item['message']}", flush=True)
    if any(item["status"] == "FAIL" for item in checks):
        return 1
    work = ROOT / "work/portable-build"
    work.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="build-", dir=work))
    seed = run / "seed"
    seed.mkdir()
    staged = run / "dist"
    try:
        info = build_seed(seed, args.config.resolve(), args.license_config.resolve())
        environment = os.environ.copy()
        for name in ("PYTHONPATH", "PYTHONHOME", "CHESSLAB_LICENSE_CONFIG"):
            environment.pop(name, None)
        environment["PYTHONNOUSERSITE"] = "1"
        subprocess.run([sys.executable, "-E", "-s", "-m", "PyInstaller", "--noconfirm", "--clean",
                        "--onefile", "--windowed", "--noupx", "--name", "ChessLab-Coach",
                        "--paths", str(ROOT / "src"), "--distpath", str(staged),
                        "--workpath", str(run / "pyinstaller"), "--specpath", str(run),
                        "--add-data", f"{seed};portable", "--add-data", f"{seed / 'licensing-public.json'};.",
                        "--add-data", f"{seed / 'build-info.json'};.", str(ROOT / "packaging/portable_entry.py")],
                       cwd=ROOT, env=environment, check=True)
        executable = staged / "ChessLab-Coach.exe"
        subprocess.run([sys.executable, "-E", "-s", str(ROOT / "packaging/check_license_bundle.py"), str(executable),
                        "--expected-public", str(args.license_config.resolve())], cwd=ROOT, env=environment, check=True)
        subprocess.run([sys.executable, "-E", "-s", str(ROOT / "packaging/verify_portable.py"), "--exe", str(executable)],
                       cwd=ROOT, env=environment, check=True)
        output = args.output.resolve()
        output.mkdir(parents=True, exist_ok=True)
        shutil.copy2(executable, output / executable.name)
        shutil.copy2(ROOT / "packaging/BACA-DULU.txt", output / "BACA-DULU.txt")
        info.update(exe_sha256=sha256(executable), validation={"archive": "PASS", "portable_smoke": "PASS"})
        (output / "build-info.json").write_text(json.dumps(info, indent=2, sort_keys=True), encoding="utf-8")
        print(f"PASS Selesai: {output / executable.name}")
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        detail = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        print(f"FAIL Build: {detail}; lihat diagnosis di atas. Output final belum dipromosikan.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
