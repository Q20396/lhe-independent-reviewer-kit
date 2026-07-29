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
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("verify_lhe_policy_snapshot", ROOT / "scripts" / "verify_lhe_policy_snapshot.py")
assert spec and spec.loader
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
CASES = json.loads((ROOT / "tests" / "fixtures" / "lhe-policy-snapshot" / "cases.json").read_text(encoding="utf-8"))


class LhePolicySnapshotContractTests(unittest.TestCase):
    def scenario(self):
        return copy.deepcopy(CASES["snapshot"]), copy.deepcopy(CASES["response"])

    def test_schemas_parse(self):
        for name in ("lhe-policy-snapshot.schema.json", "policy-checker-response.schema.json"):
            self.assertIsInstance(json.loads((ROOT / "contracts" / name).read_text(encoding="utf-8")), dict)

    def test_valid_synthetic_snapshot_and_response_pass(self):
        snapshot, response = self.scenario()
        self.assertEqual([], checker.validate_snapshot(snapshot))
        self.assertEqual([], checker.validate_response(response, snapshot))

    def test_identity_and_path_bindings_fail_closed(self):
        snapshot, _ = self.scenario()
        snapshot["commit"] = "UPPERCASE"
        self.assertEqual(["SNAPSHOT_BINDING_INVALID"], checker.validate_snapshot(snapshot))
        snapshot, _ = self.scenario()
        snapshot["selected_paths"].append(copy.deepcopy(snapshot["selected_paths"][0]))
        self.assertIn("SNAPSHOT_PATH_DUPLICATE", checker.validate_snapshot(snapshot))
        snapshot, _ = self.scenario()
        snapshot["selected_paths"][0]["path"] = "../escape"
        self.assertIn("SNAPSHOT_PATH_ENTRY_INVALID", checker.validate_snapshot(snapshot))
        snapshot, _ = self.scenario()
        snapshot["path_inventory_sha256"] = "f" * 64
        self.assertEqual(["SNAPSHOT_PATH_INVENTORY_MISMATCH"], checker.validate_snapshot(snapshot))
        snapshot, _ = self.scenario()
        snapshot["selected_paths"][0]["blob_oid"] = "f" * 40
        self.assertEqual(["SNAPSHOT_PATH_INVENTORY_MISMATCH"], checker.validate_snapshot(snapshot))

    def test_snapshot_and_response_authority_or_effect_escalation_are_rejected(self):
        snapshot, _ = self.scenario()
        snapshot["policy_claims"]["network_behavior"] = "allowed"
        self.assertIn("SNAPSHOT_POLICY_CLAIMS_INVALID", checker.validate_snapshot(snapshot))
        snapshot, response = self.scenario()
        response["requested_behaviors"]["promotion_authority"] = "merge"
        self.assertEqual(["RESPONSE_EFFECT_ESCALATION"], checker.validate_response(response, snapshot))
        _, response = self.scenario()
        response["next_stage_authorized"] = True
        self.assertEqual(["RESPONSE_AUTHORITY_ESCALATION"], checker.validate_response(response, CASES["snapshot"]))

    def test_response_must_bind_snapshot_and_not_expand_permissions(self):
        snapshot, response = self.scenario()
        response["snapshot_tree"] = "f" * 40
        self.assertEqual(["RESPONSE_IDENTITY_INVALID"], checker.validate_response(response, snapshot))
        snapshot, response = self.scenario()
        snapshot["policy_claims"]["allowed_permissions"] = ["git_object_read"]
        response["requested_permissions"] = ["artifact_read"]
        self.assertEqual(["RESPONSE_PERMISSION_CONFLICT"], checker.validate_response(response, snapshot))

    def test_malformed_data_and_cli_input_fail_closed(self):
        snapshot, _ = self.scenario()
        snapshot["policy_claims"]["allowed_permissions"] = [{}]
        self.assertIn("SNAPSHOT_POLICY_CLAIMS_INVALID", checker.validate_snapshot(snapshot))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bad = root / "bad.json"
            bad.write_text("{", encoding="utf-8")
            result = subprocess.run([sys.executable, str(ROOT / "scripts" / "verify_lhe_policy_snapshot.py"), "--snapshot", str(bad), "--response", str(bad)], check=False, capture_output=True, text=True)
            self.assertEqual(1, result.returncode)
            self.assertEqual({"reasons": ["INPUT_DOCUMENT_INVALID"], "status": "FAIL"}, json.loads(result.stdout))


if __name__ == "__main__":
    unittest.main()
