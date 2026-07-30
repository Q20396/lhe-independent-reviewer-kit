import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("tracer_map", ROOT / "scripts/verify_tracer_bullet_dependency_map.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
VALID = json.loads((ROOT / "tests/fixtures/tracer-bullet-dependency-map/cases.json").read_text(encoding="utf-8"))["valid"]


class TracerBulletDependencyMapContractTest(unittest.TestCase):
    def valid(self):
        return copy.deepcopy(VALID)

    def test_valid_static_map(self):
        self.assertEqual([], MODULE.validate(self.valid()))

    def test_identity_and_authority_are_closed(self):
        value = self.valid(); value["map_id"] = []
        self.assertEqual(["TRACER_BULLET_IDENTITY_INVALID"], MODULE.validate(value))
        value = self.valid(); value["next_stage_authorized"] = True
        self.assertEqual(["TRACER_BULLET_AUTHORITY_ESCALATION"], MODULE.validate(value))

    def test_items_require_verifiable_deliverables_and_have_no_effects(self):
        value = self.valid(); value["items"][0]["acceptance_criteria"] = []
        self.assertEqual(["TRACER_BULLET_ITEM_CONTENT_INVALID"], MODULE.validate(value))
        value = self.valid(); value["items"][0]["allowed_effects"] = ["write"]
        self.assertEqual(["TRACER_BULLET_ITEM_AUTHORITY_ESCALATION"], MODULE.validate(value))

    def test_blockers_must_resolve_and_cannot_form_cycles(self):
        value = self.valid(); value["items"][1]["blocked_by"] = ["TBI-MISSING-001"]
        self.assertEqual(["TRACER_BULLET_BLOCKER_INVALID"], MODULE.validate(value))
        value = self.valid(); value["items"][0]["blocked_by"] = ["TBI-REVIEW-001"]
        self.assertEqual(["TRACER_BULLET_CYCLE_FORBIDDEN"], MODULE.validate(value))

    def test_duplicate_ids_and_unknown_fields_fail_closed(self):
        value = self.valid(); value["items"][1]["item_id"] = "TBI-SPEC-001"
        self.assertEqual(["TRACER_BULLET_DUPLICATE_ITEM_ID"], MODULE.validate(value))
        value = self.valid(); value["items"][0]["auto_create_issue"] = True
        self.assertEqual(["TRACER_BULLET_ITEM_FIELD_SET_INVALID"], MODULE.validate(value))

    def test_deep_acyclic_and_cyclic_maps_do_not_depend_on_python_recursion(self):
        acyclic = self.valid()
        acyclic["items"] = []
        for index in range(1100):
            item_id = f"TBI-N-{index}"
            acyclic["items"].append({
                "item_id": item_id, "title": item_id, "deliverable": item_id,
                "acceptance_criteria": [item_id],
                "blocked_by": [] if index == 0 else [f"TBI-N-{index - 1}"],
                "status": "proposed", "evidence_refs": [f"EVID-N-{index}"],
                "allowed_effects": [], "execution_authorized": False,
            })
        self.assertEqual([], MODULE.validate(acyclic))
        acyclic["items"][0]["blocked_by"] = ["TBI-N-1099"]
        self.assertEqual(["TRACER_BULLET_CYCLE_FORBIDDEN"], MODULE.validate(acyclic))


if __name__ == "__main__":
    unittest.main()
