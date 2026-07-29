#!/usr/bin/env python3
"""Validate supplied, static LHE policy snapshots without reading or running LHE."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


OID = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SNAPSHOT_ID = re.compile(r"^LHE-SNAPSHOT-[A-Z0-9-]+$")
PERMISSIONS = {"git_object_read", "artifact_read"}
SNAPSHOT_FIELDS = {"schema_version", "snapshot_id", "source_repository_locator", "commit", "tree", "selected_paths", "path_inventory_sha256", "retrieved_at", "known_limitations", "policy_claims", "human_disposition", "next_stage_authorized"}
PATH_FIELDS = {"path", "blob_oid", "content_sha256"}
CLAIM_FIELDS = {"allowed_permissions", "network_behavior", "hook_behavior", "persistence_behavior", "promotion_authority"}
RESPONSE_FIELDS = {"schema_version", "snapshot_id", "snapshot_commit", "snapshot_tree", "status", "requested_permissions", "requested_behaviors", "missing_evidence", "limitations", "next_safe_action", "human_disposition", "next_stage_authorized"}
BEHAVIOR_FIELDS = {"network_behavior", "hook_behavior", "persistence_behavior", "promotion_authority"}


def strings(value: Any, *, nonempty: bool = False) -> bool:
    return isinstance(value, list) and (bool(value) if nonempty else True) and all(isinstance(item, str) and item for item in value) and len(value) == len(set(value))


def permissions(value: Any) -> bool:
    return strings(value) and all(item in PERMISSIONS for item in value)


def safe_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or value.startswith("/") or "\\" in value or "\x00" in value or "\r" in value or "\n" in value:
        return False
    return all(segment not in {"", ".", ".."} for segment in value.split("/"))


def forbidden_behaviors(value: Any) -> bool:
    return isinstance(value, dict) and set(value) == BEHAVIOR_FIELDS and value == {
        "network_behavior": "forbidden", "hook_behavior": "forbidden", "persistence_behavior": "forbidden", "promotion_authority": "none",
    }


def inventory_sha256(entries: list[dict[str, str]]) -> str:
    """Hash sorted, ASCII JSON declarations; this does not read source blobs."""
    canonical = json.dumps(sorted(entries, key=lambda entry: entry["path"]), ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def validate_snapshot(snapshot: Any) -> list[str]:
    if not isinstance(snapshot, dict) or set(snapshot) != SNAPSHOT_FIELDS:
        return ["SNAPSHOT_FIELD_SET_INVALID"]
    if snapshot.get("schema_version") != "1.0.0" or not isinstance(snapshot.get("snapshot_id"), str) or not SNAPSHOT_ID.fullmatch(snapshot["snapshot_id"]):
        return ["SNAPSHOT_IDENTITY_INVALID"]
    if not isinstance(snapshot.get("source_repository_locator"), str) or not snapshot["source_repository_locator"]:
        return ["SNAPSHOT_SOURCE_INVALID"]
    if not isinstance(snapshot.get("commit"), str) or not OID.fullmatch(snapshot["commit"]) or not isinstance(snapshot.get("tree"), str) or not OID.fullmatch(snapshot["tree"]) or not isinstance(snapshot.get("path_inventory_sha256"), str) or not SHA256.fullmatch(snapshot["path_inventory_sha256"]):
        return ["SNAPSHOT_BINDING_INVALID"]
    if not isinstance(snapshot.get("retrieved_at"), str) or not snapshot["retrieved_at"] or not strings(snapshot.get("known_limitations"), nonempty=True):
        return ["SNAPSHOT_EVIDENCE_INVALID"]
    entries = snapshot.get("selected_paths")
    if not isinstance(entries, list) or not entries:
        return ["SNAPSHOT_PATHS_INVALID"]
    reasons: list[str] = []
    paths: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != PATH_FIELDS:
            reasons.append("SNAPSHOT_PATH_ENTRY_INVALID")
            continue
        path = entry.get("path")
        if not safe_path(path):
            reasons.append("SNAPSHOT_PATH_ENTRY_INVALID")
        elif path in paths:
            reasons.append("SNAPSHOT_PATH_DUPLICATE")
        else:
            paths.add(path)
        if not isinstance(entry.get("blob_oid"), str) or not OID.fullmatch(entry["blob_oid"]) or not isinstance(entry.get("content_sha256"), str) or not SHA256.fullmatch(entry["content_sha256"]):
            reasons.append("SNAPSHOT_PATH_ENTRY_INVALID")
    if not reasons and snapshot["path_inventory_sha256"] != inventory_sha256(entries):
        reasons.append("SNAPSHOT_PATH_INVENTORY_MISMATCH")
    claims = snapshot.get("policy_claims")
    if not isinstance(claims, dict) or set(claims) != CLAIM_FIELDS or not permissions(claims.get("allowed_permissions")) or not forbidden_behaviors({name: claims.get(name) for name in BEHAVIOR_FIELDS}):
        reasons.append("SNAPSHOT_POLICY_CLAIMS_INVALID")
    if snapshot.get("human_disposition") != "pending" or snapshot.get("next_stage_authorized") is not False:
        reasons.append("SNAPSHOT_AUTHORITY_ESCALATION")
    return sorted(set(reasons))


def validate_response(response: Any, snapshot: Any) -> list[str]:
    if validate_snapshot(snapshot):
        return ["SNAPSHOT_INVALID"]
    if not isinstance(response, dict) or set(response) != RESPONSE_FIELDS:
        return ["RESPONSE_FIELD_SET_INVALID"]
    if (
        response.get("schema_version") != "1.0.0"
        or response.get("snapshot_id") != snapshot["snapshot_id"]
        or response.get("snapshot_commit") != snapshot["commit"]
        or response.get("snapshot_tree") != snapshot["tree"]
        or not isinstance(response.get("status"), str)
        or response["status"] not in {"eligible", "blocked", "unverified", "requires_human_decision"}
    ):
        return ["RESPONSE_IDENTITY_INVALID"]
    if not permissions(response.get("requested_permissions")) or not set(response["requested_permissions"]).issubset(set(snapshot["policy_claims"]["allowed_permissions"])):
        return ["RESPONSE_PERMISSION_CONFLICT"]
    if not forbidden_behaviors(response.get("requested_behaviors")):
        return ["RESPONSE_EFFECT_ESCALATION"]
    if not strings(response.get("missing_evidence")) or not strings(response.get("limitations"), nonempty=True) or not isinstance(response.get("next_safe_action"), str) or not response["next_safe_action"]:
        return ["RESPONSE_EVIDENCE_INVALID"]
    if response.get("human_disposition") != "pending" or response.get("next_stage_authorized") is not False:
        return ["RESPONSE_AUTHORITY_ESCALATION"]
    return []


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--response", type=Path, required=True)
    args = parser.parse_args()
    try:
        snapshot, response = load_json(args.snapshot), load_json(args.response)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        print(json.dumps({"status": "FAIL", "reasons": ["INPUT_DOCUMENT_INVALID"]}, sort_keys=True))
        return 1
    reasons = validate_snapshot(snapshot) or validate_response(response, snapshot)
    print(json.dumps({"status": "PASS" if not reasons else "FAIL", "reasons": reasons}, sort_keys=True))
    return 0 if not reasons else 1


if __name__ == "__main__":
    raise SystemExit(main())
