"""Rebuild the byte-level manifest for the public research artifact."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "PACK_MANIFEST.json"
IGNORED_DIRECTORIES = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", "dist", "tmp"}
IGNORED_FILENAMES = {
    "PACK_MANIFEST.json",
    "technical_note.aux",
    "technical_note.bbl",
    "technical_note.bcf",
    "technical_note.blg",
    "technical_note.log",
    "technical_note.out",
    "technical_note.run.xml",
}


def _included(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in IGNORED_DIRECTORIES or part == "__pycache__" for part in relative.parts):
        return False
    if path.name in IGNORED_FILENAMES or path.suffix in {".pyc", ".pyo"}:
        return False
    return path.is_file()


def _purpose(relative: str) -> str:
    if relative.startswith("evidence/artifact_case/"):
        return "pseudonymized artifact-case evidence"
    if relative.startswith("evidence/external_case/"):
        return "external-package evidence or provenance"
    if relative.startswith("report/figures/"):
        return "generated figure released with the technical note"
    if relative.startswith("report/"):
        return "open technical note source or compiled output"
    if relative == "scripts/render_gate_attribution.py":
        return "source code for the released PDF and PNG figure"
    if relative == "scripts/build_report.py":
        return "technical-note build script"
    if relative.startswith("scripts/") or relative == "verify.py":
        return "artifact build, verification, or release tooling"
    if relative == "requirements/figure.txt":
        return "pinned environment for figure reconstruction"
    if relative == "requirements/report-build-environment.txt":
        return "recorded environment for byte-identical technical-note reconstruction"
    if relative.startswith(".github/"):
        return "continuous verification configuration"
    if relative in {"LICENSE", "THIRD_PARTY_NOTICES.md"}:
        return "license or third-party notice"
    return "repository documentation or metadata"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    entries: dict[str, dict[str, str | int]] = {}
    for path in sorted((item for item in ROOT.rglob("*") if _included(item)), key=lambda item: item.as_posix()):
        relative = path.relative_to(ROOT).as_posix()
        entries[relative] = {
            "purpose": _purpose(relative),
            "sha256": _sha256(path),
            "size": path.stat().st_size,
        }

    manifest = {
        "schema_version": 2,
        "name": "validator-fate-profiles",
        "version": "1.0.0",
        "files": entries,
    }
    OUTPUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUTPUT.name} with {len(entries)} payload files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
