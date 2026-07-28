from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
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
        "review_contract_bytes_sha256": CONTRACT_SHA,
        "reviewer_kit_commit": COMMIT_A, "reviewer_kit_tree": TREE_A,
        "requested_checks": ["identity", "evidence"],
    }


def actual(paths: list[str] | None = None) -> dict:
    return {
        "base_commit": COMMIT_A, "base_tree": TREE_A,
        "candidate_commit": COMMIT_B, "candidate_tree": TREE_B,
        "reviewer_kit_commit": COMMIT_A, "reviewer_kit_tree": TREE_A,
        "review_contract_bytes_sha256": CONTRACT_SHA,
        "changed_paths": request()["changed_paths"] if paths is None else paths,
    }


def manifest() -> dict:
    value = {
        "schema_version": "1.0.0", "review_id": "IRR-001",
        "reviewer_kit_commit": COMMIT_A, "reviewer_kit_tree": TREE_A,
        "candidate_commit": COMMIT_B, "candidate_tree": TREE_B,
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
        "verdict": "ACCEPT",
        "findings": [{"finding_id": "FIND-001", "severity": "P3", "epistemic_status": "FACT", "evidence_ids": ["EVID-001"], "summary": "Synthetic success."}],
        "limitations": ["synthetic fixture only"],
        "human_disposition": "pending", "promotion_state": "not-promoted", "next_stage_authorized": False,
    }
    value["review_request_sha256"] = canonical_hash(request())
    value["evidence_manifest_sha256"] = canonical_hash(manifest())
    return value


class ReviewerContractTests(unittest.TestCase):
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
        self.assertEqual([], evidence.validate_runtime_binding(request(), runtime, CONTRACT_SHA))
        changed = dict(runtime)
        changed["reviewer_kit_tree"] = TREE_B
        self.assertIn("RUNTIME_REVIEWER_KIT_TREE_MISMATCH", evidence.validate_runtime_binding(request(), changed, CONTRACT_SHA))
        self.assertIn("REVIEW_CONTRACT_HASH_MISMATCH", evidence.validate_runtime_binding(request(), runtime, "f" * 64))
        self.assertEqual(["REVIEWER_KIT_RUNTIME_IDENTITY_UNAVAILABLE"], evidence.validate_runtime_binding(request(), None, CONTRACT_SHA))

    def test_manifest_requires_valid_request_and_same_candidate(self):
        invalid_request = {"candidate": {"commit": COMMIT_B, "tree": TREE_B}}
        candidate = manifest()
        candidate["review_request_sha256"] = canonical_hash(invalid_request)
        self.assertEqual(["REVIEW_REQUEST_INVALID"], self.validate_manifest(candidate, invalid_request))
        candidate = manifest()
        candidate["candidate_commit"] = COMMIT_A
        self.assertIn("CANDIDATE_COMMIT_MISMATCH", self.validate_manifest(candidate))

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
