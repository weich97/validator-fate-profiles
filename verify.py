"""Verify the released validator-fate evidence and technical note."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parent
ARTIFACT = ROOT / "evidence" / "artifact_case"
EXTERNAL = ROOT / "evidence" / "external_case"
REPORT = ROOT / "report" / "technical_note.tex"
BIBLIOGRAPHY = ROOT / "report" / "refs.bib"
FIGURE = ROOT / "report" / "figures" / "attribution_gap.pdf"
FIGURE_PNG = ROOT / "report" / "figures" / "attribution_gap.png"
REPORT_PDF = ROOT / "report" / "technical_note.pdf"
PACK_MANIFEST = ROOT / "PACK_MANIFEST.json"

ARTIFACT_STAGES = (
    "schema_validation",
    "single_artifact_validator",
    "approval_hash_binding",
    "cross_artifact_preflight",
    "orchestrator_revalidation",
)
ARTIFACT_ACCEPTED = "escape"
EXTERNAL_STAGES = ("ruff_format", "ruff_lint", "mypy", "pytest")
EXTERNAL_REJECTION_REASONS = {
    "ruff_format": "ruff_documented_rejection",
    "ruff_lint": "ruff_documented_rejection",
    "mypy": "mypy_documented_rejection",
    "pytest": "pytest_failure_report",
}
EXTERNAL_FREEZE_LABEL = "external-freeze-v1"
EXTERNAL_CATALOG_SHA256 = "03fe53670fd871aa05e6c069887ae09db162a466c4fcdba767267a4e28416e3b"
FIGURE_SHA256 = "760f2771e6c5139c4b7b524e78acf985d81523e43fbe97beb26ca0330809e28f"
FIGURE_PNG_SHA256 = "27ff96f59ebb2678ac50e2268d10c0635576b0ba5638f166d78cba0e8ed24fce"

EXPECTED_SOURCE_OUTCOMES = {
    "directed": (63, 20, 32, 17, 9, 5),
    "fuzz": (198, 0, 4, 1, 0, 16),
    "all": (261, 20, 36, 18, 9, 21),
}
EXPECTED_ARTIFACT_BYPASS = {
    "schema_validation": (261, 0, 250, 11, 21),
    "single_artifact_validator": (20, 0, 20, 0, 21),
    "approval_hash_binding": (36, 0, 36, 0, 21),
    "cross_artifact_preflight": (18, 18, 0, 0, 39),
    "orchestrator_revalidation": (9, 9, 0, 0, 30),
}
EXPECTED_ARTIFACT_TRANSITIONS = Counter(
    {
        ("schema_validation", "single_artifact_validator"): 246,
        ("schema_validation", "cross_artifact_preflight"): 4,
        ("schema_validation", "downstream_crash"): 11,
        ("single_artifact_validator", "approval_hash_binding"): 6,
        ("single_artifact_validator", "cross_artifact_preflight"): 14,
        ("approval_hash_binding", "cross_artifact_preflight"): 36,
        ("cross_artifact_preflight", "escape"): 18,
        ("orchestrator_revalidation", "escape"): 9,
    }
)
EXPECTED_SOURCE_ADMISSION = {
    "directed": (0, 0, 0, 17, 9),
    "fuzz": (0, 0, 0, 1, 0),
}
EXPECTED_EXTERNAL_BASELINE = Counter({"pytest": 9, "mypy": 6, "accepted": 5, "ruff_format": 4})
EXPECTED_EXTERNAL_FATES = {
    "ruff_format": (4, 4, 0, Counter({"accepted": 4})),
    "ruff_lint": (0, 0, 0, Counter()),
    "mypy": (6, 4, 2, Counter({"accepted": 4, "pytest": 2})),
    "pytest": (9, 9, 0, Counter({"accepted": 9})),
}
EXPECTED_EXTERNAL_FAMILIES = Counter(
    {
        ("layout_spacing", "ruff_format", "accepted"): 4,
        ("parameter_reference", "mypy", "pytest"): 2,
        ("parameter_reference", "pytest", "accepted"): 2,
        ("annotation_atom", "mypy", "accepted"): 4,
        ("predicate_replacement", "pytest", "accepted"): 3,
        ("predicate_replacement", "accepted", "accepted"): 3,
        ("scalar_boundary", "pytest", "accepted"): 4,
        ("scalar_boundary", "accepted", "accepted"): 2,
    }
)
EXPECTED_RESULT_FILES = {
    "calibration_matrix.csv",
    "command_ledger.csv",
    "family_stage_summary.csv",
    "result_summary.json",
    "stage_summary.csv",
    "transition_matrix.csv",
    "workflow_ledger.csv",
}
EXPECTED_REFERENCES = {
    "hsueh1997faultinjection": "10.1109/2.585157",
    "jia2011mutation": "10.1109/tse.2010.62",
    "just2014mutants": "10.1145/2635868.2635929",
    "arlat2011collecting": "10.1109/ladc.2011.19",
    "steininger2002identifying": "10.1109/12.980011",
    "natella2013representativeness": "10.1109/tse.2011.124",
    "johnson2020causal": "10.1145/3377811.3380377",
    "du2023kill": "10.1145/3597926.3598090",
    "du2024ripples": "10.1145/3597503.3639179",
}
REQUIRED_FILES = {
    ".gitattributes",
    ".gitignore",
    "CITATION.cff",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "THIRD_PARTY_NOTICES.md",
    "evidence/artifact_case/e1_interception.csv",
    "evidence/artifact_case/e1_leave_one_out.csv",
    "evidence/artifact_case/e1_leave_one_out_ledger.csv",
    "evidence/artifact_case/e1_source_matrix.csv",
    "evidence/external_case/AMENDMENT_2026-08-18.md",
    "evidence/external_case/FROZEN_PLAN.md",
    "evidence/external_case/IDNA_LICENSE.md",
    "evidence/external_case/REPLICATION_DONE.md",
    "evidence/external_case/calibration_matrix.csv",
    "evidence/external_case/clean_compatibility.json",
    "evidence/external_case/command_ledger.csv",
    "evidence/external_case/family_stage_summary.csv",
    "evidence/external_case/mutation_catalog.json",
    "evidence/external_case/replication_lint_requirements.txt",
    "evidence/external_case/replication_test_requirements.txt",
    "evidence/external_case/result_summary.json",
    "evidence/external_case/run_manifest.json",
    "evidence/external_case/source_and_environment_manifest.json",
    "evidence/external_case/stage_summary.csv",
    "evidence/external_case/transition_matrix.csv",
    "evidence/external_case/workflow_ledger.csv",
    "report/figures/attribution_gap.pdf",
    "report/figures/attribution_gap.png",
    "report/technical_note.pdf",
    "report/technical_note.tex",
    "report/refs.bib",
    "requirements/figure.txt",
    "requirements/report-build-environment.txt",
    "scripts/build_report.py",
    "scripts/render_gate_attribution.py",
    "verify.py",
}

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


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _is_manifest_payload(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in IGNORED_DIRECTORIES or part == "__pycache__" for part in relative.parts):
        return False
    if path.name in IGNORED_FILENAMES or path.suffix in {".pyc", ".pyo"}:
        return False
    return path.is_file()


def verify_pack_manifest() -> int:
    manifest = _read_json(PACK_MANIFEST)
    _require(manifest["schema_version"] == 2, "unsupported package-manifest schema")
    _require(manifest["name"] == "validator-fate-profiles", "package name drifted")
    _require(manifest["version"] == "1.0.0", "package version drifted")
    entries = manifest["files"]
    _require(set(entries) >= REQUIRED_FILES, "package manifest is missing required files")
    observed = {path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*") if _is_manifest_payload(path)}
    _require(observed == set(entries), "working-tree payload differs from package manifest")
    for relative, record in entries.items():
        path = ROOT / relative
        _require(path.stat().st_size == record["size"], f"size mismatch: {relative}")
        _require(_sha256(path) == record["sha256"], f"hash mismatch: {relative}")
        _require(record["purpose"], f"missing purpose: {relative}")
    return 6 + len(entries) * 3


def verify_artifact_case() -> int:
    baseline = _read_csv(ARTIFACT / "e1_interception.csv")
    _require(len(baseline) == 365, "artifact baseline must contain 365 variants")
    _require(len({row["variant_id"] for row in baseline}) == 365, "variant ids are not unique")
    _require(
        Counter(row["source_stratum"] for row in baseline) == Counter({"fuzz": 219, "directed": 146}),
        "artifact source totals drifted",
    )
    _require(
        Counter(row["path_kind"] for row in baseline) == Counter({"static": 361, "lifecycle": 4}),
        "artifact path totals drifted",
    )
    outcomes = (*ARTIFACT_STAGES, ARTIFACT_ACCEPTED)
    baseline_by_id = {row["variant_id"]: row for row in baseline}
    for source, expected_outcomes in EXPECTED_SOURCE_OUTCOMES.items():
        rows = baseline if source == "all" else [row for row in baseline if row["source_stratum"] == source]
        counts = Counter(row["first_destination"] for row in rows)
        observed = tuple(counts[outcome] for outcome in outcomes)
        _require(observed == expected_outcomes, f"artifact {source} outcome vector drifted: {observed}")

    source_rows = _read_csv(ARTIFACT / "e1_source_matrix.csv")
    _require(len(source_rows) == 18, "artifact source matrix must contain 18 rows")
    by_key = {(row["source"], row["outcome"]): int(row["count"]) for row in source_rows}
    _require(len(by_key) == 18, "artifact source matrix keys are not unique")
    for source, expected_outcomes in EXPECTED_SOURCE_OUTCOMES.items():
        observed = tuple(by_key[(source, outcome)] for outcome in outcomes)
        _require(observed == expected_outcomes, f"artifact source matrix drifted for {source}")

    aggregate = _read_csv(ARTIFACT / "e1_leave_one_out.csv")
    _require(len(aggregate) == 5, "artifact bypass summary must contain five rows")
    aggregate_by_stage = {row["layer"]: row for row in aggregate}
    _require(set(aggregate_by_stage) == set(ARTIFACT_STAGES), "artifact bypass stages drifted")
    for stage, expected_bypass in EXPECTED_ARTIFACT_BYPASS.items():
        row = aggregate_by_stage[stage]
        observed = (
            int(row["first_intercepts_when_present"]),
            int(row["newly_escaping"]),
            int(row["absorbed_by_later_layer"]),
            int(row["downstream_crashes"]),
            int(row["escapes_without_layer"]),
        )
        _require(observed == expected_bypass, f"artifact bypass tuple drifted for {stage}")
        _require(sum(observed[1:4]) == observed[0], f"artifact fates do not close for {stage}")

    ledger = _read_csv(ARTIFACT / "e1_leave_one_out_ledger.csv")
    _require(len(ledger) == 1825, "artifact bypass ledger must contain 1,825 rows")
    keys = {(row["removed_stage"], row["variant_id"]) for row in ledger}
    _require(len(keys) == 1825, "artifact bypass keys are not unique")
    ledger_ids = {row["variant_id"] for row in ledger}
    _require(ledger_ids == set(baseline_by_id), "artifact baseline and bypass variant ids differ")
    _require(
        Counter(row["variant_id"] for row in ledger) == Counter({variant_id: 5 for variant_id in baseline_by_id}),
        "artifact bypass ledger must contain five rows per variant",
    )
    metadata: dict[str, tuple[str, str, str]] = {}
    stage_index = {stage: index for index, stage in enumerate(ARTIFACT_STAGES)}
    for row in ledger:
        baseline_row = baseline_by_id[row["variant_id"]]
        _require(row["removed_stage"] in ARTIFACT_STAGES, "artifact bypass ledger has an unknown stage")
        _require(row["source_stratum"] == baseline_row["source_stratum"], "artifact source metadata drifted")
        _require(
            row["baseline_first_destination"] == baseline_row["first_destination"],
            "artifact baseline destination drifted between ledgers",
        )
        current = (row["operator_family"], row["source_stratum"], row["baseline_first_destination"])
        _require(metadata.setdefault(row["variant_id"], current) == current, "artifact metadata drifted")
        removed = row["removed_stage"]
        baseline_destination = row["baseline_first_destination"]
        outcome = row["outcome_without_stage"]
        if baseline_destination == ARTIFACT_ACCEPTED:
            _require(row["fate"] == "baseline_escape", "artifact baseline-escape fate drifted")
            _require(outcome == ARTIFACT_ACCEPTED, "artifact baseline escape changed under bypass")
        elif baseline_destination != removed:
            _require(row["fate"] == "other_stage_first_hit", "artifact non-first-hit fate drifted")
            _require(outcome == baseline_destination, "artifact non-first-hit outcome drifted")
        elif outcome == ARTIFACT_ACCEPTED:
            _require(row["fate"] == "newly_escaping", "artifact admission fate drifted")
        elif outcome == "downstream_crash":
            _require(row["fate"] == "downstream_crash", "artifact exception fate drifted")
        else:
            _require(row["fate"] == "absorbed_by_later_layer", "artifact later-rejection fate drifted")
            _require(outcome in stage_index, "artifact later rejection has an unknown destination")
            _require(stage_index[outcome] > stage_index[removed], "artifact later rejection is not downstream")
    _require(len(metadata) == 365, "artifact bypass ledger has the wrong variant count")

    baseline_accepted = sum(row["first_destination"] == ARTIFACT_ACCEPTED for row in baseline)
    for stage in ARTIFACT_STAGES:
        row = aggregate_by_stage[stage]
        stage_rows = [entry for entry in ledger if entry["removed_stage"] == stage]
        first_hit_rows = [entry for entry in stage_rows if entry["baseline_first_destination"] == stage]
        newly_accepted = sum(entry["fate"] == "newly_escaping" for entry in first_hit_rows)
        later_rejected = sum(entry["fate"] == "absorbed_by_later_layer" for entry in first_hit_rows)
        exceptions = sum(entry["fate"] == "downstream_crash" for entry in first_hit_rows)
        expected_aggregate = {
            "first_intercepts_when_present": len(first_hit_rows),
            "escapes_with_layer": baseline_accepted,
            "escapes_without_layer": sum(entry["outcome_without_stage"] == ARTIFACT_ACCEPTED for entry in stage_rows),
            "newly_escaping": newly_accepted,
            "absorbed_by_later_layer": later_rejected,
            "downstream_crashes": exceptions,
        }
        for field, expected_value in expected_aggregate.items():
            _require(int(row[field]) == expected_value, f"artifact aggregate drifted for {stage}/{field}")
        expected_load_bearing = "yes" if newly_accepted + exceptions else "no"
        _require(row["load_bearing"] == expected_load_bearing, f"artifact load-bearing label drifted for {stage}")

    transitions = Counter(
        (row["removed_stage"], row["outcome_without_stage"])
        for row in ledger
        if row["baseline_first_destination"] == row["removed_stage"]
    )
    _require(transitions == EXPECTED_ARTIFACT_TRANSITIONS, "artifact transition matrix drifted")
    for source, expected_admission in EXPECTED_SOURCE_ADMISSION.items():
        observed = tuple(
            sum(
                row["source_stratum"] == source
                and row["removed_stage"] == stage
                and row["baseline_first_destination"] == stage
                and row["fate"] == "newly_escaping"
                for row in ledger
            )
            for stage in ARTIFACT_STAGES
        )
        _require(observed == expected_admission, f"artifact source admission drifted for {source}")
    return 52


def _expected_workflow_keys(analytic_ids: set[str], control_ids: set[str]) -> set[tuple[str, str, str]]:
    keys = {
        (replay, mutant_id, bypassed_stage)
        for replay in ("1", "2")
        for mutant_id in analytic_ids
        for bypassed_stage in ("none", *EXTERNAL_STAGES)
    }
    keys.update((replay, mutant_id, "none") for replay in ("1", "2") for mutant_id in control_ids)
    return keys


def _verify_command_semantics(commands: list[dict[str, str]]) -> int:
    for row in commands:
        classification = row["classification"]
        if classification == "pass":
            _require(row["returncode"] == "0", "passing command has a nonzero return code")
            _require(row["classification_reason"] == "exit_zero", "passing command has the wrong reason")
            _require(not row["diagnostic_excerpt"], "passing command unexpectedly retains a diagnostic")
        elif classification == "controlled_rejection":
            _require(row["stage"] in EXTERNAL_REJECTION_REASONS, "unknown rejecting command stage")
            _require(row["returncode"] == "1", "controlled rejection has the wrong return code")
            _require(
                row["classification_reason"] == EXTERNAL_REJECTION_REASONS[row["stage"]],
                "controlled rejection has the wrong reason",
            )
            _require(bool(row["diagnostic_excerpt"]), "controlled rejection lacks a diagnostic")
        else:
            raise AssertionError(f"unknown command classification: {classification}")
        if row["stage"] == "pytest":
            _require(row["collected_tests"] == "6405", "pytest collection count drifted")
        else:
            _require(not row["collected_tests"], "non-pytest command records a pytest collection count")
    return 8


def verify_external_case() -> int:
    source_manifest = _read_json(EXTERNAL / "source_and_environment_manifest.json")
    run_manifest = _read_json(EXTERNAL / "run_manifest.json")
    summary = _read_json(EXTERNAL / "result_summary.json")
    catalog = _read_json(EXTERNAL / "mutation_catalog.json")
    done = (EXTERNAL / "REPLICATION_DONE.md").read_text(encoding="utf-8")

    _require(source_manifest["source"]["name"] == "idna", "external source name drifted")
    _require(source_manifest["source"]["release_tag"] == "v3.18", "external release drifted")
    design = source_manifest["design"]
    _require(design["clean_collected_tests"] == 6405, "external test count drifted")
    _require(design["primary_mutants"] == 24, "external primary count drifted")
    _require(design["directed_calibration_mutants"] == 16, "external calibration count drifted")
    _require(design["control_probes"] == 2 and design["replays"] == 2, "external repeat design drifted")
    _require(tuple(design["stages"]) == EXTERNAL_STAGES, "external stages drifted")
    for environment in source_manifest["environment"].values():
        if not isinstance(environment, dict) or "executables" not in environment:
            continue
        _require(
            all("path" not in executable for executable in environment["executables"].values()),
            "external manifest retains host executable paths",
        )
    _require(_sha256(EXTERNAL / "mutation_catalog.json") == EXTERNAL_CATALOG_SHA256, "catalog hash drifted")
    _require(catalog["primary_selection"]["outcome_information_used"] is False, "selection used outcomes")
    _require(
        catalog["primary_selection"]["directed_calibration_influenced_selection"] is False,
        "calibration influenced primary selection",
    )
    primary = [item for item in catalog["mutants"] if item["stratum"] == "primary"]
    analytic = [item for item in catalog["mutants"] if item["stratum"] != "control"]
    controls = [item for item in catalog["mutants"] if item["stratum"] == "control"]
    _require(len(primary) == 24 and len(analytic) == 40 and len(controls) == 2, "catalog counts drifted")
    _require(all(item["intended_stage"] is None for item in primary), "primary mutants have intended stages")
    _require(
        len({item["mutated_source_sha256"] for item in analytic}) == 40,
        "external source hashes are not unique",
    )

    _require(run_manifest["status"] == "COMPLETE", "external run is incomplete")
    _require(run_manifest["freeze_label"] == EXTERNAL_FREEZE_LABEL, "external freeze label drifted")
    _require(run_manifest["workflow_rows"] == 404 and run_manifest["command_rows"] == 1444, "row counts drifted")
    _require(run_manifest["no_infrastructure_errors"] is True, "external run has infrastructure errors")
    _require(run_manifest["two_serial_repeats_identical"] is True, "external outcomes differ by repeat")
    _require(run_manifest["two_command_traces_identical"] is True, "external traces differ by repeat")
    _require(EXTERNAL_FREEZE_LABEL in done and "Status: **COMPLETE**" in done, "done marker drifted")
    _require(set(run_manifest["result_files_sha256"]) == EXPECTED_RESULT_FILES, "result manifest drifted")
    for filename, expected in run_manifest["result_files_sha256"].items():
        _require(_sha256(EXTERNAL / filename) == expected, f"external result hash drifted: {filename}")

    workflows = _read_csv(EXTERNAL / "workflow_ledger.csv")
    commands = _read_csv(EXTERNAL / "command_ledger.csv")
    _require(len(workflows) == 404, "external workflow ledger must contain 404 rows")
    _require(len(commands) == 1444, "external command ledger must contain 1,444 rows")
    analytic_ids = {item["mutant_id"] for item in analytic}
    control_ids = {item["mutant_id"] for item in controls}
    observed_keys = {(row["replay"], row["mutant_id"], row["bypassed_stage"]) for row in workflows}
    _require(observed_keys == _expected_workflow_keys(analytic_ids, control_ids), "external matrix is incomplete")
    _require(len({row["cell_id"] for row in workflows}) == 404, "external cell ids are not unique")
    catalog_by_id = {item["mutant_id"]: item for item in catalog["mutants"]}
    for row in workflows:
        item = catalog_by_id[row["mutant_id"]]
        _require(row["stratum"] == item["stratum"], f"stratum drifted: {row['cell_id']}")
        _require(row["mutated_source_sha256"] == item["mutated_source_sha256"], "source hash drifted")
        expected_cell = f"r{row['replay']}-{row['mutant_id']}-bypass-{row['bypassed_stage']}"
        _require(row["cell_id"] == expected_cell, f"cell id drifted: {row['cell_id']}")
    for replay in ("1", "2"):
        rows = [row for row in workflows if row["replay"] == replay]
        _require(rows[0]["mutant_id"] == "CTRL-01" and rows[-1]["mutant_id"] == "CTRL-02", "controls drifted")
    _require(not any(row["outcome"] == "infra_error" for row in workflows), "workflow infra error found")
    _require(not any(row["classification"] == "infra_error" for row in commands), "command infra error found")

    _verify_command_semantics(commands)

    commands_by_cell: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in commands:
        commands_by_cell[row["cell_id"]].append(row)
    _require(set(commands_by_cell) == {row["cell_id"] for row in workflows}, "command cells drifted")
    workflow_by_cell = {row["cell_id"]: row for row in workflows}
    for cell_id, cell_commands in commands_by_cell.items():
        workflow = workflow_by_cell[cell_id]
        active = [stage for stage in EXTERNAL_STAGES if stage != workflow["bypassed_stage"]]
        if workflow["outcome"] == "accepted":
            expected_stages = ["source_probe", *active]
            expected_classes = ["pass"] * len(expected_stages)
        else:
            _require(workflow["destination"] in active, f"invalid rejection destination: {cell_id}")
            end = active.index(workflow["destination"])
            expected_stages = ["source_probe", *active[: end + 1]]
            expected_classes = ["pass"] * (len(expected_stages) - 1) + ["controlled_rejection"]
        _require([row["stage"] for row in cell_commands] == expected_stages, f"command path drifted: {cell_id}")
        _require(
            [row["classification"] for row in cell_commands] == expected_classes,
            f"command classification drifted: {cell_id}",
        )
    pytest_rows = [row for row in commands if row["stage"] == "pytest"]
    _require(len(pytest_rows) == 188, "pytest invocation count drifted")
    _require(
        all(row["collected_tests"] == "6405" and row["returncode"] in {"0", "1"} for row in pytest_rows),
        "pytest collection or return code drifted",
    )

    workflow_fields = (
        "mutant_id",
        "stratum",
        "intended_stage",
        "bypassed_stage",
        "outcome",
        "destination",
        "mutated_source_sha256",
    )
    replay_workflows = [
        Counter(tuple(row[field] for field in workflow_fields) for row in workflows if row["replay"] == replay)
        for replay in ("1", "2")
    ]
    _require(replay_workflows[0] == replay_workflows[1], "external workflow repeats differ")
    command_fields = tuple(field for field in commands[0] if field not in {"replay", "cell_id"})
    replay_commands = [
        Counter(tuple(row[field] for field in command_fields) for row in commands if row["replay"] == replay)
        for replay in ("1", "2")
    ]
    _require(replay_commands[0] == replay_commands[1], "external command repeats differ")

    replay_one = [row for row in workflows if row["replay"] == "1" and row["stratum"] == "primary"]
    baseline = {row["mutant_id"]: row for row in replay_one if row["bypassed_stage"] == "none"}
    _require(len(baseline) == 24, "external baseline must contain 24 primary mutants")
    _require(Counter(row["destination"] for row in baseline.values()) == EXPECTED_EXTERNAL_BASELINE, "baseline drifted")
    by_key = {(row["mutant_id"], row["bypassed_stage"]): row for row in replay_one}
    family_by_id = {item["mutant_id"]: item["operator_family"] for item in primary}
    family_observations: Counter[tuple[str, str, str]] = Counter()
    observed_profiles: dict[str, tuple[int, int, int, Counter[str]]] = {}
    observed_transitions: Counter[tuple[str, str]] = Counter()
    for mutant_id, row in baseline.items():
        stage = row["destination"]
        destination = "accepted" if stage == "accepted" else by_key[(mutant_id, stage)]["destination"]
        family_observations[(family_by_id[mutant_id], stage, destination)] += 1
    _require(family_observations == EXPECTED_EXTERNAL_FAMILIES, "external family fates drifted")
    for stage, expected in EXPECTED_EXTERNAL_FATES.items():
        first_hits = [row for row in baseline.values() if row["destination"] == stage]
        scoped = [by_key[(row["mutant_id"], stage)] for row in first_hits]
        profile = (
            len(first_hits),
            sum(row["outcome"] == "accepted" for row in scoped),
            sum(row["outcome"] == "controlled_rejection" for row in scoped),
            Counter(row["destination"] for row in scoped),
        )
        observed_profiles[stage] = profile
        observed_transitions.update((stage, row["destination"]) for row in scoped)
        _require(profile == expected, f"external fate profile drifted for {stage}")
        _require(profile[0] == profile[1] + profile[2], f"external fates do not close for {stage}")

    stage_rows = _read_csv(EXTERNAL / "stage_summary.csv")
    stage_summary = {
        row["stage"]: (
            int(row["first_hits"]),
            int(row["newly_accepted"]),
            int(row["later_rejected"]),
            row["downstream_exceptions"],
        )
        for row in stage_rows
    }
    expected_stage_summary = {
        stage: (profile[0], profile[1], profile[2], "N/A") for stage, profile in observed_profiles.items()
    }
    _require(stage_summary == expected_stage_summary, "external stage summary drifted")
    transition_rows = _read_csv(EXTERNAL / "transition_matrix.csv")
    transition_summary = Counter(
        {(row["removed_stage"], row["destination"]): int(row["count"]) for row in transition_rows}
    )
    _require(transition_summary == observed_transitions, "external transition summary drifted")
    calibration = _read_csv(EXTERNAL / "calibration_matrix.csv")
    calibration_summary = Counter(
        {(row["intended_stage"], row["observed_destination"]): int(row["count"]) for row in calibration}
    )
    _require(
        calibration_summary == Counter({(stage, stage): 4 for stage in EXTERNAL_STAGES}),
        "external calibration drifted",
    )
    _require(str(summary["exception_outcome"]).startswith("not available"), "external exception outcome drifted")
    return 52


def verify_report() -> int:
    text = REPORT.read_text(encoding="utf-8")
    normalized = re.sub(r"\s+", " ", text)
    required = (
        "What First-Failure Counts Miss: Admission and Downstream Fate",
        "\\author{Weicheng Xue",
        "This document is an open technical note and has not undergone peer review.",
        "365 input mutations",
        "261 of 344 refusals",
        "250 are rejected later",
        "11 reach downstream exceptions",
        "selected under a recorded outcome-blind rule",
        "361 alter this post-execution set",
        "Four lifecycle probes",
        "146 directed probes and 219 generic mutations",
        "6,405 collected pytest items",
        "4 layout, 4 parameter-reference, 4 annotation, 6 predicate, and 6 scalar-boundary edits",
        "Sixteen directed mutants calibrated routing",
        "Two controls bracketed each of two repeats",
        "344 variants are rejected and 21 are accepted",
        "261, 20, 36, 18, and 9",
        "317 first rejections",
        "all 27",
        "(C_1,S_1,X_1)=(0,250,11)",
        "\\mathbf{b}_1=(0,95.8\\%,4.2\\%)",
        "246 move to component validation",
        "four to preflight",
        "six first hits to binding and 14 to preflight",
        "all 36 to preflight",
        "Ruff format & 4 & 4 & 0",
        "Ruff lint & 0 & 0 & 0",
        "all four annotation edits passed",
        "both parameter-reference edits failed at pytest",
        "mypy & 6 & 4 & 2 & pytest (2)",
        "pytest & 9 & 9 & 0",
        "The two repeats agreed",
        "Five primary mutants passed the chain",
        "$X_i$ is unavailable",
        "selector implementation is not included",
        "pytest reporting timeout",
        "decisions about hardening or removing a stage",
    )
    for marker in required:
        _require(re.sub(r"\s+", " ", marker) in normalized, f"technical-note marker missing: {marker}")
    forbidden = (
        "Anonymous " + "author(s)",
        "Information and Software " + "Technology",
        "els" + "article",
    )
    for marker in forbidden:
        _require(marker not in text, f"submission-only marker remains in technical note: {marker}")
    _require(_sha256(FIGURE) == FIGURE_SHA256, "technical-note figure hash drifted")
    _require(_sha256(FIGURE_PNG) == FIGURE_PNG_SHA256, "technical-note figure PNG hash drifted")
    _require(REPORT_PDF.is_file() and REPORT_PDF.stat().st_size > 0, "technical-note PDF is missing")

    bibliography = BIBLIOGRAPHY.read_text(encoding="utf-8")
    keys = set(re.findall(r"@\w+\s*\{\s*([^,\s]+)", bibliography))
    _require(keys == set(EXPECTED_REFERENCES), "bibliography keys drifted")
    dois = {value.lower() for value in re.findall(r"\bdoi\s*=\s*\{([^}]+)\}", bibliography, re.I)}
    _require(dois == set(EXPECTED_REFERENCES.values()), "bibliography DOI set drifted")
    cited: set[str] = set()
    for group in re.findall(r"\\cite\{([^}]+)\}", text):
        cited.update(key.strip() for key in group.split(","))
    _require(cited == keys, "citation and bibliography keys differ")
    return len(required) + len(forbidden) + 6


def verify_rendered_figure() -> int:
    script = ROOT / "scripts" / "render_gate_attribution.py"
    with tempfile.TemporaryDirectory(prefix="validator_fate_figure_") as temporary:
        output = Path(temporary) / "output"
        mpl_config = Path(temporary) / "mpl-config"
        environment = dict(os.environ)
        environment.update(
            {
                "MPLCONFIGDIR": str(mpl_config),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONHASHSEED": "0",
            }
        )
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--source-matrix",
                str(ARTIFACT / "e1_source_matrix.csv"),
                "--leave-one-out",
                str(ARTIFACT / "e1_leave_one_out.csv"),
                "--output-dir",
                str(output),
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=120,
        )
        _require(result.returncode == 0, f"figure rebuild failed:\n{result.stdout}{result.stderr}")
        rebuilt = output / "attribution_gap.pdf"
        rebuilt_png = output / "attribution_gap.png"
        _require(rebuilt.is_file(), "figure rebuild did not produce a PDF")
        _require(rebuilt_png.is_file(), "figure rebuild did not produce a PNG")
        _require(_sha256(rebuilt) == _sha256(FIGURE), "rebuilt PDF figure differs from released figure")
        _require(_sha256(rebuilt_png) == _sha256(FIGURE_PNG), "rebuilt PNG figure differs from released figure")
    return 5


def verify_built_report() -> int:
    script = ROOT / "scripts" / "build_report.py"
    with tempfile.TemporaryDirectory(prefix="validator_fate_report_") as temporary:
        report = Path(temporary) / "report"
        figures = report / "figures"
        figures.mkdir(parents=True)
        shutil.copy2(REPORT, report / REPORT.name)
        shutil.copy2(BIBLIOGRAPHY, report / BIBLIOGRAPHY.name)
        shutil.copy2(FIGURE, figures / FIGURE.name)
        environment = dict(os.environ)
        environment.update({"PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"})
        result = subprocess.run(
            [sys.executable, str(script), "--report-dir", str(report)],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=180,
        )
        _require(result.returncode == 0, f"technical-note rebuild failed:\n{result.stdout}{result.stderr}")
        rebuilt = report / REPORT_PDF.name
        _require(rebuilt.is_file(), "technical-note rebuild did not produce a PDF")
        _require(_sha256(rebuilt) == _sha256(REPORT_PDF), "rebuilt technical note differs from released PDF")
    return 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--render-figure",
        action="store_true",
        help="also rebuild the PDF figure; requires the pinned figure environment",
    )
    parser.add_argument(
        "--build-report",
        action="store_true",
        help="also rebuild the technical-note PDF; requires pdflatex and biber",
    )
    args = parser.parse_args(argv)
    checks = verify_pack_manifest() + verify_artifact_case() + verify_external_case() + verify_report()
    if args.render_figure:
        checks += verify_rendered_figure()
    if args.build_report:
        checks += verify_built_report()
    print(f"research artifact verification passed: {checks} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
