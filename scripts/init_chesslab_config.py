"""Inisialisasi config tanpa menimpa preferensi pengguna atau membuat kunci."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

from build_support import (ROOT, read_json, validate_config, validate_public,
                           validate_engine, validate_templates, stockfish_notices)


def initialize(config: Path, public_path: Path, engine: Path | None = None,
               templates: Path | None = None, example=ROOT / "config.example.json"):
    validate_public(public_path)
    if config.exists():
        _, settings = validate_config(config)
        validate_engine(settings.stockfish_path)
        stockfish_notices(settings.stockfish_path)
        validate_templates(settings.templates_dir)
        return False
    raw = read_json(example)
    if engine is not None:
        raw["stockfish_path"] = str(engine.resolve())
    if templates is not None:
        raw["templates_dir"] = str(templates.resolve())
    config.parent.mkdir(parents=True, exist_ok=True)
    # Kandidat divalidasi relatif ke lokasi config final, bukan cwd pemanggil.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", prefix=".config-",
                                     dir=config.parent, encoding="utf-8", delete=False) as stream:
        candidate = Path(stream.name)
        json.dump(raw, stream, indent=2)
        stream.write("\n")
    try:
        _, settings = validate_config(candidate)
        validate_engine(settings.stockfish_path)
        stockfish_notices(settings.stockfish_path)
        validate_templates(settings.templates_dir)
        # Hard link atomik: gagal jika config dibuat proses lain saat validasi.
        import os
        os.link(candidate, config)
    finally:
        candidate.unlink(missing_ok=True)
    return True


def main():
    parser = argparse.ArgumentParser(description="Buat/validasi config ChessLab tanpa overwrite.")
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument("--license-config", type=Path, default=ROOT / "licensing-public.json")
    parser.add_argument("--stockfish-path", type=Path)
    parser.add_argument("--templates-dir", type=Path)
    args = parser.parse_args()
    try:
        created = initialize(args.config.resolve(), args.license_config.resolve(), args.stockfish_path, args.templates_dir)
    except (ValueError, OSError) as exc:
        print(f"FAIL Inisialisasi: {exc}")
        return 1
    print("PASS config.json dibuat dan aset tervalidasi." if created else "PASS Konfigurasi lama dipertahankan; aset dan lisensi publik valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
