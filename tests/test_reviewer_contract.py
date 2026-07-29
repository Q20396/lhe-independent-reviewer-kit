from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


identity = load_module("verify_candidate_identity", ROOT / "scripts" / "verify_candidate_identity.py")
evidence = load_module("verify_evidence_manifest", ROOT / "scripts" / "verify_evidence_manifest.py")

COMMIT_A = "a" * 40
TREE_A = "b" * 40
COMMIT_B = "c" * 40
TREE_B = "d" * 40
CONTRACT_SHA = "e" * 64
DELTA_SHA = "f" * 64
ARTIFACT_BYTES = b"synthetic raw command output\n"
ARTIFACT_SHA = hashlib.sha256(ARTIFACT_BYTES).hexdigest()


def canonical_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def request() -> dict:
    paths = ["contracts/review-request.schema.json", "scripts/verify_candidate_identity.py"]
    return {
        "schema_version": "1.0.0", "review_id": "IRR-001", "repository_locator": "example/repository",
        "base": {"commit": COMMIT_A, "tree": TREE_A},
        "candidate": {"commit": COMMIT_B, "tree": TREE_B},
        "changed_paths": paths, "changed_paths_sha256": canonical_hash(sorted(paths)),
        "candidate_object_delta_sha256": DELTA_SHA,
        "review_contract_bytes_sha256": CONTRACT_SHA,
        "reviewer_kit_commit": COMMIT_A, "reviewer_kit_tree": TREE_A,
        "requested_checks": ["identity", "evidence"],
    }


def actual(paths: list[str] | None = None) -> dict:
    changed_paths = request()["changed_paths"] if paths is None else paths
    return {
        "base_commit": COMMIT_A, "base_tree": TREE_A,
        "candidate_commit": COMMIT_B, "candidate_tree": TREE_B,
        "reviewer_kit_commit": COMMIT_A, "reviewer_kit_tree": TREE_A,
        "review_contract_bytes_sha256": CONTRACT_SHA,
        "candidate_object_delta_sha256": DELTA_SHA,
        "changed_paths": changed_paths,
        "changed_paths_sha256": canonical_hash(sorted(changed_paths)),
    }


def manifest() -> dict:
    value = {
        "schema_version": "1.0.0", "review_id": "IRR-001",
        "reviewer_kit_commit": COMMIT_A, "reviewer_kit_tree": TREE_A,
        "candidate_commit": COMMIT_B, "candidate_tree": TREE_B,
        "candidate_object_delta_sha256": DELTA_SHA,
        "evidence": [{
            "evidence_id": "EVID-001", "kind": "command", "claim_direction": "supports",
            "raw_artifact_locator": "artifacts/evidence.txt", "raw_artifact_sha256": ARTIFACT_SHA,
            "limitations": ["synthetic fixture only"],
        }],
    }
    value["review_request_sha256"] = canonical_hash(request())
    return value


def verdict() -> dict:
    value = {
        "schema_version": "1.0.0", "review_id": "IRR-001",
        "reviewer_kit_commit": COMMIT_A, "reviewer_kit_tree": TREE_A,
        "candidate_commit": COMMIT_B, "candidate_tree": TREE_B,
        "candidate_object_delta_sha256": DELTA_SHA,
        "verdict": "ACCEPT",
        "findings": [{"finding_id": "FIND-001", "severity": "P3", "epistemic_status": "FACT", "evidence_ids": ["EVID-001"], "summary": "Synthetic success."}],
        "limitations": ["synthetic fixture only"],
        "human_disposition": "pending", "promotion_state": "not-promoted", "next_stage_authorized": False,
    }
    value["review_request_sha256"] = canonical_hash(request())
    value["evidence_manifest_sha256"] = canonical_hash(manifest())
    return value


class ReviewerContractTests(unittest.TestCase):
    def git(self, root: Path, *arguments: str) -> str:
        return subprocess.run(["git", "-C", str(root), *arguments], check=True, capture_output=True, text=True).stdout.strip()

    def target_repository(self, directory_name: str = "target"):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name) / directory_name
        subprocess.run(["git", "init", str(root)], check=True, capture_output=True, text=True)
        self.git(root, "config", "user.name", "Reviewer Kit Test")
        self.git(root, "config", "user.email", "reviewer-kit@example.invalid")
        (root / "tracked.txt").write_text("base\n", encoding="utf-8")
        self.git(root, "add", "tracked.txt")
        self.git(root, "commit", "-m", "base")
        base = self.git(root, "rev-parse", "HEAD")
        (root / "tracked.txt").write_text("candidate\n", encoding="utf-8")
        self.git(root, "add", "tracked.txt")
        self.git(root, "commit", "-m", "candidate")
        return temporary, root, base

    def artifact_root(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / "artifacts").mkdir()
        (root / "artifacts" / "evidence.txt").write_bytes(ARTIFACT_BYTES)
        return temporary, root

    def validate_manifest(self, candidate: dict | None = None, review: dict | None = None):
        temporary, root = self.artifact_root()
        try:
            return evidence.validate(candidate or manifest(), review or request(), root)
        finally:
            temporary.cleanup()

    def test_all_contract_schemas_are_json(self):
        for path in (ROOT / "contracts").glob("*.json"):
            self.assertIsInstance(json.loads(path.read_text()), dict)

    def test_valid_identity_passes(self):
        self.assertEqual([], identity.validate(request(), actual()))

    def test_target_identity_is_derived_from_detached_head_without_target_writes(self):
        temporary, target, base = self.target_repository()
        try:
            index = target / ".git" / "index"
            before = index.read_bytes()
            self.git(target, "checkout", "--detach")
            derived, reasons = identity.derive_target_identity(target, base, ROOT)
            self.assertEqual([], reasons)
            self.assertIsNotNone(derived)
            assert derived is not None
            self.assertEqual(self.git(target, "rev-parse", "HEAD"), derived["candidate_commit"])
            self.assertEqual(["tracked.txt"], derived["changed_paths"])
            self.assertEqual(before, index.read_bytes())
            again, repeat_reasons = identity.derive_target_identity(target, base, ROOT)
            self.assertEqual([], repeat_reasons)
            self.assertEqual(derived, again)
        finally:
            temporary.cleanup()

    def test_target_identity_accepts_a_utf8_worktree_root(self):
        temporary, target, base = self.target_repository("目标-checkout")
        try:
            derived, reasons = identity.derive_target_identity(target, base, ROOT)
            self.assertEqual([], reasons)
            self.assertIsNotNone(derived)
            self.assertEqual(["tracked.txt"], derived["changed_paths"])
        finally:
            temporary.cleanup()

    def test_target_identity_rejects_non_commit_and_unsupported_changed_path(self):
        temporary, target, base = self.target_repository()
        try:
            self.git(target, "tag", "-a", "base-tag", "-m", "tag", base)
            tag_object = self.git(target, "rev-parse", "base-tag")
            _, reasons = identity.derive_target_identity(target, tag_object, ROOT)
            self.assertEqual(["BASE_COMMIT_INVALID"], reasons)
            (target / "bad\nname.txt").write_text("unsupported\n", encoding="utf-8")
            self.git(target, "add", "bad\nname.txt")
            self.git(target, "commit", "-m", "unsupported path")
            _, reasons = identity.derive_target_identity(target, base, ROOT)
            self.assertEqual(["TARGET_OBJECT_DELTA_INVALID"], reasons)
        finally:
            temporary.cleanup()

    def test_target_identity_rejects_a_base_outside_target_history(self):
        temporary, target, base = self.target_repository()
        try:
            self.git(target, "checkout", "--orphan", "unrelated")
            self.git(target, "rm", "-rf", ".")
            (target / "unrelated.txt").write_text("unrelated\n", encoding="utf-8")
            self.git(target, "add", "unrelated.txt")
            self.git(target, "commit", "-m", "unrelated")
            unrelated = self.git(target, "rev-parse", "HEAD")
            self.git(target, "checkout", "--detach", base)
            _, reasons = identity.derive_target_identity(target, unrelated, ROOT)
            self.assertEqual(["BASE_NOT_ANCESTOR"], reasons)
        finally:
            temporary.cleanup()

    def test_target_identity_rejects_same_reviewer_repository(self):
        _, reasons = identity.derive_target_identity(ROOT, COMMIT_A, ROOT)
        self.assertEqual(["TARGET_REPOSITORY_NOT_INDEPENDENT"], reasons)

    def test_identity_drift_and_malformed_actual_are_rejected(self):
        changed = actual()
        changed["candidate_commit"] = COMMIT_A
        self.assertIn("CANDIDATE_COMMIT_MISMATCH", identity.validate(request(), changed))
        self.assertEqual(["ACTUAL_IDENTITY_INVALID"], identity.validate(request(), {}))

    def test_actual_reviewer_identity_is_checked(self):
        changed = actual()
        changed["reviewer_kit_commit"] = "f" * 40
        self.assertIn("REVIEWER_KIT_COMMIT_MISMATCH", identity.validate(request(), changed))
        changed = actual()
        changed["reviewer_kit_tree"] = "f" * 40
        self.assertIn("REVIEWER_KIT_TREE_MISMATCH", identity.validate(request(), changed))

    def test_request_requires_full_contract_identity(self):
        candidate = request()
        del candidate["review_contract_bytes_sha256"]
        self.assertEqual(["REQUEST_FIELD_SET_INVALID"], identity.validate(candidate, actual()))

    def test_changed_path_drift_and_duplicates_are_rejected(self):
        self.assertIn("CHANGED_PATHS_MISMATCH", identity.validate(request(), actual(["unexpected.py"])))
        candidate = request()
        candidate["changed_paths"] = ["x", "x"]
        candidate["changed_paths_sha256"] = canonical_hash(sorted(candidate["changed_paths"]))
        self.assertIn("REQUEST_PATHS_DUPLICATE", identity.validate(candidate, actual(["x", "x"])))
        self.assertIn("ACTUAL_PATHS_DUPLICATE", identity.validate(request(), actual(["contracts/review-request.schema.json", "contracts/review-request.schema.json"])))

    def test_repository_escape_paths_are_rejected(self):
        for path in ("../escape.py", "/tmp/escape.py", "nested//file.py", "nested\\file.py"):
            candidate = request()
            candidate["changed_paths"] = [path]
            candidate["changed_paths_sha256"] = canonical_hash([path])
            self.assertIn("REQUEST_PATH_INVALID", identity.validate(candidate, actual([path])))

    def test_valid_evidence_manifest_passes_and_rehashes_artifact(self):
        self.assertEqual([], self.validate_manifest())

    def test_runtime_binding_requires_actual_kit_identity_and_contract_bytes(self):
        runtime = {"reviewer_kit_commit": COMMIT_A, "reviewer_kit_tree": TREE_A}
        target = {
            "base_commit": COMMIT_A, "base_tree": TREE_A,
            "candidate_commit": COMMIT_B, "candidate_tree": TREE_B,
            "changed_paths": request()["changed_paths"],
            "changed_paths_sha256": request()["changed_paths_sha256"],
            "candidate_object_delta_sha256": DELTA_SHA,
        }
        self.assertEqual([], evidence.validate_runtime_binding(request(), runtime, CONTRACT_SHA, target))
        changed = dict(runtime)
        changed["reviewer_kit_tree"] = TREE_B
        self.assertIn("RUNTIME_REVIEWER_KIT_TREE_MISMATCH", evidence.validate_runtime_binding(request(), changed, CONTRACT_SHA, target))
        self.assertIn("REVIEW_CONTRACT_HASH_MISMATCH", evidence.validate_runtime_binding(request(), runtime, "0" * 64, target))
        self.assertEqual(["REVIEWER_KIT_RUNTIME_IDENTITY_UNAVAILABLE"], evidence.validate_runtime_binding(request(), None, CONTRACT_SHA, target))

    def test_manifest_requires_valid_request_and_same_candidate(self):
        invalid_request = {"candidate": {"commit": COMMIT_B, "tree": TREE_B}}
        candidate = manifest()
        candidate["review_request_sha256"] = canonical_hash(invalid_request)
        self.assertEqual(["REVIEW_REQUEST_INVALID"], self.validate_manifest(candidate, invalid_request))
        candidate = manifest()
        candidate["candidate_commit"] = COMMIT_A
        self.assertIn("CANDIDATE_COMMIT_MISMATCH", self.validate_manifest(candidate))
        candidate = manifest()
        candidate["candidate_object_delta_sha256"] = "0" * 64
        self.assertIn("CANDIDATE_OBJECT_DELTA_SHA256_MISMATCH", self.validate_manifest(candidate))

    def test_manifest_rejects_builder_verdict_and_bad_evidence(self):
        candidate = manifest()
        candidate["builder_pass_receipt"] = {"verdict": "ACCEPT"}
        self.assertIn("MANIFEST_FIELD_SET_INVALID", self.validate_manifest(candidate))
        candidate = manifest()
        candidate["evidence"][0]["kind"] = {}
        candidate["evidence"][0]["limitations"] = [{}]
        reasons = self.validate_manifest(candidate)
        self.assertIn("EVIDENCE_KIND_INVALID", reasons)
        self.assertIn("LIMITATIONS_INVALID", reasons)

    def test_manifest_rejects_missing_or_forged_artifacts(self):
        candidate = manifest()
        candidate["evidence"][0]["raw_artifact_sha256"] = "f" * 64
        self.assertIn("RAW_ARTIFACT_HASH_MISMATCH", self.validate_manifest(candidate))
        candidate = manifest()
        candidate["evidence"][0]["raw_artifact_locator"] = "../escape.txt"
        self.assertIn("RAW_ARTIFACT_LOCATOR_INVALID", self.validate_manifest(candidate))

    def test_verdict_binds_request_manifest_kit_and_finding_evidence(self):
        temporary, root = self.artifact_root()
        try:
            self.assertEqual([], evidence.validate_verdict(verdict(), request(), manifest(), root))
            candidate = verdict()
            candidate["reviewer_kit_tree"] = "f" * 40
            self.assertIn("VERDICT_REVIEWER_KIT_TREE_MISMATCH", evidence.validate_verdict(candidate, request(), manifest(), root))
            candidate = verdict()
            candidate["candidate_object_delta_sha256"] = "0" * 64
            self.assertIn("VERDICT_CANDIDATE_OBJECT_DELTA_SHA256_MISMATCH", evidence.validate_verdict(candidate, request(), manifest(), root))
            candidate = verdict()
            candidate["findings"][0]["evidence_ids"] = ["EVID-404"]
            self.assertIn("FINDING_EVIDENCE_REFERENCE_INVALID", evidence.validate_verdict(candidate, request(), manifest(), root))
            candidate = verdict()
            candidate["findings"][0]["evidence_ids"] = [{"bad": "value"}]
            self.assertIn("FINDING_EVIDENCE_REFERENCE_INVALID", evidence.validate_verdict(candidate, request(), manifest(), root))
            candidate = verdict()
            candidate["limitations"] = [{"bad": "value"}]
            self.assertIn("VERDICT_LIMITATIONS_INVALID", evidence.validate_verdict(candidate, request(), manifest(), root))
            candidate = verdict()
            candidate["verdict"] = {"bad": "value"}
            self.assertIn("VERDICT_VALUE_INVALID", evidence.validate_verdict(candidate, request(), manifest(), root))
            self.assertEqual(["VERDICT_FIELD_SET_INVALID"], evidence.validate_verdict([], request(), manifest(), root))
        finally:
            temporary.cleanup()

    def test_verdict_schema_keeps_human_authority_pending(self):
        schema = json.loads((ROOT / "contracts" / "review-verdict.schema.json").read_text())
        properties = schema["properties"]
        self.assertEqual("pending", properties["human_disposition"]["const"])
        self.assertEqual("not-promoted", properties["promotion_state"]["const"])
        self.assertIs(False, properties["next_stage_authorized"]["const"])


if __name__ == "__main__":
    unittest.main()
