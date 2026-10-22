"""Regresi bootstrap/build; fixture tidak menyentuh konfigurasi atau kunci pengguna."""
import base64
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_support as support
import init_chesslab_config as bootstrap
from preflight_build import run_checks
from verify_local_license import verify_pair


@pytest.fixture
def public(tmp_path):
    # Kunci sekali pakai untuk test saja; tidak pernah memakai/mengubah secrets/ lokal.
    key = Ed25519PrivateKey.generate()
    value = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    raw = {"api_url": "http://localhost:8080", "product": "chesslab-pc",
           "public_keys": {"qa-test": base64.urlsafe_b64encode(value).decode()}}
    path = tmp_path / "licensing-public.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path, raw, key


@pytest.fixture
def config(tmp_path):
    raw = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
    raw["templates_dir"] = str(ROOT / "templates")
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path, raw


def test_missing_config_and_preflight_non_success(tmp_path, public):
    with pytest.raises(ValueError, match="belum tersedia"):
        support.validate_config(tmp_path / "config.json")
    results = run_checks(tmp_path / "config.json", public[0], ROOT / "outputs/qa-test", check_environment=False)
    assert any(r["status"] == "FAIL" and r["check"] == "Konfigurasi aplikasi" for r in results)


def test_missing_engine_is_actionable(tmp_path):
    with pytest.raises(ValueError, match="Stockfish EXE belum tersedia"):
        support.validate_engine(tmp_path / "missing.exe")


def test_templates_require_all_thirteen_real_classes(tmp_path):
    with pytest.raises(ValueError, match="Folder template belum"):
        support.validate_templates(tmp_path / "missing")
    shutil.copytree(ROOT / "templates", tmp_path / "templates")
    assert len(support.validate_templates(tmp_path / "templates")) == 64
    for image in (tmp_path / "templates/white_king").glob("*.png"):
        image.unlink()
    with pytest.raises(ValueError, match="white_king"):
        support.validate_templates(tmp_path / "templates")


def test_corrupt_png_rejected(tmp_path):
    shutil.copytree(ROOT / "templates", tmp_path / "templates")
    image = next((tmp_path / "templates/white_king").glob("*.png"))
    image.write_bytes(b"bukan PNG")
    with pytest.raises(ValueError, match="PNG rusak"):
        support.validate_templates(tmp_path / "templates")


@pytest.mark.parametrize("value", ["invalid!", "eA==", None, "-----BEGIN PRIVATE KEY-----"])
def test_invalid_public_key_rejected(public, value):
    path, raw, _ = public
    raw["public_keys"]["qa-test"] = value
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="Ed25519"):
        support.validate_public(path)


@pytest.mark.parametrize("url", ["https://", "http://remote.example", "file:///secret", "https://user:password@example.com",
                                  "https://example.com/api", "https://example.com?token=secret", "https://example.com#secret", "http://localhost:bad"])
def test_incorrect_api_urls_rejected_without_echoing_secrets(public, url):
    path, raw, _ = public
    raw["api_url"] = url
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError) as error:
        support.validate_public(path)
    assert url not in str(error.value)


def test_current_repo_import_required(tmp_path):
    support.validate_import_path(ROOT / "src/chesslab/__init__.py")
    with pytest.raises(ValueError, match="repositori lain"):
        support.validate_import_path(tmp_path / "old-repo/src/chesslab/__init__.py")


@pytest.mark.parametrize("version,platform,bits,free", [((3, 14), "win32", 64, False), ((3, 11), "win32", 64, False),
                                                       ((3, 13), "linux", 64, False), ((3, 13), "win32", 32, False),
                                                       ((3, 13), "win32", 64, True)])
def test_unsupported_build_interpreters_rejected(version, platform, bits, free):
    with pytest.raises(ValueError, match="CPython 3.13"):
        support.validate_python(version, platform, bits, free)


def test_supported_build_interpreter():
    support.validate_python((3, 13, 17), "win32", 64, False)


def test_native_arm64_requires_separate_certification():
    with pytest.raises(ValueError, match="CPython 3.13"):
        support.validate_python((3, 13), "win32", 64, False, "win-arm64")


def test_windows_relocation_waits_for_transient_directory_lock(tmp_path):
    if sys.platform != "win32":
        pytest.skip("Penguncian handle khusus Windows")
    import ctypes
    from ctypes import wintypes
    import threading
    import time
    spec = importlib.util.spec_from_file_location("portable_relocation_test", ROOT / "packaging/verify_portable.py")
    verify = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verify)
    source = tmp_path / "USB awal"
    source.mkdir()
    destination = tmp_path / "USB pindah caf\u00e9"
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW(str(source), 0, 3, None, 3, 0x02000000, None)
    assert handle != wintypes.HANDLE(-1).value
    def release():
        time.sleep(.25)
        kernel.CloseHandle(handle)
    worker = threading.Thread(target=release)
    worker.start()
    try:
        verify.relocate(source, destination, timeout=2)
        assert destination.is_dir() and not source.exists()
    finally:
        worker.join()


@pytest.mark.parametrize("name", [".env", ".env.backup", "license-private.pem", "database.db", "private.key"])
def test_forbidden_asset_filenames(tmp_path, name):
    target = tmp_path / name
    target.write_bytes(b"fixture")
    with pytest.raises(ValueError, match="terlarang"):
        support.check_input_file(target)


def test_private_key_content_cannot_hide_as_notice(tmp_path):
    target = tmp_path / "README.md"
    target.write_bytes(b"-----BEGIN PRIVATE KEY-----\nQA-FIXTURE\n")
    with pytest.raises(ValueError, match="kunci privat"):
        support.check_input_file(target)


def test_secret_inside_template_tree_is_rejected(tmp_path):
    shutil.copytree(ROOT / "templates", tmp_path / "templates")
    (tmp_path / "templates/.env.backup").write_text("QA-FIXTURE", encoding="utf-8")
    with pytest.raises(ValueError, match="rahasia"):
        support.validate_templates(tmp_path / "templates")


def test_public_and_application_config_reject_server_fields(public, config):
    path, raw, _ = public
    raw["database_password"] = "QA-SECRET-DO-NOT-PRINT"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="kolom terlarang"):
        support.validate_public(path)
    path, raw = config
    raw["signing_key_path"] = "secrets/license-private.pem"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="asing/rahasia"):
        support.validate_config(path)


def test_config_relative_to_file_and_accepts_windows_bom(config, tmp_path, monkeypatch):
    path, raw = config
    path.write_text(json.dumps(raw), encoding="utf-8-sig")
    monkeypatch.chdir(ROOT.parent)
    _, settings = support.validate_config(path)
    assert settings.stockfish_path == tmp_path / "engine/stockfish.exe"
    assert settings.runtime_dir == tmp_path / "runtime"


def test_initialization_idempotent_does_not_overwrite_config(tmp_path, public, monkeypatch):
    monkeypatch.setattr(bootstrap, "validate_engine", lambda path: None)
    monkeypatch.setattr(bootstrap, "stockfish_notices", lambda path: [])
    destination = tmp_path / "config.json"
    assert bootstrap.initialize(destination, public[0], tmp_path / "engine.exe", ROOT / "templates")
    raw = json.loads(destination.read_text(encoding="utf-8"))
    raw["engine_strength"] = "Human"
    destination.write_text(json.dumps(raw), encoding="utf-8")
    before = destination.read_bytes()
    assert not bootstrap.initialize(destination, public[0], tmp_path / "other.exe", tmp_path / "other")
    assert destination.read_bytes() == before


def test_missing_assets_do_not_leave_generated_config(tmp_path, public):
    destination = tmp_path / "config.json"
    with pytest.raises(ValueError, match="Stockfish"):
        bootstrap.initialize(destination, public[0], tmp_path / "missing.exe", ROOT / "templates")
    assert not destination.exists()
    assert not list(tmp_path.glob(".config-*"))


def test_key_pair_mismatch_detected_without_rotation(public, tmp_path):
    _, raw, key = public
    pem = tmp_path / "qa-private.pem"
    pem.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    before = pem.read_bytes()
    assert len(verify_pair(raw, pem, "qa-test")) == 64
    with pytest.raises(ValueError, match="ID signing key"):
        verify_pair(raw, pem, "wrong-id")
    raw["public_keys"]["qa-test"] = base64.urlsafe_b64encode(bytes(32)).decode()
    with pytest.raises(ValueError, match="bukan pasangan"):
        verify_pair(raw, pem, "qa-test")
    assert pem.read_bytes() == before


def test_output_cannot_target_source_or_another_repo(tmp_path):
    with pytest.raises(ValueError, match="outputs/"):
        support.validate_output(ROOT / "src")
    with pytest.raises(ValueError, match="outputs/"):
        support.validate_output(tmp_path)


def test_build_seed_selects_png_only_and_removes_machine_paths(config, public, tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("windows_build_test", ROOT / "packaging/build_portable.py")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    path, raw = config
    # Binary kecil berikut hanya fixture unit test, tidak pernah input build rilis.
    engine = tmp_path / "fixture.exe"
    engine.write_bytes(b"unit-test-only")
    raw["stockfish_path"] = str(engine)
    path.write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setattr(build, "collect_licenses", lambda destination, engine: {})
    seed = tmp_path / "seed"
    seed.mkdir()
    info = build.build_seed(seed, path, public[0])
    packaged = json.loads((seed / "config.json").read_text(encoding="utf-8"))
    assert packaged["stockfish_path"] == "engine/stockfish.exe"
    assert packaged["templates_dir"] == "templates"
    assert packaged["runtime_dir"] == "runtime"
    assert len(list((seed / "templates").rglob("*.png"))) == 64
    assert not any(support.forbidden_name(p) for p in info["payload_sha256"])
    assert json.loads((seed / "licensing-public.json").read_text(encoding="utf-8")) == public[1]
