from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_external_architecture_lens", ROOT / "scripts" / "verify_external_architecture_lens.py")
assert spec and spec.loader
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
CASES = json.loads((ROOT / "tests" / "fixtures" / "external-architecture-lens" / "cases.json").read_text(encoding="utf-8"))


class ExternalArchitectureLensContractTests(unittest.TestCase):
    def scenario(self):
        return copy.deepcopy(CASES["artifacts"]), copy.deepcopy(CASES["review"])

    def test_schemas_parse_and_valid_fixture_passes(self):
        for name in ("external-architecture-artifact.schema.json", "external-architecture-lens-review.schema.json"):
            self.assertIsInstance(json.loads((ROOT / "contracts" / name).read_text(encoding="utf-8")), dict)
        artifacts, review = self.scenario()
        self.assertEqual([], checker.validate_artifacts(artifacts))
        self.assertEqual([], checker.validate_review(review, artifacts))

    def test_schema_shape_rejects_fact_and_requires_inference_evidence(self):
        schema = json.loads((ROOT / "contracts" / "external-architecture-lens-review.schema.json").read_text(encoding="utf-8"))
        finding = schema["$defs"]["finding"]
        self.assertEqual(["INFERENCE", "UNKNOWN"], finding["properties"]["classification"]["enum"])
        self.assertEqual(1, finding["allOf"][0]["then"]["properties"]["evidence_refs"]["minItems"])

    def test_artifact_identity_path_and_authority_fail_closed(self):
        artifacts, _ = self.scenario()
        artifacts[0]["commit"] = "bad"
        self.assertIn("ARTIFACT_IDENTITY_INVALID", checker.validate_artifacts(artifacts))
        artifacts, _ = self.scenario()
        artifacts[0]["evidence_items"][0]["path"] = "../escape"
        self.assertIn("ARTIFACT_EVIDENCE_ITEM_INVALID", checker.validate_artifacts(artifacts))
        artifacts, _ = self.scenario()
        artifacts[0]["next_stage_authorized"] = True
        self.assertIn("ARTIFACT_AUTHORITY_ESCALATION", checker.validate_artifacts(artifacts))

    def test_review_binds_artifacts_and_evidence(self):
        artifacts, review = self.scenario()
        review["artifact_ids"] = ["EXT-ART-ECC-001"]
        self.assertEqual(["REVIEW_ARTIFACT_BINDING_INVALID"], checker.validate_review(review, artifacts))
        artifacts, review = self.scenario()
        review["findings"][0]["evidence_refs"] = ["EXT-ART-ECC-001:EXT-EV-MISSING"]
        self.assertIn("REVIEW_FINDING_EVIDENCE_INVALID", checker.validate_review(review, artifacts))
        artifacts, review = self.scenario()
        artifacts[0]["evidence_items"][0]["provenance"] = "INFERRED"
        review["findings"][0]["classification"] = "FACT"
        self.assertIn("REVIEW_FACT_PROVENANCE_INVALID", checker.validate_review(review, artifacts))
        artifacts, review = self.scenario()
        review["findings"][0]["classification"] = "FACT"
        self.assertIn("REVIEW_FACT_UNVERIFIED", checker.validate_review(review, artifacts))
        artifacts, review = self.scenario()
        review["findings"][0]["evidence_refs"] = []
        self.assertIn("REVIEW_FINDING_EVIDENCE_INVALID", checker.validate_review(review, artifacts))

    def test_execution_hooks_network_and_lhe_mutation_are_forbidden(self):
        artifacts, review = self.scenario()
        review["external_execution_required"] = True
        self.assertEqual(["REVIEW_EFFECT_ESCALATION"], checker.validate_review(review, artifacts))
        artifacts, review = self.scenario()
        review["network_behavior"] = "allowed"
        self.assertEqual(["REVIEW_EFFECT_ESCALATION"], checker.validate_review(review, artifacts))
        artifacts, review = self.scenario()
        review["findings"][0]["recommended_target"] = "lhe_proposal_only"
        self.assertIn("REVIEW_LHE_MUTATION_FORBIDDEN", checker.validate_review(review, artifacts))

    def test_malformed_list_values_and_cli_input_fail_closed(self):
        artifacts, review = self.scenario()
        review["artifact_ids"] = [{}]
        self.assertEqual(["REVIEW_IDENTITY_INVALID"], checker.validate_review(review, artifacts))
        artifacts, review = self.scenario()
        review["findings"] = [{}]
        self.assertIn("REVIEW_FINDING_INVALID", checker.validate_review(review, artifacts))
        artifacts, review = self.scenario()
        review["findings"][0]["disposition"] = {}
        self.assertIn("REVIEW_FINDING_INVALID", checker.validate_review(review, artifacts))
        with tempfile.TemporaryDirectory() as temporary:
            bad = Path(temporary) / "bad.json"
            bad.write_text("{", encoding="utf-8")
            result = subprocess.run([sys.executable, str(ROOT / "scripts" / "verify_external_architecture_lens.py"), "--artifacts", str(bad), "--review", str(bad)], check=False, capture_output=True, text=True)
            self.assertEqual(1, result.returncode)
            self.assertEqual({"reasons": ["INPUT_DOCUMENT_INVALID"], "status": "FAIL"}, json.loads(result.stdout))


if __name__ == "__main__":
    unittest.main()
