"""Render baseline first-hit provenance and scoped-bypass fate profiles.

Inputs:
  evidence/artifact_case/e1_source_matrix.csv
  evidence/artifact_case/e1_leave_one_out.csv

Outputs:
  report/figures/attribution_gap.pdf
  report/figures/attribution_gap.png
"""

from __future__ import annotations

import argparse
import csv
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_MATRIX = ROOT / "evidence/artifact_case/e1_source_matrix.csv"
DEFAULT_LEAVE_ONE_OUT = ROOT / "evidence/artifact_case/e1_leave_one_out.csv"
DEFAULT_OUTPUT_DIR = ROOT / "report/figures"
STEM = "attribution_gap"

STAGES = (
    "schema_validation",
    "single_artifact_validator",
    "approval_hash_binding",
    "cross_artifact_preflight",
    "orchestrator_revalidation",
)
STAGE_LABELS = {
    "schema_validation": "Schema validation",
    "single_artifact_validator": "Component validation",
    "approval_hash_binding": "Approval/hash binding",
    "cross_artifact_preflight": "Cross-artifact preflight",
    "orchestrator_revalidation": "Lifecycle/journal outcome",
}
SOURCE_KEYS = ("directed", "fuzz")
SOURCE_LABELS = {
    "directed": "Directed probes",
    "fuzz": "Generic mutations",
}
SOURCE_COLORS = {
    "directed": "#35689A",
    "fuzz": "#78A6C8",
}
FATES = (
    ("absorbed_by_later_layer", "Later controlled rejection ($S_i$)", "#35689A"),
    ("newly_escaping", "Newly accepted ($C_i$)", "#D17A22"),
    ("downstream_crashes", "Downstream exception ($X_i$)", "#8E3B46"),
)
INK = "#202020"
GRID = "#D7D7D7"
FIGURE_TIMESTAMP = datetime(2026, 8, 17, tzinfo=timezone.utc)

CountMatrix = dict[str, dict[str, int]]


def _require_columns(path: Path, fieldnames: Sequence[str] | None, required: set[str]) -> None:
    missing = required - set(fieldnames or ())
    if missing:
        raise ValueError(f"{path} is missing columns: {sorted(missing)}")


def _nonnegative_int(value: object, *, context: str) -> int:
    if not isinstance(value, (str, bytes, bytearray, int)):
        raise ValueError(f"{context} is not an integer: {value!r}")
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{context} is not an integer: {value!r}") from exc
    if parsed < 0:
        raise ValueError(f"{context} must be nonnegative, got {parsed}")
    return parsed


def load_source_matrix(path: Path) -> CountMatrix:
    required_columns = {"source", "outcome", "count", "source_total"}
    allowed_sources = {*SOURCE_KEYS, "all"}
    allowed_outcomes = {*STAGES, "escape"}
    table: CountMatrix = {source: {} for source in allowed_sources}
    totals: dict[str, int] = {}

    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        _require_columns(path, reader.fieldnames, required_columns)
        for line_number, row in enumerate(reader, start=2):
            source = row["source"]
            outcome = row["outcome"]
            if source not in allowed_sources:
                raise ValueError(f"{path}:{line_number} has unknown source {source!r}")
            if outcome not in allowed_outcomes:
                raise ValueError(f"{path}:{line_number} has unknown outcome {outcome!r}")
            if outcome in table[source]:
                raise ValueError(f"{path}:{line_number} duplicates {source}/{outcome}")

            count = _nonnegative_int(row["count"], context=f"{path}:{line_number} count")
            source_total = _nonnegative_int(
                row["source_total"],
                context=f"{path}:{line_number} source_total",
            )
            previous_total = totals.setdefault(source, source_total)
            if previous_total != source_total:
                raise ValueError(f"{path} has inconsistent totals for source {source!r}")
            table[source][outcome] = count

    for source in allowed_sources:
        missing = allowed_outcomes - set(table[source])
        if missing:
            raise ValueError(f"{path} is missing outcomes for {source!r}: {sorted(missing)}")
        observed_total = sum(table[source].values())
        if observed_total != totals[source]:
            raise ValueError(f"{path} counts for {source!r} sum to {observed_total}, not source_total={totals[source]}")

    if totals["all"] != totals["directed"] + totals["fuzz"]:
        raise ValueError(f"{path} all/source totals do not add up")
    for outcome in allowed_outcomes:
        expected = table["directed"][outcome] + table["fuzz"][outcome]
        if table["all"][outcome] != expected:
            raise ValueError(f"{path} all/{outcome}={table['all'][outcome]}, but directed+generic={expected}")

    return {source: {stage: table[source][stage] for stage in STAGES} for source in (*SOURCE_KEYS, "all")}


def load_bypass_fates(path: Path) -> CountMatrix:
    required_columns = {
        "layer",
        "first_intercepts_when_present",
        "absorbed_by_later_layer",
        "newly_escaping",
        "downstream_crashes",
    }
    rows: CountMatrix = {}

    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        _require_columns(path, reader.fieldnames, required_columns)
        for line_number, row in enumerate(reader, start=2):
            stage = row["layer"]
            if stage not in STAGES:
                raise ValueError(f"{path}:{line_number} has unknown stage {stage!r}")
            if stage in rows:
                raise ValueError(f"{path}:{line_number} duplicates stage {stage!r}")

            first_hits = _nonnegative_int(
                row["first_intercepts_when_present"],
                context=f"{path}:{line_number} first_intercepts_when_present",
            )
            fates = {
                field: _nonnegative_int(row[field], context=f"{path}:{line_number} {field}")
                for field, _label, _color in FATES
            }
            fate_total = sum(fates.values())
            if fate_total != first_hits:
                raise ValueError(
                    f"{path}:{line_number} bypass fates for {stage!r} do not partition "
                    f"its first hits: {fate_total} != {first_hits}"
                )
            rows[stage] = fates

    missing = set(STAGES) - set(rows)
    if missing:
        raise ValueError(f"{path} is missing stages: {sorted(missing)}")
    return rows


def validate_alignment(source_counts: CountMatrix, bypass_fates: CountMatrix) -> None:
    for stage in STAGES:
        first_hits = source_counts["all"][stage]
        fate_total = sum(bypass_fates[stage].values())
        if first_hits != fate_total:
            raise ValueError(
                f"source matrix and bypass table disagree for {stage}: "
                f"{first_hits} first rejections versus {fate_total} bypass outcomes"
            )


def _style_axis(ax: Axes) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", color=GRID, linewidth=0.6, alpha=0.75)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", labelsize=9.5)


def _panel_first_rejections(ax: Axes, source_counts: CountMatrix) -> None:
    positions = list(range(len(STAGES)))
    bar_height = 0.34
    maximum = max(source_counts[source][stage] for source in SOURCE_KEYS for stage in STAGES)

    for source, offset in zip(SOURCE_KEYS, (-bar_height / 2, bar_height / 2), strict=True):
        values = [source_counts[source][stage] for stage in STAGES]
        y_positions = [position + offset for position in positions]
        ax.barh(
            y_positions,
            values,
            height=bar_height,
            color=SOURCE_COLORS[source],
            label=SOURCE_LABELS[source],
        )
        for y_position, value in zip(y_positions, values, strict=True):
            ax.text(
                value + maximum * 0.012,
                y_position,
                str(value),
                va="center",
                fontsize=9.2,
                color=INK,
            )

    ax.set_yticks(positions)
    ax.set_yticklabels([STAGE_LABELS[stage] for stage in STAGES])
    ax.invert_yaxis()
    ax.set_xlim(0, maximum * 1.17)
    ax.set_xlabel("Variants in the baseline first-hit set", fontsize=10)
    ax.set_title("(a) Baseline first-hit provenance", fontsize=11)
    ax.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, -0.36),
        frameon=False,
        fontsize=9.2,
        ncol=2,
    )
    _style_axis(ax)


def _panel_bypass_fates(ax: Axes, bypass_fates: CountMatrix) -> None:
    positions = list(range(len(STAGES)))
    totals = [sum(bypass_fates[stage].values()) for stage in STAGES]
    if any(total <= 0 for total in totals):
        raise ValueError("every stage must have at least one baseline first rejection")

    left = [0.0] * len(STAGES)
    for field, label, color in FATES:
        counts = [bypass_fates[stage][field] for stage in STAGES]
        widths = [count / total for count, total in zip(counts, totals, strict=True)]
        ax.barh(
            positions,
            widths,
            left=left,
            height=0.58,
            color=color,
            label=label,
        )
        for y_position, start, width, count in zip(
            positions,
            left,
            widths,
            counts,
            strict=True,
        ):
            if count == 0:
                continue
            if width >= 0.035:
                ax.text(
                    start + width / 2,
                    y_position,
                    str(count),
                    ha="center",
                    va="center",
                    fontsize=9.0,
                    color="white",
                    fontweight="bold",
                )
            else:
                ax.annotate(
                    str(count),
                    xy=(start + width, y_position),
                    xytext=(3, 0),
                    textcoords="offset points",
                    va="center",
                    fontsize=8.8,
                    color=color,
                    fontweight="bold",
                )
        left = [start + width for start, width in zip(left, widths, strict=True)]

    for y_position, total in zip(positions, totals, strict=True):
        ax.text(1.04, y_position, f"n={total}", va="center", fontsize=9.0, color=INK)

    ax.set_yticks(positions)
    ax.set_yticklabels([STAGE_LABELS[stage] for stage in STAGES])
    ax.invert_yaxis()
    ax.set_xlim(0, 1.18)
    ax.set_xticks([0.0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"])
    ax.set_xlabel("Share of the baseline first-hit set", fontsize=10)
    ax.set_title("(b) Fate profile under scoped bypass", fontsize=11)
    ax.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, -0.36),
        frameon=False,
        fontsize=8.7,
        ncol=3,
    )
    _style_axis(ax)


def build_figure(source_counts: CountMatrix, bypass_fates: CountMatrix) -> Figure:
    validate_alignment(source_counts, bypass_fates)
    figure, (ax_first, ax_fates) = plt.subplots(1, 2, figsize=(11.6, 4.9))
    _panel_first_rejections(ax_first, source_counts)
    _panel_bypass_fates(ax_fates, bypass_fates)
    figure.tight_layout(rect=(0.0, 0.23, 1.0, 1.0), w_pad=2.7)
    return figure


def render(
    source_matrix_path: Path,
    leave_one_out_path: Path,
    output_dir: Path,
) -> tuple[Path, Path]:
    source_counts = load_source_matrix(source_matrix_path)
    bypass_fates = load_bypass_fates(leave_one_out_path)
    figure = build_figure(source_counts, bypass_fates)

    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"{STEM}.pdf"
    png_path = output_dir / f"{STEM}.png"
    figure.savefig(
        pdf_path,
        bbox_inches="tight",
        metadata={
            "Title": "Baseline first-hit provenance and scoped-bypass fate profiles",
            "Creator": "scripts/render_gate_attribution.py",
            "CreationDate": FIGURE_TIMESTAMP,
            "ModDate": FIGURE_TIMESTAMP,
        },
    )
    figure.savefig(
        png_path,
        bbox_inches="tight",
        dpi=220,
        metadata={
            "Title": "Baseline first-hit provenance and scoped-bypass fate profiles",
            "Software": "scripts/render_gate_attribution.py",
        },
    )
    plt.close(figure)
    return pdf_path, png_path


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _display_path(path: Path) -> Path:
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render attribution and stage-bypass outcomes.")
    parser.add_argument("--source-matrix", default=str(DEFAULT_SOURCE_MATRIX))
    parser.add_argument("--leave-one-out", default=str(DEFAULT_LEAVE_ONE_OUT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)

    pdf_path, png_path = render(
        _resolve_path(args.source_matrix),
        _resolve_path(args.leave_one_out),
        _resolve_path(args.output_dir),
    )
    print(f"wrote {_display_path(pdf_path)}")
    print(f"wrote {_display_path(png_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
