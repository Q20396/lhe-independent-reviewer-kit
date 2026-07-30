#!/usr/bin/env python3
"""Validate a discoverable workflow declaration without starting a workflow."""
import argparse
import json
import re
from pathlib import Path

FIELDS = {"schema_version", "pack_id", "title", "activation", "spec_required", "workstream_capsule_required", "governance_mode", "inputs", "deliverables", "stop_conditions", "allowed_effects", "client_authority_owner", "execution_authorized"}
GOVERNANCE = {"not-required", "client-requested", "risk-triggered"}


def nonempty_unique_strings(value):
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item for item in value) and len(value) == len(set(value))


def validate(value):
    if not isinstance(value, dict) or set(value) != FIELDS:
        return ["WORKFLOW_PACK_FIELD_SET_INVALID"]
    if value.get("schema_version") != "1.0.0" or not isinstance(value.get("pack_id"), str) or not re.fullmatch(r"WFP-[A-Z0-9-]+", value["pack_id"]) or not isinstance(value.get("title"), str) or not value["title"]:
        return ["WORKFLOW_PACK_IDENTITY_INVALID"]
    if value.get("activation") != "explicit-only" or value.get("spec_required") is not True or value.get("workstream_capsule_required") is not True:
        return ["WORKFLOW_PACK_ACTIVATION_INVALID"]
    if not isinstance(value.get("governance_mode"), str) or value["governance_mode"] not in GOVERNANCE:
        return ["WORKFLOW_PACK_GOVERNANCE_INVALID"]
    if any(not nonempty_unique_strings(value.get(name)) for name in ("inputs", "deliverables", "stop_conditions")):
        return ["WORKFLOW_PACK_CONTENT_INVALID"]
    if value.get("allowed_effects") != []:
        return ["WORKFLOW_PACK_EFFECT_FORBIDDEN"]
    if value.get("client_authority_owner") != "client" or value.get("execution_authorized") is not False:
        return ["WORKFLOW_PACK_AUTHORITY_ESCALATION"]
    return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", type=Path, required=True)
    args = parser.parse_args()
    try:
        value = json.loads(args.pack.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        print(json.dumps({"status": "FAIL", "reasons": ["INPUT_DOCUMENT_INVALID"]}))
        return 1
    reasons = validate(value)
    print(json.dumps({"status": "PASS" if not reasons else "FAIL", "reasons": reasons}, sort_keys=True))
    return 0 if not reasons else 1


if __name__ == "__main__":
    raise SystemExit(main())
