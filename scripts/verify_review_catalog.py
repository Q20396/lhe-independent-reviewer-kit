#!/usr/bin/env python3
"""Validate static review catalog selections without invoking review packs."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


MODULE_ID = re.compile(r"^[a-z][a-z0-9-]*$")
COMPONENT_ID = re.compile(r"^[a-z][a-z0-9:-]*$")
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
CATALOG_FIELDS = {"schema_version", "catalog_id", "modules", "components"}
MODULE_FIELDS = {
    "id", "kind", "version", "source_locator", "targets", "dependencies",
    "cost", "stability", "invocation_mode", "required_permissions",
    "side_effects", "network_behavior", "hook_behavior", "persistence_behavior",
    "evidence_outputs", "limitations", "rollback", "verification_state", "review_packs",
}
COMPONENT_FIELDS = {"id", "family", "modules"}
PROFILE_FIELDS = {"schema_version", "profile_id", "components", "human_disposition", "next_stage_authorized"}
ADVISOR_FIELDS = {"schema_version", "status", "profile_id", "selected_modules", "required_permissions", "missing_evidence", "limitations", "next_safe_action", "human_disposition", "next_stage_authorized"}
PERMISSIONS = {"git_object_read", "artifact_read"}
PROFILE_COMPONENTS = {
    "minimal-verification": {"baseline:identity"},
    "architecture-review": {"baseline:identity", "architecture:external-lenses"},
    "provider-intake": {"baseline:identity", "provider:manifest"},
    "release-review": {"baseline:identity", "release:assurance"},
}


def unique_nonempty_strings(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item for item in value) and len(value) == len(set(value))


def allowed_strings(value: Any, allowed: set[str], *, allow_empty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(isinstance(item, str) and item in allowed for item in value)
        and len(value) == len(set(value))
    )


def dependency_closure(module_ids: set[str], dependencies: dict[str, list[str]]) -> tuple[set[str], bool]:
    resolved: set[str] = set()
    visiting: set[str] = set()

    def visit(module_id: str) -> bool:
        if module_id in resolved:
            return True
        if module_id in visiting or module_id not in dependencies:
            return False
        visiting.add(module_id)
        if not all(visit(dependency) for dependency in dependencies[module_id]):
            return False
        visiting.remove(module_id)
        resolved.add(module_id)
        return True

    return resolved, all(visit(module_id) for module_id in module_ids)


def validate_catalog(catalog: Any) -> list[str]:
    if not isinstance(catalog, dict) or set(catalog) != CATALOG_FIELDS:
        return ["CATALOG_FIELD_SET_INVALID"]
    if catalog.get("schema_version") != "1.0.0" or not isinstance(catalog.get("catalog_id"), str) or not re.fullmatch(r"CAT-[A-Z0-9-]+", catalog["catalog_id"]):
        return ["CATALOG_IDENTITY_INVALID"]
    modules, components = catalog.get("modules"), catalog.get("components")
    if not isinstance(modules, list) or not modules or not isinstance(components, list) or not components:
        return ["CATALOG_COLLECTIONS_INVALID"]
    reasons: list[str] = []
    module_ids: set[str] = set()
    for module in modules:
        if not isinstance(module, dict) or set(module) != MODULE_FIELDS:
            reasons.append("MODULE_FIELD_SET_INVALID")
            continue
        module_id = module.get("id")
        if not isinstance(module_id, str) or not MODULE_ID.fullmatch(module_id):
            reasons.append("MODULE_ID_INVALID")
        elif module_id in module_ids:
            reasons.append("MODULE_ID_DUPLICATE")
        else:
            module_ids.add(module_id)
        if module.get("kind") != "review_module" or not isinstance(module.get("version"), str) or not SEMVER.fullmatch(module["version"]):
            reasons.append("MODULE_IDENTITY_INVALID")
        if not isinstance(module.get("source_locator"), str) or not re.match(r"^[a-z][a-z0-9+.-]*://", module["source_locator"]):
            reasons.append("MODULE_SOURCE_INVALID")
        if not unique_nonempty_strings(module.get("targets")) or not unique_nonempty_strings(module.get("review_packs")):
            reasons.append("MODULE_COLLECTION_INVALID")
        dependencies = module.get("dependencies")
        if not isinstance(dependencies, list) or not all(isinstance(item, str) and MODULE_ID.fullmatch(item) for item in dependencies) or len(dependencies) != len(set(dependencies)):
            reasons.append("MODULE_DEPENDENCIES_INVALID")
        if (
            not isinstance(module.get("cost"), str) or module["cost"] not in {"light", "medium", "heavy"}
            or not isinstance(module.get("stability"), str) or module["stability"] not in {"experimental", "stable"}
            or not isinstance(module.get("invocation_mode"), str) or module["invocation_mode"] not in {"user_only", "model_eligible"}
        ):
            reasons.append("MODULE_CLASSIFICATION_INVALID")
        if not allowed_strings(module.get("required_permissions"), PERMISSIONS, allow_empty=True):
            reasons.append("MODULE_PERMISSION_INVALID")
        if any(module.get(name) != "forbidden" for name in ("network_behavior", "hook_behavior", "persistence_behavior")) or module.get("side_effects") != "none" or module.get("rollback") != "not_applicable":
            reasons.append("MODULE_EFFECT_ESCALATION")
        if (
            not isinstance(module.get("verification_state"), str)
            or module["verification_state"] not in {"declared", "unverified"}
            or not allowed_strings(module.get("evidence_outputs"), {"diagnostic_report", "recommendation_envelope"})
            or not unique_nonempty_strings(module.get("limitations"))
        ):
            reasons.append("MODULE_EVIDENCE_BOUNDARY_INVALID")
    dependencies: dict[str, list[str]] = {}
    for module in modules:
        if isinstance(module, dict) and set(module) == MODULE_FIELDS and isinstance(module.get("dependencies"), list) and any(dependency not in module_ids for dependency in module["dependencies"]):
            reasons.append("MODULE_DEPENDENCY_UNKNOWN")
        if isinstance(module, dict) and set(module) == MODULE_FIELDS and isinstance(module.get("id"), str) and module["id"] in module_ids and isinstance(module.get("dependencies"), list):
            dependencies[module["id"]] = module["dependencies"]
    if dependencies and not dependency_closure(set(dependencies), dependencies)[1]:
        reasons.append("MODULE_DEPENDENCY_CYCLE")
    component_ids: set[str] = set()
    for component in components:
        if not isinstance(component, dict) or set(component) != COMPONENT_FIELDS:
            reasons.append("COMPONENT_FIELD_SET_INVALID")
            continue
        component_id = component.get("id")
        if not isinstance(component_id, str) or not COMPONENT_ID.fullmatch(component_id):
            reasons.append("COMPONENT_ID_INVALID")
        elif component_id in component_ids:
            reasons.append("COMPONENT_ID_DUPLICATE")
        else:
            component_ids.add(component_id)
        if (
            not isinstance(component.get("family"), str)
            or component["family"] not in {"baseline", "architecture", "provider", "release"}
            or not isinstance(component.get("modules"), list)
            or not component["modules"]
            or not all(isinstance(module, str) for module in component["modules"])
            or len(component["modules"]) != len(set(component["modules"]))
            or any(module not in module_ids for module in component["modules"])
        ):
            reasons.append("COMPONENT_MODULES_INVALID")
    return sorted(set(reasons))


def validate_profile(profile: Any, catalog: Any) -> list[str]:
    catalog_reasons = validate_catalog(catalog)
    if catalog_reasons:
        return ["CATALOG_INVALID"]
    if not isinstance(profile, dict) or set(profile) != PROFILE_FIELDS:
        return ["PROFILE_FIELD_SET_INVALID"]
    if profile.get("schema_version") != "1.0.0" or not isinstance(profile.get("profile_id"), str) or profile["profile_id"] not in PROFILE_COMPONENTS:
        return ["PROFILE_IDENTITY_INVALID"]
    components = profile.get("components")
    catalog_components = {component["id"] for component in catalog["components"]}
    if (
        not isinstance(components, list)
        or not components
        or not all(isinstance(component, str) for component in components)
        or len(components) != len(set(components))
        or any(component not in catalog_components for component in components)
    ):
        return ["PROFILE_COMPONENTS_INVALID"]
    if set(components) != PROFILE_COMPONENTS[profile["profile_id"]]:
        return ["PROFILE_COMPONENTS_INVALID"]
    if profile.get("human_disposition") != "pending" or profile.get("next_stage_authorized") is not False:
        return ["PROFILE_AUTHORITY_ESCALATION"]
    return []


def validate_advisor_response(response: Any, profile: Any, catalog: Any) -> list[str]:
    profile_reasons = validate_profile(profile, catalog)
    if profile_reasons:
        return ["PROFILE_INVALID"]
    if not isinstance(response, dict) or set(response) != ADVISOR_FIELDS:
        return ["ADVISOR_FIELD_SET_INVALID"]
    if (
        response.get("schema_version") != "1.0.0"
        or not isinstance(response.get("status"), str)
        or response["status"] not in {"eligible", "blocked", "unverified", "requires_human_decision"}
        or response.get("profile_id") != profile["profile_id"]
    ):
        return ["ADVISOR_IDENTITY_INVALID"]
    component_modules = {component["id"]: component["modules"] for component in catalog["components"]}
    dependencies = {module["id"]: module["dependencies"] for module in catalog["modules"]}
    direct_modules = {module for component in profile["components"] for module in component_modules[component]}
    expected_modules, resolved = dependency_closure(direct_modules, dependencies)
    if not resolved:
        return ["ADVISOR_MODULE_SELECTION_INVALID"]
    selected = response.get("selected_modules")
    if (
        not isinstance(selected, list)
        or not selected
        or not all(isinstance(module, str) for module in selected)
        or len(selected) != len(set(selected))
        or set(selected) != expected_modules
    ):
        return ["ADVISOR_MODULE_SELECTION_INVALID"]
    if not allowed_strings(response.get("required_permissions"), PERMISSIONS, allow_empty=True):
        return ["ADVISOR_PERMISSION_INVALID"]
    module_permissions = {module["id"]: set(module["required_permissions"]) for module in catalog["modules"]}
    expected_permissions = set().union(*(module_permissions[module] for module in expected_modules))
    if set(response["required_permissions"]) != expected_permissions:
        return ["ADVISOR_PERMISSION_INVALID"]
    if (
        not isinstance(response.get("missing_evidence"), list)
        or not all(isinstance(value, str) and value for value in response["missing_evidence"])
        or len(response["missing_evidence"]) != len(set(response["missing_evidence"]))
    ):
        return ["ADVISOR_MISSING_EVIDENCE_INVALID"]
    if not unique_nonempty_strings(response.get("limitations")) or not isinstance(response.get("next_safe_action"), str) or not response["next_safe_action"]:
        return ["ADVISOR_LIMITATIONS_INVALID"]
    if response.get("human_disposition") != "pending" or response.get("next_stage_authorized") is not False:
        return ["ADVISOR_AUTHORITY_ESCALATION"]
    return []


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--advisor", type=Path, required=True)
    args = parser.parse_args()
    try:
        catalog, profile, advisor = load_json(args.catalog), load_json(args.profile), load_json(args.advisor)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        print(json.dumps({"status": "FAIL", "reasons": ["INPUT_DOCUMENT_INVALID"]}, sort_keys=True))
        return 1
    reasons = validate_catalog(catalog) or validate_profile(profile, catalog) or validate_advisor_response(advisor, profile, catalog)
    print(json.dumps({"status": "PASS" if not reasons else "FAIL", "reasons": reasons}, sort_keys=True))
    return 0 if not reasons else 1


if __name__ == "__main__":
    raise SystemExit(main())
