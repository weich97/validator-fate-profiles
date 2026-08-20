"""Build the open technical note from its LaTeX source."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "report"
SOURCE_DATE_EPOCH = "1787184000"  # 2026-08-20T00:00:00Z


def _require_tool(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise RuntimeError(f"required TeX tool is unavailable: {name}")
    return executable


def _run(argv: list[str], environment: dict[str, str], *, cwd: Path) -> None:
    print("running", " ".join(Path(part).name if index == 0 else part for index, part in enumerate(argv)))
    subprocess.run(argv, cwd=cwd, env=environment, check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    report = args.report_dir.resolve()
    source = report / "technical_note.tex"
    output = report / "technical_note.pdf"
    if not source.is_file():
        raise FileNotFoundError(source)

    pdflatex = _require_tool("pdflatex")
    biber = _require_tool("biber")
    environment = dict(os.environ)
    environment.update(
        {
            "SOURCE_DATE_EPOCH": SOURCE_DATE_EPOCH,
            "FORCE_SOURCE_DATE": "1",
            "TZ": "UTC",
        }
    )
    latex = [pdflatex, "-interaction=nonstopmode", "-halt-on-error", source.name]
    _run(latex, environment, cwd=report)
    _run([biber, source.stem], environment, cwd=report)
    _run(latex, environment, cwd=report)
    _run(latex, environment, cwd=report)

    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError("technical-note build did not produce a PDF")
    display = output.relative_to(ROOT) if output.is_relative_to(ROOT) else Path(output.name)
    print(f"wrote {display}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
