from __future__ import annotations

import io
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import install_source_python_packages as installer  # noqa: E402
from scripts import source_python_batch as source_batch  # noqa: E402

SOURCE_DIRECTORY = ROOT / "content" / "imported" / "source-backed"


def _tar_with_member(member: tarfile.TarInfo, data: bytes = b"") -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:xz") as bundle:
        if member.isfile():
            member.size = len(data)
            bundle.addfile(member, io.BytesIO(data))
        else:
            bundle.addfile(member)
    return buffer.getvalue()


def test_embedded_source_batch_matches_native_package_ids() -> None:
    rows = source_batch.load_python_candidates(SOURCE_DIRECTORY)
    assert len(rows) == 20
    assert {str(row["id"]) for row in rows} == set(installer.EXPECTED_PACKAGE_IDS)
    assert len({str(row["slug"]) for row in rows}) == 20


def test_installer_materializes_and_rechecks_exact_packages(tmp_path: Path) -> None:
    output = tmp_path / "questions"
    first = installer.install_packages(SOURCE_DIRECTORY, output)
    second = installer.install_packages(SOURCE_DIRECTORY, output)
    checked = installer.check_packages(SOURCE_DIRECTORY, output)

    assert first["packages"] == 20
    assert first["installed"] == list(installer.EXPECTED_PACKAGE_IDS)
    assert second["installed"] == []
    assert second["unchanged"] == list(installer.EXPECTED_PACKAGE_IDS)
    assert checked["status"] == "valid"
    assert checked["packages"] == 20


def test_archive_checksum_corruption_fails_closed(tmp_path: Path) -> None:
    archive_directory = tmp_path / "archive"
    archive_directory.mkdir()
    for source in sorted(SOURCE_DIRECTORY.glob(installer.PART_GLOB)):
        (archive_directory / source.name).write_bytes(source.read_bytes())
    first = sorted(archive_directory.glob(installer.PART_GLOB))[0]
    data = bytearray(first.read_bytes())
    data[0] ^= 0xFF
    first.write_bytes(data)

    with pytest.raises(ValueError, match="checksum mismatch"):
        installer.assemble_archive(archive_directory)


def test_archive_path_traversal_is_rejected(tmp_path: Path) -> None:
    member = tarfile.TarInfo("../escape")
    member.type = tarfile.REGTYPE
    with pytest.raises(ValueError, match="unsafe archive member path"):
        installer.extract_archive(_tar_with_member(member, b"blocked"), tmp_path)
    assert not (tmp_path.parent / "escape").exists()


def test_archive_links_are_rejected(tmp_path: Path) -> None:
    member = tarfile.TarInfo("IMP-0007/reference-link.py")
    member.type = tarfile.SYMTYPE
    member.linkname = "/etc/passwd"
    with pytest.raises(ValueError, match="regular file or directory"):
        installer.extract_archive(_tar_with_member(member), tmp_path)
