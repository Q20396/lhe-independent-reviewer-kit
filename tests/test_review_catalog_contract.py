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


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


catalog_verifier = load_module("verify_review_catalog", ROOT / "scripts" / "verify_review_catalog.py")
CASES = json.loads((ROOT / "tests" / "fixtures" / "review-catalog" / "cases.json").read_text(encoding="utf-8"))


class ReviewCatalogContractTests(unittest.TestCase):
    def scenario(self):
        return copy.deepcopy(CASES["catalog"]), copy.deepcopy(CASES["profile"]), copy.deepcopy(CASES["advisor"])

    def test_contract_schemas_parse(self):
        for path in (ROOT / "contracts").glob("*.schema.json"):
            self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict)

    def test_valid_static_catalog_profile_and_advisor_pass(self):
        catalog, profile, advisor = self.scenario()
        self.assertEqual([], catalog_verifier.validate_catalog(catalog))
        self.assertEqual([], catalog_verifier.validate_profile(profile, catalog))
        self.assertEqual([], catalog_verifier.validate_advisor_response(advisor, profile, catalog))

    def test_cli_validates_three_explicit_contract_documents(self):
        catalog, profile, advisor = self.scenario()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = {}
            for name, value in (("catalog", catalog), ("profile", profile), ("advisor", advisor)):
                path = root / f"{name}.json"
                path.write_text(json.dumps(value), encoding="utf-8")
                paths[name] = path
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "verify_review_catalog.py"), "--catalog", str(paths["catalog"]), "--profile", str(paths["profile"]), "--advisor", str(paths["advisor"])],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual({"reasons": [], "status": "PASS"}, json.loads(result.stdout))

    def test_catalog_rejects_unknown_dependency_and_duplicate_module(self):
        catalog, _, _ = self.scenario()
        catalog["modules"][1]["dependencies"] = ["missing-module"]
        self.assertIn("MODULE_DEPENDENCY_UNKNOWN", catalog_verifier.validate_catalog(catalog))
        catalog, _, _ = self.scenario()
        catalog["modules"][1]["id"] = "target-identity"
        self.assertIn("MODULE_ID_DUPLICATE", catalog_verifier.validate_catalog(catalog))

    def test_catalog_rejects_runtime_effect_escalation(self):
        catalog, _, _ = self.scenario()
        catalog["modules"][0]["network_behavior"] = "required"
        catalog["modules"][0]["hook_behavior"] = "optional"
        self.assertIn("MODULE_EFFECT_ESCALATION", catalog_verifier.validate_catalog(catalog))

    def test_catalog_rejects_malformed_enum_values_and_dependency_cycles(self):
        for field in ("cost", "stability", "invocation_mode", "verification_state"):
            catalog, _, _ = self.scenario()
            catalog["modules"][0][field] = {}
            self.assertTrue(catalog_verifier.validate_catalog(catalog))
        catalog, _, _ = self.scenario()
        catalog["modules"][0]["required_permissions"] = [{}]
        self.assertIn("MODULE_PERMISSION_INVALID", catalog_verifier.validate_catalog(catalog))
        catalog, _, _ = self.scenario()
        catalog["modules"][0]["dependencies"] = ["architecture-lenses"]
        self.assertIn("MODULE_DEPENDENCY_CYCLE", catalog_verifier.validate_catalog(catalog))

    def test_profile_rejects_unknown_component_and_authority_escalation(self):
        catalog, profile, _ = self.scenario()
        profile["components"] = ["unknown:component"]
        self.assertEqual(["PROFILE_COMPONENTS_INVALID"], catalog_verifier.validate_profile(profile, catalog))
        _, profile, _ = self.scenario()
        profile["next_stage_authorized"] = True
        self.assertEqual(["PROFILE_AUTHORITY_ESCALATION"], catalog_verifier.validate_profile(profile, CASES["catalog"]))
        catalog, profile, _ = self.scenario()
        profile["profile_id"] = "minimal-verification"
        self.assertEqual(["PROFILE_COMPONENTS_INVALID"], catalog_verifier.validate_profile(profile, catalog))

    def test_advisor_must_match_profile_modules_and_remain_non_authorizing(self):
        catalog, profile, advisor = self.scenario()
        advisor["selected_modules"] = ["target-identity"]
        self.assertEqual(["ADVISOR_MODULE_SELECTION_INVALID"], catalog_verifier.validate_advisor_response(advisor, profile, catalog))
        _, profile, advisor = self.scenario()
        advisor["human_disposition"] = "approved"
        self.assertEqual(["ADVISOR_AUTHORITY_ESCALATION"], catalog_verifier.validate_advisor_response(advisor, profile, CASES["catalog"]))

    def test_advisor_rejects_unknown_permission_and_duplicate_missing_evidence(self):
        catalog, profile, advisor = self.scenario()
        advisor["required_permissions"] = ["network"]
        self.assertEqual(["ADVISOR_PERMISSION_INVALID"], catalog_verifier.validate_advisor_response(advisor, profile, catalog))
        _, profile, advisor = self.scenario()
        advisor["missing_evidence"] *= 2
        self.assertEqual(["ADVISOR_MISSING_EVIDENCE_INVALID"], catalog_verifier.validate_advisor_response(advisor, profile, CASES["catalog"]))

    def test_advisor_requires_the_permission_union_and_dependency_closure(self):
        catalog, profile, advisor = self.scenario()
        advisor["required_permissions"] = []
        self.assertEqual(["ADVISOR_PERMISSION_INVALID"], catalog_verifier.validate_advisor_response(advisor, profile, catalog))
        catalog, profile, advisor = self.scenario()
        profile["components"] = ["architecture:external-lenses"]
        advisor["selected_modules"] = ["architecture-lenses"]
        self.assertEqual(["PROFILE_INVALID"], catalog_verifier.validate_advisor_response(advisor, profile, catalog))

    def test_malformed_list_members_fail_closed_without_exceptions(self):
        catalog, _, _ = self.scenario()
        catalog["components"][0]["modules"] = [{}]
        self.assertIn("COMPONENT_MODULES_INVALID", catalog_verifier.validate_catalog(catalog))
        catalog, profile, _ = self.scenario()
        profile["components"] = [{}]
        self.assertEqual(["PROFILE_COMPONENTS_INVALID"], catalog_verifier.validate_profile(profile, catalog))
        catalog, profile, advisor = self.scenario()
        advisor["selected_modules"] = [{}]
        self.assertEqual(["ADVISOR_MODULE_SELECTION_INVALID"], catalog_verifier.validate_advisor_response(advisor, profile, catalog))
        _, profile, advisor = self.scenario()
        advisor["missing_evidence"] = [{}]
        self.assertEqual(["ADVISOR_MISSING_EVIDENCE_INVALID"], catalog_verifier.validate_advisor_response(advisor, profile, CASES["catalog"]))


if __name__ == "__main__":
    unittest.main()
