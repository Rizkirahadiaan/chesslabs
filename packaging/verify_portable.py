"""Integration check: launch just the EXE, then move it with its saved settings."""
import json
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def run_check(folder, report):
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment["PATH"] = str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32")
    result = subprocess.run([str(folder / "ChessLab-Coach.exe"), "--self-test", str(report)],
                            cwd=ROOT / "work", env=environment, timeout=90, check=False)
    data = json.loads(report.read_text(encoding="utf-8"))
    if result.returncode or not data.get("ok") or not data.get("frozen"):
        raise RuntimeError(json.dumps(data, indent=2))
    if data.get("overlay_styles") != ["shadow", "dots"]:
        raise RuntimeError("EXE belum memuat kedua tampilan rekomendasi terbaru")
    if set(data.get("human_style_moves", {})) != {"ON", "OFF"}:
        raise RuntimeError("EXE belum memuat mode gaya manusiawi ON/OFF")
    if not data.get("human_level_move"):
        raise RuntimeError("EXE belum memuat level Human")
    return data


def main():
    parser = argparse.ArgumentParser(description="Verifikasi paket Windows ChessLab")
    parser.add_argument("--exe", type=Path, default=ROOT / "outputs/licensed/ChessLab-Coach.exe")
    args = parser.parse_args()
    work = ROOT / "work" / "portable-verification"
    work.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="run-", dir=work))
    first = run / "USB awal"
    first.mkdir()
    shutil.copy2(args.exe, first / "ChessLab-Coach.exe")
    initial = run_check(first, run / "first.json")
    config = first / "ChessLab-data/config.json"
    raw = json.loads(config.read_text(encoding="utf-8"))
    raw["engine_strength"] = "Human"
    raw["overlay_style"] = "shadow"
    raw["human_style"] = False
    config.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    moved = run / "USB pindah caf\u00e9"
    first.rename(moved)
    relocated = run_check(moved, run / "relocated.json")
    assert json.loads((moved / "ChessLab-data/config.json").read_text())["engine_strength"] == "Human"
    assert json.loads((moved / "ChessLab-data/config.json").read_text())["overlay_style"] == "shadow"
    assert json.loads((moved / "ChessLab-data/config.json").read_text())["human_style"] is False
    log = (moved / "ChessLab-data/runtime/portable.log").read_text(encoding="utf-8")
    assert "Traceback" not in log, log
    result = {"ok": True, "python_on_path": False, "working_directory_differs": True,
              "moved_with_preferences": True, "non_ascii_path": True,
              "first": initial, "relocated": relocated}
    report = work / "result.json"
    report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
