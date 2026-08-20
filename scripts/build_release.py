"""Build a deterministic release archive from the byte-level manifest."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "PACK_MANIFEST.json"
DIST = ROOT / "dist"
VERSION = "1.0.1"
ARCHIVE = DIST / f"validator-fate-profiles-v{VERSION}.zip"
CHECKSUMS = DIST / "SHA256SUMS.txt"
PREFIX = f"validator-fate-profiles-v{VERSION}"
ZIP_TIMESTAMP = (2026, 8, 20, 0, 0, 0)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if (
        manifest.get("schema_version") != 2
        or manifest.get("name") != "validator-fate-profiles"
        or manifest.get("version") != VERSION
    ):
        raise RuntimeError("unsupported or mismatched package manifest")
    for relative, record in manifest["files"].items():
        archive_path = PurePosixPath(relative)
        if (
            archive_path.is_absolute()
            or ".." in archive_path.parts
            or "\\" in relative
            or archive_path.as_posix() != relative
        ):
            raise RuntimeError(f"unsafe manifest path: {relative}")
        source = (ROOT / Path(*archive_path.parts)).resolve()
        if not source.is_relative_to(ROOT.resolve()):
            raise RuntimeError(f"manifest path escapes the repository: {relative}")
        if not source.is_file():
            raise FileNotFoundError(source)
        if source.stat().st_size != record["size"] or _sha256(source) != record["sha256"]:
            raise RuntimeError(f"manifest payload drifted: {relative}")
    paths = ["PACK_MANIFEST.json", *sorted(manifest["files"])]
    DIST.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in paths:
            source = ROOT / Path(*PurePosixPath(relative).parts)
            if not source.is_file():
                raise FileNotFoundError(source)
            info = zipfile.ZipInfo(f"{PREFIX}/{relative}", ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            archive.writestr(info, source.read_bytes())
    CHECKSUMS.write_text(f"{_sha256(ARCHIVE)}  {ARCHIVE.name}\n", encoding="ascii", newline="\n")
    display_path = ARCHIVE.relative_to(ROOT) if ARCHIVE.is_relative_to(ROOT) else Path(ARCHIVE.name)
    print(f"wrote {display_path} ({ARCHIVE.stat().st_size} bytes)")
    print(f"sha256 {_sha256(ARCHIVE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
