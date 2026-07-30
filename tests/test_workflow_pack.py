import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("workflow_pack", ROOT / "scripts/verify_workflow_pack.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
VALID = json.loads((ROOT / "tests/fixtures/workflow-pack/cases.json").read_text())["valid"]


class WorkflowPackTest(unittest.TestCase):
    def changed(self, field, value):
        result = copy.deepcopy(VALID)
        result[field] = value
        return result

    def test_valid_catalog_entry(self):
        self.assertEqual([], MODULE.validate(copy.deepcopy(VALID)))

    def test_activation_and_governance_are_closed(self):
        self.assertEqual(["WORKFLOW_PACK_ACTIVATION_INVALID"], MODULE.validate(self.changed("activation", "automatic")))
        self.assertEqual(["WORKFLOW_PACK_GOVERNANCE_INVALID"], MODULE.validate(self.changed("governance_mode", [])))

    def test_content_and_effects_are_safe(self):
        self.assertEqual(["WORKFLOW_PACK_CONTENT_INVALID"], MODULE.validate(self.changed("inputs", [{}])))
        self.assertEqual(["WORKFLOW_PACK_EFFECT_FORBIDDEN"], MODULE.validate(self.changed("allowed_effects", ["network"])))

    def test_authority_cannot_be_declared(self):
        self.assertEqual(["WORKFLOW_PACK_AUTHORITY_ESCALATION"], MODULE.validate(self.changed("client_authority_owner", "agent")))
        self.assertEqual(["WORKFLOW_PACK_AUTHORITY_ESCALATION"], MODULE.validate(self.changed("execution_authorized", True)))
