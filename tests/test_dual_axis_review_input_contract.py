import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dual_axis", ROOT / "scripts/verify_dual_axis_review_input.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
VALID = json.loads((ROOT / "tests/fixtures/dual-axis-review-input/cases.json").read_text(encoding="utf-8"))["valid"]


class DualAxisReviewInputContractTest(unittest.TestCase):
    def changed(self, path, value):
        result = copy.deepcopy(VALID)
        current = result
        for key in path[:-1]:
            current = current[key]
        current[path[-1]] = value
        return result

    def test_valid_input_keeps_both_axes_separate(self):
        self.assertEqual([], MODULE.validate(copy.deepcopy(VALID)))

    def test_identity_and_request_binding_fail_closed(self):
        self.assertEqual(["DUAL_AXIS_IDENTITY_INVALID"], MODULE.validate(self.changed(["input_id"], "bad")))
        self.assertEqual(["DUAL_AXIS_REQUEST_BINDING_INVALID"], MODULE.validate(self.changed(["target_candidate_commit"], "bad")))

    def test_both_axes_and_checks_are_required(self):
        self.assertEqual(["DUAL_AXIS_AXIS_SET_INVALID"], MODULE.validate(self.changed(["axes"], {"spec": VALID["axes"]["spec"]})))
        self.assertEqual(["DUAL_AXIS_CHECK_SET_INVALID"], MODULE.validate(self.changed(["requested_checks"], ["spec"])))

    def test_axis_source_cannot_claim_a_missing_source(self):
        invalid = self.changed(["axes", "spec", "source", "kind"], "none")
        self.assertEqual(["DUAL_AXIS_SOURCE_INVALID"], MODULE.validate(invalid))
        invalid = self.changed(["axes", "standards", "availability"], "provided")
        self.assertEqual(["DUAL_AXIS_SOURCE_INVALID"], MODULE.validate(invalid))

    def test_axis_enums_are_type_safe_and_unavailable_has_no_content_hash(self):
        self.assertEqual(["DUAL_AXIS_SOURCE_INVALID"], MODULE.validate(self.changed(["axes", "spec", "availability"], [])))
        self.assertEqual(["DUAL_AXIS_SOURCE_INVALID"], MODULE.validate(self.changed(["axes", "spec", "source", "kind"], {})))
        unavailable_hash = copy.deepcopy(VALID)
        unavailable_hash["axes"]["standards"]["source"]["bytes_sha256"] = "c" * 64
        self.assertEqual(["DUAL_AXIS_SOURCE_INVALID"], MODULE.validate(unavailable_hash))

    def test_effects_and_authority_are_not_granted(self):
        self.assertEqual(["DUAL_AXIS_EFFECT_FORBIDDEN"], MODULE.validate(self.changed(["allowed_effects"], ["network"])))
        self.assertEqual(["DUAL_AXIS_AUTHORITY_ESCALATION"], MODULE.validate(self.changed(["next_stage_authorized"], True)))

    def test_unknown_fields_are_rejected(self):
        invalid = copy.deepcopy(VALID)
        invalid["automatic_subagents"] = True
        self.assertEqual(["DUAL_AXIS_FIELD_SET_INVALID"], MODULE.validate(invalid))


if __name__ == "__main__":
    unittest.main()
