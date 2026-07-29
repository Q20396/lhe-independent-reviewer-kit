import json,importlib.util,unittest,copy
from pathlib import Path
R=Path(__file__).resolve().parents[1];s=importlib.util.spec_from_file_location('d',R/'scripts/verify_review_delivery_bundle.py');d=importlib.util.module_from_spec(s);s.loader.exec_module(d);C=json.loads((R/'tests/fixtures/review-delivery-bundle/cases.json').read_text())['bundle']
class T(unittest.TestCase):
 def test_ok(self):self.assertEqual([],d.v(copy.deepcopy(C),C['target_commit'],C['target_identity_manifest_sha256']))
 def test_target_binding(self):x=copy.deepcopy(C);x['target_commit']='a'*40;self.assertEqual(['BUNDLE_TARGET_MISMATCH'],d.v(x,C['target_commit'],C['target_identity_manifest_sha256']))
 def test_target_identity_binding(self):x=copy.deepcopy(C);x['target_identity_manifest_sha256']='c'*64;self.assertEqual(['BUNDLE_TARGET_IDENTITY_MISMATCH'],d.v(x,C['target_commit'],C['target_identity_manifest_sha256']))
 def test_no_authority(self):x=copy.deepcopy(C);x['next_stage_authorized']=True;self.assertEqual(['BUNDLE_AUTHORITY_ESCALATION'],d.v(x))
 def test_no_execution_action(self):x=copy.deepcopy(C);x['recommendations']=['install'];self.assertEqual(['BUNDLE_EVIDENCE_INVALID'],d.v(x))
