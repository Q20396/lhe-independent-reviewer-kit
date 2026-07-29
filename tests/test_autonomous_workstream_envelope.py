import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("workstream", ROOT / "scripts/verify_autonomous_workstream_envelope.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
VALID = json.loads((ROOT / "tests/fixtures/autonomous-workstream-envelope/cases.json").read_text())["valid"]


class AutonomousWorkstreamEnvelopeTest(unittest.TestCase):
    def mutated(self, path, value):
        result = copy.deepcopy(VALID)
        target = result
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        return result

    def test_valid_request_is_only_a_static_request(self):
        self.assertEqual([], MODULE.validate(copy.deepcopy(VALID)))

    def test_only_client_owns_authority(self):
        self.assertEqual(["CLIENT_AUTHORITY_ESCALATION"], MODULE.validate(self.mutated(["client_authority_owner"], "agent")))
        self.assertEqual(["CLIENT_AUTHORITY_ESCALATION"], MODULE.validate(self.mutated(["authorization_state"], "approved-for-one-run")))
        self.assertEqual(["CLIENT_AUTHORITY_ESCALATION"], MODULE.validate(self.mutated(["execution_authorized"], True)))

    def test_effects_and_writes_are_default_denied(self):
        self.assertEqual(["WORKSTREAM_EFFECTS_FORBIDDEN"], MODULE.validate(self.mutated(["effect_budget", "allowed_effects"], ["network"])))
        self.assertEqual(["WORKSTREAM_WRITE_SCOPE_FORBIDDEN"], MODULE.validate(self.mutated(["allowed_paths"], ["src/app.py"])))

    def test_budgets_and_outputs_are_closed(self):
        self.assertEqual(["WORKSTREAM_BUDGET_INVALID"], MODULE.validate(self.mutated(["effect_budget", "max_handoffs"], 13)))
        self.assertEqual(["WORKSTREAM_EVIDENCE_INVALID"], MODULE.validate(self.mutated(["evidence_outputs"], ["release"])))
        self.assertEqual(["WORKSTREAM_EVIDENCE_INVALID"], MODULE.validate(self.mutated(["evidence_outputs"], [{}])))
        self.assertEqual(["WORKSTREAM_EVIDENCE_INVALID"], MODULE.validate(self.mutated(["evidence_outputs"], [[]])))
