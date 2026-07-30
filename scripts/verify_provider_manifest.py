#!/usr/bin/env python3
"""Validate declared-disabled providers and diagnostic-only doctor responses."""
import argparse
import json
import re
from pathlib import Path
from typing import Any

PERMS = {"git_object_read", "artifact_read"}
KINDS = {"graph_provider", "planning_provider", "catalog_provider", "worker_orchestration_provider", "workflow_pack_provider"}
MF = {"schema_version", "provider_id", "kind", "version", "status", "source_identity", "required_permissions", "network_behavior", "hook_behavior", "persistence_behavior", "execution_behavior", "evidence_requirements", "limitations", "human_disposition", "next_stage_authorized"}
DF = {"schema_version", "provider_id", "status", "reason_codes", "observed_evidence", "limitations", "next_safe_action", "human_disposition", "next_stage_authorized"}


def strings(value: Any, nonempty: bool = False) -> bool:
    return isinstance(value, list) and (bool(value) if nonempty else True) and all(isinstance(item, str) and item for item in value) and len(value) == len(set(value))


def source_identity(value: Any) -> bool:
    expected = {"intake_status", "repository_locator", "commit", "tree", "parent", "source_blobs"}
    if not isinstance(value, dict) or set(value) != expected:
        return False
    if value.get("intake_status") != "public_read_only" or not isinstance(value.get("repository_locator"), str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value["repository_locator"]):
        return False
    if any(not isinstance(value.get(key), str) or not re.fullmatch(r"[0-9a-f]{40}", value[key]) for key in ("commit", "tree", "parent")):
        return False
    blobs = value.get("source_blobs")
    if not isinstance(blobs, list) or not blobs:
        return False
    paths: list[str] = []
    for blob in blobs:
        if not isinstance(blob, dict) or set(blob) != {"path", "sha1"}:
            return False
        path, sha1 = blob.get("path"), blob.get("sha1")
        if not isinstance(path, str) or not path or path.startswith("/") or "\\" in path or ".." in path.split("/"):
            return False
        if not isinstance(sha1, str) or not re.fullmatch(r"[0-9a-f]{40}", sha1):
            return False
        paths.append(path)
    return len(paths) == len(set(paths))


def manifest(value: Any) -> list[str]:
    if not isinstance(value, dict) or set(value) != MF:
        return ["MANIFEST_FIELD_SET_INVALID"]
    if value.get("schema_version") != "1.0.0" or not isinstance(value.get("provider_id"), str) or not re.fullmatch(r"PROVIDER-[A-Z0-9-]+", value["provider_id"]) or not isinstance(value.get("kind"), str) or value["kind"] not in KINDS or not isinstance(value.get("version"), str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value["version"]):
        return ["MANIFEST_IDENTITY_INVALID"]
    if not source_identity(value.get("source_identity")):
        return ["MANIFEST_SOURCE_IDENTITY_INVALID"]
    if value.get("status") != "declared_disabled" or any(value.get(key) != "forbidden" for key in ("network_behavior", "hook_behavior", "persistence_behavior", "execution_behavior")):
        return ["MANIFEST_EFFECT_ESCALATION"]
    if not strings(value.get("required_permissions")) or any(permission not in PERMS for permission in value["required_permissions"]) or not strings(value.get("evidence_requirements"), True) or not strings(value.get("limitations"), True):
        return ["MANIFEST_EVIDENCE_INVALID"]
    return [] if value.get("human_disposition") == "pending" and value.get("next_stage_authorized") is False else ["MANIFEST_AUTHORITY_ESCALATION"]


def doctor(value: Any, provider: Any) -> list[str]:
    if manifest(provider):
        return ["MANIFEST_INVALID"]
    if not isinstance(value, dict) or set(value) != DF:
        return ["DOCTOR_FIELD_SET_INVALID"]
    if value.get("schema_version") != "1.0.0" or value.get("provider_id") != provider["provider_id"] or not isinstance(value.get("status"), str) or value["status"] not in {"blocked", "unverified", "requires_human_decision"}:
        return ["DOCTOR_IDENTITY_INVALID"]
    if not strings(value.get("reason_codes"), True) or not strings(value.get("observed_evidence")) or not strings(value.get("limitations"), True) or not isinstance(value.get("next_safe_action"), str) or value["next_safe_action"] not in {"collect_static_evidence", "request_human_decision", "request_provider_intake"}:
        return ["DOCTOR_EVIDENCE_INVALID"]
    return [] if value.get("human_disposition") == "pending" and value.get("next_stage_authorized") is False else ["DOCTOR_AUTHORITY_ESCALATION"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--doctor", type=Path, required=True)
    args = parser.parse_args()
    try:
        provider = json.loads(args.manifest.read_text())
        response = json.loads(args.doctor.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        print('{"reasons":["INPUT_DOCUMENT_INVALID"],"status":"FAIL"}')
        return 1
    reasons = manifest(provider) or doctor(response, provider)
    print(json.dumps({"status": "PASS" if not reasons else "FAIL", "reasons": reasons}, sort_keys=True))
    return 0 if not reasons else 1


if __name__ == "__main__":
    raise SystemExit(main())
