import copy,importlib.util,json,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1];s=importlib.util.spec_from_file_location("handoff",R/"scripts/verify_swarm_handoff_receipt.py");m=importlib.util.module_from_spec(s);s.loader.exec_module(m);V=json.loads((R/"tests/fixtures/swarm-handoff-receipt/cases.json").read_text())["valid"]
class HandoffReceiptTest(unittest.TestCase):
 def x(self,k,v):x=copy.deepcopy(V);x[k]=v;return x
 def test_valid_static_receipt(self):self.assertEqual([],m.validate(copy.deepcopy(V)))
 def test_cannot_authorize_or_execute(self):
  self.assertEqual(["HANDOFF_AUTHORITY_ESCALATION"],m.validate(self.x("client_authority_owner","agent")))
  self.assertEqual(["HANDOFF_AUTHORITY_ESCALATION"],m.validate(self.x("execution_authorized",True)))
 def test_cannot_report_effects(self):self.assertEqual(["HANDOFF_EFFECT_FORBIDDEN"],m.validate(self.x("effect_summary",["network"])))
 def test_risks_and_next_step_required(self):
  self.assertEqual(["HANDOFF_EVIDENCE_INVALID"],m.validate(self.x("unresolved_risks",[])))
  self.assertEqual(["HANDOFF_EVIDENCE_INVALID"],m.validate(self.x("next_safe_action","handoff")))
  self.assertEqual(["HANDOFF_EVIDENCE_INVALID"],m.validate(self.x("next_safe_action",[])))
  self.assertEqual(["HANDOFF_EVIDENCE_INVALID"],m.validate(self.x("next_safe_action",{})))
