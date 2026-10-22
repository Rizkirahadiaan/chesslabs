"""Validasi bersama untuk bootstrap, preflight, dan input paket Windows."""
from __future__ import annotations

from dataclasses import fields
import hashlib
import importlib
from importlib import metadata
import json
from pathlib import Path
import re
import subprocess
import sys
import sysconfig
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FIELDS = {"api_url", "product", "public_keys", "renewal_instructions"}
PACKAGES = {"python-chess": "chess", "opencv-python": "cv2", "numpy": "numpy",
            "Pillow": "PIL", "cryptography": "cryptography", "httpx": "httpx",
            "PyInstaller": "PyInstaller", "pytest": "pytest"}
SECRET_SUFFIXES = {".pem", ".key", ".pfx", ".p12", ".jks", ".db", ".bin"}


def read_json(path: Path) -> dict:
    if not path.is_file():
        raise ValueError(f"Berkas belum tersedia: {path.name}. Jalankan init-chesslab-config.ps1 atau provision konfigurasi publik.")
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError(f"JSON tidak valid: {path.name}; periksa sintaks/encoding UTF-8.") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} harus berupa objek JSON.")
    return value


def validate_python(version=None, platform=None, bits=None, free_threaded=None, architecture=None):
    version = sys.version_info if version is None else version
    platform = sys.platform if platform is None else platform
    bits = (64 if sys.maxsize > 2**32 else 32) if bits is None else bits
    free_threaded = sysconfig.get_config_var("Py_GIL_DISABLED") if free_threaded is None else free_threaded
    architecture = sysconfig.get_platform() if architecture is None else architecture
    if tuple(version[:2]) != (3, 13) or platform != "win32" or bits != 64 or free_threaded or architecture != "win-amd64":
        raise ValueError("Build teruji memerlukan CPython 3.13 x64 standar pada Windows 10/11; gunakan setup-windows.ps1 -Python <python313.exe>.")


def validate_environment(root=ROOT):
    if sys.prefix == sys.base_prefix:
        raise ValueError("Virtual environment belum dipakai. Gunakan .venv\\Scripts\\python.exe.")
    if Path(sys.prefix).resolve() != (root / ".venv").resolve():
        raise ValueError("Interpreter harus berasal dari .venv repositori ini.")
    if sys.flags.ignore_environment != 1:
        # Wrappers memasang PYTHONNOUSERSITE dan menghapus PYTHONPATH/PYTHONHOME.
        import site
        if site.ENABLE_USER_SITE:
            raise ValueError("User site-packages harus nonaktif dalam environment build.")
    module = importlib.import_module("chesslab")
    validate_import_path(Path(module.__file__), root)


def validate_import_path(location: Path, root=ROOT):
    if location.resolve() != (root / "src/chesslab/__init__.py").resolve():
        raise ValueError("Import chesslab mengarah ke repositori lain. Jalankan ulang setup-windows.ps1 untuk memasang editable dari checkout ini.")


def validate_dependencies(root=ROOT):
    from packaging.requirements import Requirement
    for line in (root / "requirements-windows.lock").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        requirement = Requirement(line)
        if requirement.marker and not requirement.marker.evaluate():
            continue
        if metadata.version(requirement.name) not in requirement.specifier:
            raise ValueError(f"Versi {requirement.name} berbeda dari lock; jalankan ulang setup-windows.ps1.")
    for module in (*PACKAGES.values(), "tkinter", "_tkinter"):
        importlib.import_module(module)
    result = subprocess.run([sys.executable, "-m", "pip", "check"], capture_output=True, timeout=60)
    if result.returncode:
        raise ValueError("pip check gagal; jalankan ulang setup-windows.ps1 untuk menyelaraskan dependency.")


def validate_public(path: Path) -> dict:
    raw = read_json(path)
    if set(raw) - PUBLIC_FIELDS:
        raise ValueError("Konfigurasi publik memiliki kolom terlarang; jangan menyalin .env/konfigurasi server.")
    url_value = raw.get("api_url")
    if not isinstance(url_value, str):
        raise ValueError("api_url wajib berupa URL origin HTTP(S).")
    try:
        url = urlsplit(url_value)
        valid = (url.scheme == "https" or (url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1"}))
        valid = valid and url.hostname and url.port != 0 and url.path in ("", "/")
        valid = valid and not (url.username or url.password or url.query or url.fragment)
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("api_url harus origin HTTPS, atau HTTP localhost/127.0.0.1 untuk UAT; tanpa kredensial, path, query, atau fragment.")
    if raw.get("product") != "chesslab-pc":
        raise ValueError("product harus chesslab-pc untuk paket Windows ini.")
    keys = raw.get("public_keys")
    if not isinstance(keys, dict) or not keys:
        raise ValueError("public_keys belum diisi. Minta konfigurasi publik dari pengelola server; jangan membuat kunci baru.")
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    import base64
    try:
        for identifier, value in keys.items():
            if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", identifier):
                raise ValueError()
            if not isinstance(value, str):
                raise ValueError()
            decoded = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
            Ed25519PublicKey.from_public_bytes(decoded)
    except (ValueError, TypeError) as exc:
        raise ValueError("public_keys harus berisi ID dan kunci publik Ed25519 raw 32 byte dalam base64url.") from exc
    if not isinstance(raw.get("renewal_instructions", ""), str):
        raise ValueError("renewal_instructions harus berupa teks.")
    return raw


def validate_config(path: Path):
    from chesslab.config import Settings, BoardBox, load_settings
    raw = read_json(path)
    if set(raw) - {field.name for field in fields(Settings)}:
        raise ValueError("config.json berisi kolom asing/rahasia. Hanya field Settings yang diizinkan.")
    required = {"stockfish_path", "allowed_window_titles", "board"}
    if required - set(raw):
        raise ValueError("Konfigurasi kurang: " + ", ".join(sorted(required - set(raw))))
    if not isinstance(raw["board"], dict) or set(raw["board"]) - {field.name for field in fields(BoardBox)}:
        raise ValueError("board harus mengikuti field BoardBox pada config.example.json.")
    if not isinstance(raw["allowed_window_titles"], list) or not raw["allowed_window_titles"] or not all(isinstance(x, str) and x.strip() for x in raw["allowed_window_titles"]):
        raise ValueError("allowed_window_titles harus daftar judul jendela lokal/test yang tidak kosong.")
    for key in ("stockfish_path", "templates_dir", "runtime_dir"):
        if key in raw and (not isinstance(raw[key], str) or not raw[key].strip()):
            raise ValueError(f"{key} harus berupa path yang tidak kosong.")
    try:
        settings = load_settings(path)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Nilai konfigurasi tidak sesuai Settings/BoardBox; periksa config.example.json.") from exc
    return raw, settings


def forbidden_name(name: str) -> bool:
    parts = Path(name.replace("\\", "/")).parts
    return any(p.lower().startswith(".env") or p.lower() in {"secrets", "license-server", "admin-dashboard", ".git", ".venv", ".tools"} for p in parts) or Path(name).suffix.lower() in SECRET_SUFFIXES


def check_input_file(path: Path):
    if path.is_symlink() or forbidden_name(path.name):
        raise ValueError(f"Input paket terlarang/symlink: {path.name}")
    # Jangan pernah mencetak isi input yang dicurigai rahasia.
    with path.open("rb") as stream:
        tail = b""
        while chunk := stream.read(1024 * 1024):
            sample = tail + chunk
            if re.search(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----", sample):
                raise ValueError(f"Materi kunci privat ditemukan pada input: {path.name}")
            tail = sample[-128:]


def validate_templates(directory: Path) -> list[Path]:
    from chesslab.board import PIECE_NAME_TO_SYMBOL
    from PIL import Image
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError(f"Folder template belum tersedia/berupa symlink: {directory}")
    for path in directory.rglob("*"):
        if path.is_symlink() or forbidden_name(str(path.relative_to(directory))):
            raise ValueError("Folder template berisi rahasia/symlink; pindahkan berkas non-template sebelum build.")
    selected = []
    for group in (*PIECE_NAME_TO_SYMBOL, "empty"):
        images = sorted(p for p in (directory / group).glob("*") if p.suffix.lower() == ".png" and p.is_file())
        if not images:
            raise ValueError(f"Template PNG belum lengkap: {group}. Provision template asli atau jalankan collect-templates.")
        for image in images:
            check_input_file(image)
            try:
                with Image.open(image) as data:
                    if data.format != "PNG" or min(data.size) < 2:
                        raise ValueError()
                    data.verify()
            except (OSError, ValueError) as exc:
                raise ValueError(f"Template PNG rusak: {image.name}") from exc
        selected.extend(images)
    from chesslab.vision import TemplateRecognizer
    if len(TemplateRecognizer(directory, .74).templates) != 13:
        raise ValueError("TemplateRecognizer tidak dapat membaca seluruh 13 kelas template.")
    return selected


def validate_engine(engine: Path, execute=True):
    if not engine.is_file() or engine.suffix.lower() != ".exe":
        raise ValueError(f"Stockfish EXE belum tersedia: {engine}. Ekstrak distribusi resmi Stockfish 19 beserta lisensi dan src/.")
    check_input_file(engine)
    if execute:
        import chess
        import chess.engine
        try:
            with chess.engine.SimpleEngine.popen_uci(str(engine), timeout=10) as process:
                name = process.id.get("name", "")
                if not re.match(r"^Stockfish 19(?:\s|$)", name):
                    raise ValueError("Engine harus Stockfish 19; tidak mengganti engine secara otomatis.")
                process.ping()
                board = chess.Board()
                result = process.play(board, chess.engine.Limit(time=.1))
                if result.move not in board.legal_moves:
                    raise ValueError("Uji UCI tidak menghasilkan langkah legal.")
        except (OSError, TimeoutError, chess.engine.EngineError) as exc:
            raise ValueError("Stockfish gagal uji UCI. Gunakan binary resmi yang sesuai CPU, periksa NNUE dan blokir Windows.") from exc


def stockfish_notices(engine: Path) -> list[Path]:
    base = engine.parent
    for name in ("Copying.txt", "AUTHORS", "README.md"):
        if not (base / name).is_file():
            raise ValueError(f"Distribusi Stockfish kurang {name}; ekstrak arsip resmi lengkap.")
    if not (base / "src/Makefile").is_file() or not list((base / "src").glob("*.cpp")):
        raise ValueError("Sumber Stockfish src/ belum tersedia; provision sumber yang sesuai binary untuk redistribusi.")
    selected = [base / name for name in ("Copying.txt", "AUTHORS", "README.md")]
    for folder in ("src", "scripts"):
        for source in sorted((base / folder).rglob("*")):
            if source.is_symlink() or forbidden_name(str(source.relative_to(base))):
                raise ValueError("Sumber Stockfish mengandung input terlarang/symlink.")
            if source.is_file():
                selected.append(source)
    for source in selected:
        check_input_file(source)
    return selected


def validate_output(output: Path, root=ROOT):
    output = output.resolve()
    if not output.is_relative_to((root / "outputs").resolve()):
        raise ValueError("Output build wajib di dalam outputs/ repositori ini.")
    if output.exists() and not output.is_dir():
        raise ValueError("Path output bukan direktori.")
    for name in ("ChessLab-Coach.exe", "BACA-DULU.txt", "build-info.json"):
        target = output / name
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise ValueError("Tujuan output berisi symlink/direktori yang bertabrakan.")
    return output


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()
