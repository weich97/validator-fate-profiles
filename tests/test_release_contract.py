"""Regression tests for the public evidence-release contract."""

from __future__ import annotations

import csv
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import verify
from scripts import build_release, check_release_hygiene


class EvidenceContractTests(unittest.TestCase):
    def test_manifest_and_claims(self) -> None:
        self.assertGreater(verify.verify_pack_manifest(), 100)
        self.assertGreater(verify.verify_artifact_case(), 0)
        self.assertGreater(verify.verify_external_case(), 0)
        self.assertGreater(verify.verify_report(), 0)

    def test_release_hygiene(self) -> None:
        self.assertGreater(check_release_hygiene._check_content(), 0)
        self.assertGreater(check_release_hygiene._check_report(), 0)
        self.assertGreater(check_release_hygiene._check_pdf_lineage(), 0)

    def test_artifact_case_rejects_broken_baseline_join(self) -> None:
        with tempfile.TemporaryDirectory(prefix="validator_fate_artifact_join_") as temporary:
            artifact = Path(temporary) / "artifact_case"
            shutil.copytree(verify.ARTIFACT, artifact)
            ledger = artifact / "e1_leave_one_out_ledger.csv"
            with ledger.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
                fieldnames = list(rows[0])
            rows[0]["variant_id"] = "VX999"
            with ledger.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            with (
                mock.patch.object(verify, "ARTIFACT", artifact),
                self.assertRaisesRegex(AssertionError, "baseline and bypass variant ids differ"),
            ):
                verify.verify_artifact_case()

    def test_external_command_semantics_reject_bad_return_code(self) -> None:
        commands = verify._read_csv(verify.EXTERNAL / "command_ledger.csv")
        rejecting = next(row.copy() for row in commands if row["classification"] == "controlled_rejection")
        rejecting["returncode"] = "0"
        with self.assertRaisesRegex(AssertionError, "wrong return code"):
            verify._verify_command_semantics([rejecting])

    def test_release_archive_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory(prefix="validator_fate_release_test_") as temporary:
            dist = Path(temporary)
            archive = dist / "release.zip"
            checksums = dist / "SHA256SUMS.txt"
            with (
                mock.patch.object(build_release, "DIST", dist),
                mock.patch.object(build_release, "ARCHIVE", archive),
                mock.patch.object(build_release, "CHECKSUMS", checksums),
            ):
                self.assertEqual(build_release.main(), 0)
                first = archive.read_bytes()
                self.assertEqual(build_release.main(), 0)
                self.assertEqual(first, archive.read_bytes())

            with zipfile.ZipFile(archive) as released:
                names = released.namelist()
                self.assertEqual(len(names), len(set(names)))
                self.assertTrue(all(name.startswith(f"{build_release.PREFIX}/") for name in names))
                self.assertTrue(all(".." not in Path(name).parts for name in names))
                extracted = dist / "tmp" / "fresh"
                released.extractall(extracted)

            relocated_root = extracted / build_release.PREFIX
            with mock.patch.object(check_release_hygiene, "ROOT", relocated_root):
                self.assertGreater(check_release_hygiene._check_content(), 0)
                self.assertGreater(check_release_hygiene._check_report(), 0)
                self.assertGreater(check_release_hygiene._check_pdf_lineage(), 0)

    def test_release_builder_rejects_stale_manifest(self) -> None:
        manifest = json.loads(build_release.MANIFEST.read_text(encoding="utf-8"))
        manifest["files"]["verify.py"]["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory(prefix="validator_fate_manifest_test_") as temporary:
            stale = Path(temporary) / "PACK_MANIFEST.json"
            stale.write_text(json.dumps(manifest), encoding="utf-8")
            with (
                mock.patch.object(build_release, "MANIFEST", stale),
                self.assertRaisesRegex(RuntimeError, "manifest payload drifted"),
            ):
                build_release.main()

    def test_release_builder_rejects_traversal_path(self) -> None:
        manifest = {
            "schema_version": 2,
            "name": "validator-fate-profiles",
            "version": "1.0.0",
            "files": {"../outside.txt": {"size": 0, "sha256": "0" * 64, "purpose": "invalid"}},
        }
        with tempfile.TemporaryDirectory(prefix="validator_fate_path_test_") as temporary:
            unsafe = Path(temporary) / "PACK_MANIFEST.json"
            unsafe.write_text(json.dumps(manifest), encoding="utf-8")
            with (
                mock.patch.object(build_release, "MANIFEST", unsafe),
                self.assertRaisesRegex(RuntimeError, "unsafe manifest path"),
            ):
                build_release.main()


if __name__ == "__main__":
    unittest.main()
