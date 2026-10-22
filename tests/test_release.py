"""Regresi integritas aset serta allowlist arsip rilis."""
import io
import json
from pathlib import Path
import stat
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_release import create_archive, validate_tag, validate_build
from provision_release_assets import safe_members, extract_engine, download_asset, provision_public


@pytest.mark.parametrize("tag", ["v0.1.0", "v0.1.0-rc.1", "v0.1.0-beta.2"])
def test_release_tag_matches_project_version(tag):
    assert validate_tag(tag, "0.1.0") == tag[1:]


@pytest.mark.parametrize("tag", ["v0.2.0", "0.1.0", "v0.1.0;echo bad", "v0.1.0-latest", "v0.1.0-rc.1/escape"])
def test_incorrect_or_unsafe_release_tags_rejected(tag):
    with pytest.raises(ValueError, match="Tag harus"):
        validate_tag(tag, "0.1.0")


@pytest.mark.parametrize("name", ["../outside", "/absolute", "C:/outside", "..\\outside"])
def test_zip_traversal_rejected(name):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr(name, "fixture")
    with zipfile.ZipFile(data) as archive, pytest.raises(ValueError, match="tidak aman"):
        safe_members(archive)


def test_zip_symlink_rejected():
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        info = zipfile.ZipInfo("link")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, "../outside")
    with zipfile.ZipFile(data) as archive, pytest.raises(ValueError, match="tidak aman"):
        safe_members(archive)


def test_duplicate_windows_paths_rejected():
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("README.md", "one")
        archive.writestr("readme.md", "two")
    with zipfile.ZipFile(data) as archive, pytest.raises(ValueError, match="duplikat"):
        safe_members(archive)


def test_existing_engine_files_not_overwritten(tmp_path):
    archive_path = tmp_path / "fixture.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("stockfish/engine.exe", b"unit-test-only")
        archive.writestr("stockfish/src/Makefile", "fixture")
    destination = tmp_path / "engine"
    engine = extract_engine(archive_path, destination, "engine.exe")
    assert extract_engine(archive_path, destination, "engine.exe") == engine
    engine.write_bytes(b"existing-local-content")
    with pytest.raises(ValueError, match="tidak ditimpa"):
        extract_engine(archive_path, destination, "engine.exe")
    assert engine.read_bytes() == b"existing-local-content"


def test_engine_cache_checksum_failure_is_not_silently_replaced(tmp_path):
    cache = tmp_path / "download.zip"
    cache.write_bytes(b"existing-file")
    with pytest.raises(ValueError, match="Checksum cache"):
        download_asset("https://github.com/official-stockfish/Stockfish/releases/download/test/test.zip", "0"*64, cache)
    assert cache.read_bytes() == b"existing-file"


def test_concurrent_download_partial_is_preserved(tmp_path):
    cache = tmp_path / "engine.zip"
    partial = cache.with_suffix(".downloading")
    partial.write_bytes(b"another-process")
    with pytest.raises(FileExistsError):
        download_asset("https://github.com/official-stockfish/Stockfish/releases/download/test/test.zip", "0"*64, cache)
    assert partial.read_bytes() == b"another-process"


def test_public_provisioning_refuses_server_configuration(tmp_path):
    target = tmp_path / "licensing-public.json"
    with pytest.raises(ValueError, match="terlarang"):
        provision_public(target, json.dumps({"private_key": "QA-FIXTURE"}))
    assert not target.exists()


def test_stale_or_unverified_executable_cannot_be_released(tmp_path):
    executable = tmp_path / "fixture.exe"
    executable.write_bytes(b"unit-test-only")
    with pytest.raises(ValueError, match="belum memiliki"):
        validate_build(executable, {})
    with pytest.raises(ValueError, match="Checksum EXE"):
        validate_build(executable, {"validation": {"archive": "PASS", "portable_smoke": "PASS"}, "exe_sha256": "0"*64})


def test_release_archive_never_copies_local_server_secrets(tmp_path):
    executable = tmp_path / "fixture.exe"
    executable.write_bytes(b"unit-test-only")
    notice = tmp_path / "BACA-DULU.txt"
    notice.write_text("Petunjuk QA", encoding="utf-8")
    (tmp_path / ".env").write_text("QA-FIXTURE", encoding="utf-8")
    (tmp_path / "license-private.pem").write_text("QA-FIXTURE", encoding="utf-8")
    output = tmp_path / "release"
    archive_path = create_archive(executable, {}, notice, "v0.1.0-rc.1", output)
    with zipfile.ZipFile(archive_path) as archive:
        assert {Path(name).name for name in archive.namelist()} == {"ChessLab-Coach.exe", "BACA-DULU.txt", "build-info.json"}
    assert (output / "SHA256SUMS.txt").is_file()
    with pytest.raises(ValueError, match="sudah ada"):
        create_archive(executable, {}, notice, "v0.1.0-rc.1", output)
