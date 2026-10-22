"""Jalankan dengan .venv\\Scripts\\python.exe scripts\\preflight_build.py."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from build_support import (ROOT, validate_python, validate_environment, validate_dependencies,
                           validate_config, validate_public, validate_templates, validate_engine,
                           stockfish_notices, validate_output, check_input_file)


def run_checks(config=ROOT / "config.json", public_path=ROOT / "licensing-public.json",
               output=ROOT / "outputs/licensed", *, check_environment=True):
    results = []
    values = {}

    def check(name, function):
        try:
            values[name] = function()
            results.append({"check": name, "status": "PASS", "message": "Terpenuhi."})
        except Exception as exc:
            # Validator menghasilkan pesan aman; exception dependency tak dikenal tidak dicetak.
            message = str(exc) if isinstance(exc, (ValueError, FileNotFoundError)) else f"{type(exc).__name__}; periksa dependency/path dan jalankan setup kembali."
            results.append({"check": name, "status": "FAIL", "message": message})

    if check_environment:
        check("Python Windows 3.13 x64", validate_python)
        check("Venv dan import checkout aktif", validate_environment)
        check("Dependency terkunci, PyInstaller, Tk dan pip check", validate_dependencies)
    check("Konfigurasi aplikasi", lambda: validate_config(Path(config)))
    check("Konfigurasi lisensi publik", lambda: validate_public(Path(public_path)))
    check("Input konfigurasi tanpa kunci privat", lambda: [check_input_file(Path(p)) for p in (config, public_path)])
    if "Konfigurasi aplikasi" in values:
        settings = values["Konfigurasi aplikasi"][1]
        check("Stockfish 19 dan langkah UCI legal", lambda: validate_engine(settings.stockfish_path))
        check("Lisensi dan sumber Stockfish", lambda: stockfish_notices(settings.stockfish_path))
        check("PNG asli pada 13 kelas template", lambda: validate_templates(settings.templates_dir))
    check("Tujuan output", lambda: validate_output(Path(output)))
    public = values.get("Konfigurasi lisensi publik")
    if public and public["api_url"].rstrip("/") != "http://localhost:8080":
        results.append({"check": "Endpoint UAT", "status": "WARNING", "message": "Endpoint valid tetapi berbeda dari http://localhost:8080. Pastikan server/key sesuai target."})
    return results


def main():
    parser = argparse.ArgumentParser(description="Preflight build Windows; FAIL menghentikan build.")
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument("--license-config", type=Path, default=ROOT / "licensing-public.json")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/licensed")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    results = run_checks(args.config.resolve(), args.license_config.resolve(), args.output)
    for item in results:
        print(f"{item['status']:7} {item['check']}: {item['message']}")
    failed = any(item["status"] == "FAIL" for item in results)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({"ok": not failed, "checks": results}, indent=2), encoding="utf-8")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
