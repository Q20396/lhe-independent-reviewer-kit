import copy,importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];s=importlib.util.spec_from_file_location("p",ROOT/"scripts/verify_provider_manifest.py");p=importlib.util.module_from_spec(s);s.loader.exec_module(p);C=json.loads((ROOT/"tests/fixtures/provider-manifest/cases.json").read_text())
class T(unittest.TestCase):
 def x(self):return copy.deepcopy(C["manifest"]),copy.deepcopy(C["doctor"])
 def test_ok(self):m,d=self.x();self.assertEqual([],p.manifest(m));self.assertEqual([],p.doctor(d,m))
 def test_effect(self):m,d=self.x();m["network_behavior"]="allowed";self.assertEqual(["MANIFEST_EFFECT_ESCALATION"],p.manifest(m))
 def test_authority(self):m,d=self.x();d["next_stage_authorized"]=True;self.assertEqual(["DOCTOR_AUTHORITY_ESCALATION"],p.doctor(d,m))
 def test_type(self):m,d=self.x();m["required_permissions"]=[{}];self.assertEqual(["MANIFEST_EVIDENCE_INVALID"],p.manifest(m))
 def test_binding(self):m,d=self.x();d["provider_id"]="PROVIDER-X";self.assertEqual(["DOCTOR_IDENTITY_INVALID"],p.doctor(d,m))
 def test_semver_and_safe_action(self):
  m,d=self.x();m["version"]="not-a-semver";self.assertEqual(["MANIFEST_IDENTITY_INVALID"],p.manifest(m))
  m,d=self.x();d["next_safe_action"]="Install and execute the provider.";self.assertEqual(["DOCTOR_EVIDENCE_INVALID"],p.doctor(d,m))
  m,d=self.x();d["status"]=[];self.assertEqual(["DOCTOR_IDENTITY_INVALID"],p.doctor(d,m))
  m,d=self.x();d["next_safe_action"]=[];self.assertEqual(["DOCTOR_EVIDENCE_INVALID"],p.doctor(d,m))
 def test_source_identity_is_required_and_fail_closed(self):
  m,d=self.x();m["source_identity"]["commit"]="invalid";self.assertEqual(["MANIFEST_SOURCE_IDENTITY_INVALID"],p.manifest(m))
  m,d=self.x();m["source_identity"]["source_blobs"]=[{"path":"../escape.py","sha1":"d"*40}];self.assertEqual(["MANIFEST_SOURCE_IDENTITY_INVALID"],p.manifest(m))
  m,d=self.x();m["source_identity"]["source_blobs"]+=[{"path":"provider.py","sha1":"e"*40}];self.assertEqual(["MANIFEST_SOURCE_IDENTITY_INVALID"],p.manifest(m))
 def test_declared_langgraph_swarm_example_is_disabled(self):
  example=json.loads((ROOT/"examples/providers/langgraph-swarm-001.json").read_text())
  self.assertEqual([],p.manifest(example))
  self.assertEqual("worker_orchestration_provider",example["kind"])
  self.assertEqual("declared_disabled",example["status"])
  self.assertEqual([],example["required_permissions"])
