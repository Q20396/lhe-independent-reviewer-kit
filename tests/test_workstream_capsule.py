import copy,importlib.util,json,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1];s=importlib.util.spec_from_file_location("capsule",R/"scripts/verify_workstream_capsule.py");m=importlib.util.module_from_spec(s);s.loader.exec_module(m);V=json.loads((R/"tests/fixtures/workstream-capsule/cases.json").read_text())["valid"]
class CapsuleTest(unittest.TestCase):
 def x(self,k,v):x=copy.deepcopy(V);x[k]=v;return x
 def test_valid_static_capsule(self):self.assertEqual([],m.validate(copy.deepcopy(V)))
 def test_content_is_closed(self):
  self.assertEqual(["CAPSULE_CONTENT_INVALID"],m.validate(self.x("phase",[])))
  self.assertEqual(["CAPSULE_CONTENT_INVALID"],m.validate(self.x("evidence_refs",[{}])))
  self.assertEqual(["CAPSULE_CONTENT_INVALID"],m.validate(self.x("evidence_refs",["Customer bank account: 123456"])))
  self.assertEqual(["CAPSULE_CONTENT_INVALID"],m.validate(self.x("blockers",["password=secret-value"])))
  self.assertEqual(["CAPSULE_CONTENT_INVALID"],m.validate(self.x("next_safe_action",{})))
 def test_no_default_persistence(self):self.assertEqual(["CAPSULE_PERSISTENCE_FORBIDDEN"],m.validate(self.x("persistence_requested",True)))
 def test_client_authority_stays_pending(self):
  self.assertEqual(["CAPSULE_AUTHORITY_ESCALATION"],m.validate(self.x("human_disposition","approved")))
  self.assertEqual(["CAPSULE_AUTHORITY_ESCALATION"],m.validate(self.x("next_stage_authorized",True)))
