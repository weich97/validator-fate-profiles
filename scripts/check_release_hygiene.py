"""Reject private paths, credentials, submission residue, and missing PDF lineage."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRECTORIES = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", "dist", "tmp"}
SKIP_FILENAMES = {
    "technical_note.aux",
    "technical_note.bbl",
    "technical_note.bcf",
    "technical_note.blg",
    "technical_note.log",
    "technical_note.out",
    "technical_note.run.xml",
}


def _brand_tokens() -> tuple[bytes, ...]:
    # Split literals so the hygiene checker does not itself introduce them.
    return (
        ("co" + "dex").encode(),
        ("cl" + "aude").encode(),
        ("anth" + "ropic").encode(),
        ("open" + "ai").encode(),
        ("chat" + "gpt").encode(),
    )


def _private_path_tokens() -> tuple[bytes, ...]:
    return (
        ("c:" + "\\users\\").encode(),
        ("d:" + "\\trade" + "arena").encode(),
        ("/" + "users/").encode(),
        ("/" + "home/").encode(),
        ("file" + "://").encode(),
    )


def _files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if (
            path.is_file()
            and path.name not in SKIP_FILENAMES
            and path.suffix not in {".pyc", ".pyo"}
            and not any(part in SKIP_DIRECTORIES or part == "__pycache__" for part in relative.parts)
        ):
            files.append(path)
    return files


def _check_content() -> int:
    forbidden = _brand_tokens() + _private_path_tokens()
    secret_patterns = (
        re.compile(rb"gh[pousr]_[A-Za-z0-9_]{16,}"),
        re.compile(rb"sk-[A-Za-z0-9_-]{16,}"),
        re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    )
    failures: list[str] = []
    checked = 0
    for path in _files():
        relative = path.relative_to(ROOT).as_posix()
        data = path.read_bytes().lower()
        checked += 1
        for token in forbidden:
            if token in data or token.decode(errors="ignore") in relative.lower():
                failures.append(f"forbidden release token in {relative}")
        for pattern in secret_patterns:
            if pattern.search(data):
                failures.append(f"credential-shaped value in {relative}")
    if failures:
        raise AssertionError("\n".join(sorted(set(failures))))
    return checked


def _check_report() -> int:
    source = (ROOT / "report/technical_note.tex").read_text(encoding="utf-8")
    markers = (
        "Anonymous " + "author(s)",
        "Information and Software " + "Technology",
        "els" + "article",
    )
    for marker in markers:
        if marker in source:
            raise AssertionError(f"submission-only marker remains in technical note: {marker}")
    if "\\author{Weicheng Xue" not in source:
        raise AssertionError("public author marker is missing from technical note")
    return 4


def _check_pdf_lineage() -> int:
    pdfs = {
        path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*.pdf") if "tmp" not in path.relative_to(ROOT).parts
    }
    expected = {
        "report/figures/attribution_gap.pdf",
        "report/technical_note.pdf",
    }
    if pdfs != expected:
        raise AssertionError(f"unexpected PDF set: {sorted(pdfs ^ expected)}")
    dependencies = {
        "report/figures/attribution_gap.pdf": {
            "scripts/render_gate_attribution.py",
            "evidence/artifact_case/e1_source_matrix.csv",
            "evidence/artifact_case/e1_leave_one_out.csv",
            "requirements/figure.txt",
        },
        "report/technical_note.pdf": {
            "scripts/build_report.py",
            "report/technical_note.tex",
            "report/refs.bib",
            "report/figures/attribution_gap.pdf",
            "provenance/report-build-environment.md",
        },
    }
    for pdf, sources in dependencies.items():
        if not (ROOT / pdf).is_file():
            raise AssertionError(f"released PDF is missing: {pdf}")
        for source in sources:
            if not (ROOT / source).is_file():
                raise AssertionError(f"PDF source is missing for {pdf}: {source}")
    return len(expected) + sum(len(items) for items in dependencies.values())


def _check_history_if_present() -> int:
    if not (ROOT / ".git").is_dir():
        return 0
    result = subprocess.run(
        ["git", "log", "--all", "--format=%an <%ae> | %cn <%ce> | %s%n%b"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    lowered = result.stdout.lower().encode()
    for token in _brand_tokens():
        if token in lowered:
            raise AssertionError("forbidden assistant attribution remains in Git history")
    for token in _private_path_tokens()[:2]:
        if token in lowered:
            raise AssertionError("private host path remains in Git history")
    return 1


def main() -> int:
    checks = _check_content() + _check_report() + _check_pdf_lineage() + _check_history_if_present()
    print(f"release hygiene passed: {checks} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
