#!/usr/bin/env python3
"""Validate a static, client-owned autonomous-workstream request; never execute it."""

import argparse
import json
import re
from pathlib import Path


FIELDS = {"schema_version", "workstream_id", "spec_sha256", "target_identity_manifest_sha256", "client_authority_owner", "authorization_state", "execution_authorized", "agents", "effect_budget", "allowed_paths", "stop_conditions", "evidence_outputs"}
EFFECT_FIELDS = {"max_handoffs", "max_tool_calls", "max_tokens", "allowed_effects"}
OUTPUTS = {"handoff_receipt", "evidence_bundle", "limitation_report"}


def strings(value, minimum=0):
    return isinstance(value, list) and len(value) >= minimum and all(isinstance(item, str) and item for item in value) and len(value) == len(set(value))


def validate(value):
    if not isinstance(value, dict) or set(value) != FIELDS:
        return ["WORKSTREAM_FIELD_SET_INVALID"]
    if value.get("schema_version") != "1.0.0" or not isinstance(value.get("workstream_id"), str) or not re.fullmatch(r"AWS-[A-Z0-9-]+", value["workstream_id"]):
        return ["WORKSTREAM_IDENTITY_INVALID"]
    for name in ("spec_sha256", "target_identity_manifest_sha256"):
        if not isinstance(value.get(name), str) or not re.fullmatch(r"[0-9a-f]{64}", value[name]):
            return ["WORKSTREAM_IDENTITY_INVALID"]
    if value.get("client_authority_owner") != "client" or value.get("authorization_state") != "pending" or value.get("execution_authorized") is not False:
        return ["CLIENT_AUTHORITY_ESCALATION"]
    if not strings(value.get("agents"), 1) or not strings(value.get("stop_conditions"), 1):
        return ["WORKSTREAM_EVIDENCE_INVALID"]
    if value.get("allowed_paths") != []:
        return ["WORKSTREAM_WRITE_SCOPE_FORBIDDEN"]
    if not isinstance(value.get("evidence_outputs"), list) or not value["evidence_outputs"] or any(not isinstance(item, str) or item not in OUTPUTS for item in value["evidence_outputs"]) or len(value["evidence_outputs"]) != len(set(value["evidence_outputs"])):
        return ["WORKSTREAM_EVIDENCE_INVALID"]
    budget = value.get("effect_budget")
    if not isinstance(budget, dict) or set(budget) != EFFECT_FIELDS or budget.get("allowed_effects") != []:
        return ["WORKSTREAM_EFFECTS_FORBIDDEN"]
    if any(isinstance(budget.get(name), bool) or not isinstance(budget.get(name), int) or budget[name] < minimum or budget[name] > maximum for name, minimum, maximum in (("max_handoffs", 0, 12), ("max_tool_calls", 0, 30), ("max_tokens", 1, 200000))):
        return ["WORKSTREAM_BUDGET_INVALID"]
    return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--envelope", type=Path, required=True)
    args = parser.parse_args()
    try:
        value = json.loads(args.envelope.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        print(json.dumps({"status": "FAIL", "reasons": ["INPUT_DOCUMENT_INVALID"]}))
        return 1
    reasons = validate(value)
    print(json.dumps({"status": "PASS" if not reasons else "FAIL", "reasons": reasons}, sort_keys=True))
    return 0 if not reasons else 1


if __name__ == "__main__":
    raise SystemExit(main())
