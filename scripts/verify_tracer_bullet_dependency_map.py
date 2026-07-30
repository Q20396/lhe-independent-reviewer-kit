#!/usr/bin/env python3
"""Validate a static dependency map without creating or running tickets."""
import argparse
import json
import re
from pathlib import Path

FIELDS = {"schema_version", "map_id", "workstream_capsule_id", "spec_sha256", "items", "allowed_effects", "human_disposition", "next_stage_authorized"}
ITEM_FIELDS = {"item_id", "title", "deliverable", "acceptance_criteria", "blocked_by", "status", "evidence_refs", "allowed_effects", "execution_authorized"}


def valid_sha256(value):
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value))


def strings(value, pattern=None, min_items=1):
    return isinstance(value, list) and len(value) >= min_items and all(isinstance(item, str) and item and (pattern is None or re.fullmatch(pattern, item)) for item in value) and len(value) == len(set(value))


def item_reasons(item):
    if not isinstance(item, dict) or set(item) != ITEM_FIELDS:
        return ["TRACER_BULLET_ITEM_FIELD_SET_INVALID"]
    if not isinstance(item.get("item_id"), str) or not re.fullmatch(r"TBI-[A-Z0-9-]+", item["item_id"]) or any(not isinstance(item.get(name), str) or not item[name] for name in ("title", "deliverable")):
        return ["TRACER_BULLET_ITEM_IDENTITY_INVALID"]
    if not strings(item.get("acceptance_criteria")) or not strings(item.get("evidence_refs"), r"EVID-[A-Z0-9-]+") or not strings(item.get("blocked_by"), r"TBI-[A-Z0-9-]+", min_items=0):
        return ["TRACER_BULLET_ITEM_CONTENT_INVALID"]
    if item.get("status") != "proposed" or item.get("allowed_effects") != [] or item.get("execution_authorized") is not False:
        return ["TRACER_BULLET_ITEM_AUTHORITY_ESCALATION"]
    return []


def has_cycle(edges):
    remaining = {node: set(blockers) for node, blockers in edges.items()}
    ready = [node for node, blockers in remaining.items() if not blockers]
    while ready:
        completed = ready.pop()
        for node, blockers in remaining.items():
            if completed in blockers:
                blockers.remove(completed)
                if not blockers:
                    ready.append(node)
        remaining.pop(completed, None)
    return bool(remaining)


def validate(value):
    if not isinstance(value, dict) or set(value) != FIELDS:
        return ["TRACER_BULLET_FIELD_SET_INVALID"]
    if value.get("schema_version") != "1.0.0" or not isinstance(value.get("map_id"), str) or not re.fullmatch(r"TBDM-[A-Z0-9-]+", value["map_id"]) or not isinstance(value.get("workstream_capsule_id"), str) or not re.fullmatch(r"WSC-[A-Z0-9-]+", value["workstream_capsule_id"]) or not valid_sha256(value.get("spec_sha256")):
        return ["TRACER_BULLET_IDENTITY_INVALID"]
    items = value.get("items")
    if not isinstance(items, list) or not items:
        return ["TRACER_BULLET_ITEMS_INVALID"]
    for item in items:
        if reasons := item_reasons(item):
            return reasons
    ids = [item["item_id"] for item in items]
    if len(ids) != len(set(ids)):
        return ["TRACER_BULLET_DUPLICATE_ITEM_ID"]
    edges = {item["item_id"]: item["blocked_by"] for item in items}
    if any(item_id in blockers or any(blocker not in edges for blocker in blockers) for item_id, blockers in edges.items()):
        return ["TRACER_BULLET_BLOCKER_INVALID"]
    if has_cycle(edges):
        return ["TRACER_BULLET_CYCLE_FORBIDDEN"]
    if value.get("allowed_effects") != [] or value.get("human_disposition") != "pending" or value.get("next_stage_authorized") is not False:
        return ["TRACER_BULLET_AUTHORITY_ESCALATION"]
    return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", type=Path, required=True)
    args = parser.parse_args()
    try:
        value = json.loads(args.map.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        print(json.dumps({"status": "FAIL", "reasons": ["INPUT_DOCUMENT_INVALID"]}))
        return 1
    reasons = validate(value)
    print(json.dumps({"status": "PASS" if not reasons else "FAIL", "reasons": reasons}, sort_keys=True))
    return 0 if not reasons else 1


if __name__ == "__main__":
    raise SystemExit(main())
