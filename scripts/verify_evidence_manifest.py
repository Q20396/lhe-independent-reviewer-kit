#!/usr/bin/env python3
"""Validate structural evidence boundaries without granting review authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from verify_candidate_identity import (
    is_safe_repository_path,
    derive_target_identity,
    read_runtime_identity,
    validate_request_structure,
)


SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
REVIEW_ID = re.compile(r"^IRR-[A-Z0-9-]+$")
EVIDENCE_ID = re.compile(r"^EVID-[A-Z0-9-]+$")
ALLOWED_KINDS = {"command", "git_object", "ci_run", "provider_artifact"}
ALLOWED_DIRECTIONS = {"supports", "refutes", "neutral"}
MANIFEST_FIELDS = {
    "schema_version", "review_id", "review_request_sha256", "reviewer_kit_commit",
    "reviewer_kit_tree", "candidate_commit", "candidate_tree", "candidate_object_delta_sha256", "evidence",
}
EVIDENCE_FIELDS = {
    "evidence_id", "kind", "claim_direction", "raw_artifact_locator",
    "raw_artifact_sha256", "limitations",
}
VERDICT_FIELDS = {
    "schema_version", "review_id", "review_request_sha256", "evidence_manifest_sha256",
    "reviewer_kit_commit", "reviewer_kit_tree", "candidate_commit", "candidate_tree",
    "candidate_object_delta_sha256",
    "verdict", "findings", "limitations", "human_disposition", "promotion_state",
    "next_stage_authorized",
}
ROOT = Path(__file__).resolve().parents[1]


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def resolve_artifact(root: Path, locator: Any) -> Path | None:
    if not is_safe_repository_path(locator):
        return None
    candidate = (root / locator).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def validate_runtime_binding(
    request: Any, runtime_identity: dict[str, str] | None, review_contract_bytes_sha256: str | None,
    target_identity: dict[str, Any] | None,
) -> list[str]:
    if validate_request_structure(request):
        return ["REVIEW_REQUEST_INVALID"]
    if runtime_identity is None:
        return ["REVIEWER_KIT_RUNTIME_IDENTITY_UNAVAILABLE"]
    reasons: list[str] = []
    for name in ("reviewer_kit_commit", "reviewer_kit_tree"):
        if runtime_identity.get(name) != request[name]:
            reasons.append(f"RUNTIME_{name.upper()}_MISMATCH")
    if not isinstance(review_contract_bytes_sha256, str) or not SHA256.fullmatch(review_contract_bytes_sha256):
        reasons.append("REVIEW_CONTRACT_HASH_INVALID")
    elif review_contract_bytes_sha256 != request["review_contract_bytes_sha256"]:
        reasons.append("REVIEW_CONTRACT_HASH_MISMATCH")
    if target_identity is None:
        reasons.append("TARGET_IDENTITY_REQUIRED")
    elif runtime_identity is not None and isinstance(review_contract_bytes_sha256, str) and SHA256.fullmatch(review_contract_bytes_sha256):
        actual = {
            **target_identity,
            **runtime_identity,
            "review_contract_bytes_sha256": review_contract_bytes_sha256,
        }
        from verify_candidate_identity import validate
        reasons.extend(validate(request, actual))
    return sorted(set(reasons))


def validate(manifest: Any, request: Any, artifact_root: Path) -> list[str]:
    if not isinstance(manifest, dict):
        return ["MANIFEST_NOT_OBJECT"]
    if not isinstance(request, dict):
        return ["REVIEW_REQUEST_REQUIRED"]
    if validate_request_structure(request):
        return ["REVIEW_REQUEST_INVALID"]
    if not artifact_root.is_dir():
        return ["ARTIFACT_ROOT_INVALID"]
    if set(manifest) != MANIFEST_FIELDS:
        return ["MANIFEST_FIELD_SET_INVALID"]
    reasons: list[str] = []
    if manifest["schema_version"] != "1.0.0":
        reasons.append("SCHEMA_VERSION_INVALID")
    if not isinstance(manifest["review_id"], str) or not REVIEW_ID.fullmatch(manifest["review_id"]):
        reasons.append("REVIEW_ID_INVALID")
    if manifest["review_id"] != request.get("review_id"):
        reasons.append("REVIEW_ID_MISMATCH")
    if not isinstance(manifest["review_request_sha256"], str) or not SHA256.fullmatch(manifest["review_request_sha256"]):
        reasons.append("REVIEW_REQUEST_HASH_INVALID")
    elif manifest["review_request_sha256"] != canonical_sha256(request):
        reasons.append("REVIEW_REQUEST_HASH_MISMATCH")
    if not isinstance(manifest["reviewer_kit_commit"], str) or not GIT_SHA.fullmatch(manifest["reviewer_kit_commit"]):
        reasons.append("REVIEWER_KIT_COMMIT_INVALID")
    elif manifest["reviewer_kit_commit"] != request.get("reviewer_kit_commit"):
        reasons.append("REVIEWER_KIT_COMMIT_MISMATCH")
    if not isinstance(manifest["reviewer_kit_tree"], str) or not GIT_SHA.fullmatch(manifest["reviewer_kit_tree"]):
        reasons.append("REVIEWER_KIT_TREE_INVALID")
    elif manifest["reviewer_kit_tree"] != request.get("reviewer_kit_tree"):
        reasons.append("REVIEWER_KIT_TREE_MISMATCH")
    request_candidate = request.get("candidate")
    if not isinstance(request_candidate, dict):
        reasons.append("REVIEW_REQUEST_CANDIDATE_INVALID")
    for name in ("candidate_commit", "candidate_tree"):
        if not isinstance(manifest[name], str) or not GIT_SHA.fullmatch(manifest[name]):
            reasons.append(f"{name.upper()}_INVALID")
        elif isinstance(request_candidate, dict) and manifest[name] != request_candidate.get(name.removeprefix("candidate_")):
            reasons.append(f"{name.upper()}_MISMATCH")
    if not isinstance(manifest["candidate_object_delta_sha256"], str) or not SHA256.fullmatch(manifest["candidate_object_delta_sha256"]):
        reasons.append("CANDIDATE_OBJECT_DELTA_SHA256_INVALID")
    elif manifest["candidate_object_delta_sha256"] != request["candidate_object_delta_sha256"]:
        reasons.append("CANDIDATE_OBJECT_DELTA_SHA256_MISMATCH")
    evidence = manifest["evidence"]
    if not isinstance(evidence, list) or not evidence:
        return reasons + ["EVIDENCE_REQUIRED"]
    ids: set[str] = set()
    for item in evidence:
        if not isinstance(item, dict):
            reasons.append("EVIDENCE_ITEM_TYPE_INVALID")
            continue
        if set(item) != EVIDENCE_FIELDS:
            reasons.append("EVIDENCE_FIELD_SET_INVALID")
            continue
        evidence_id = item["evidence_id"]
        if not isinstance(evidence_id, str) or not EVIDENCE_ID.fullmatch(evidence_id):
            reasons.append("EVIDENCE_ID_INVALID")
        elif evidence_id in ids:
            reasons.append("EVIDENCE_ID_DUPLICATE")
        else:
            ids.add(evidence_id)
        if not isinstance(item["kind"], str) or item["kind"] not in ALLOWED_KINDS:
            reasons.append("EVIDENCE_KIND_INVALID")
        if not isinstance(item["claim_direction"], str) or item["claim_direction"] not in ALLOWED_DIRECTIONS:
            reasons.append("EVIDENCE_DIRECTION_INVALID")
        artifact = resolve_artifact(artifact_root, item["raw_artifact_locator"])
        if artifact is None:
            reasons.append("RAW_ARTIFACT_LOCATOR_INVALID")
        elif not artifact.is_file():
            reasons.append("RAW_ARTIFACT_MISSING")
        if not isinstance(item["raw_artifact_sha256"], str) or not SHA256.fullmatch(item["raw_artifact_sha256"]):
            reasons.append("RAW_ARTIFACT_HASH_INVALID")
        elif artifact is not None and artifact.is_file() and hashlib.sha256(artifact.read_bytes()).hexdigest() != item["raw_artifact_sha256"]:
            reasons.append("RAW_ARTIFACT_HASH_MISMATCH")
        limitations = item["limitations"]
        if (
            not isinstance(limitations, list)
            or not limitations
            or any(not isinstance(value, str) or not value for value in limitations)
            or len(limitations) != len(set(limitations))
        ):
            reasons.append("LIMITATIONS_INVALID")
    return sorted(set(reasons))


def validate_verdict(verdict: Any, request: Any, manifest: Any, artifact_root: Path) -> list[str]:
    manifest_reasons = validate(manifest, request, artifact_root)
    if manifest_reasons:
        return ["EVIDENCE_MANIFEST_INVALID"]
    if not isinstance(verdict, dict) or set(verdict) != VERDICT_FIELDS:
        return ["VERDICT_FIELD_SET_INVALID"]
    reasons: list[str] = []
    if verdict["schema_version"] != "1.0.0":
        reasons.append("VERDICT_SCHEMA_VERSION_INVALID")
    if not isinstance(verdict["review_id"], str) or not REVIEW_ID.fullmatch(verdict["review_id"]):
        reasons.append("VERDICT_REVIEW_ID_INVALID")
    elif verdict["review_id"] != request["review_id"]:
        reasons.append("VERDICT_REVIEW_ID_MISMATCH")
    if not isinstance(verdict["review_request_sha256"], str) or not SHA256.fullmatch(verdict["review_request_sha256"]):
        reasons.append("VERDICT_REQUEST_HASH_INVALID")
    elif verdict["review_request_sha256"] != canonical_sha256(request):
        reasons.append("VERDICT_REQUEST_HASH_MISMATCH")
    if not isinstance(verdict["evidence_manifest_sha256"], str) or not SHA256.fullmatch(verdict["evidence_manifest_sha256"]):
        reasons.append("VERDICT_MANIFEST_HASH_INVALID")
    elif verdict["evidence_manifest_sha256"] != canonical_sha256(manifest):
        reasons.append("VERDICT_MANIFEST_HASH_MISMATCH")
    for name in ("reviewer_kit_commit", "reviewer_kit_tree"):
        if not isinstance(verdict[name], str) or not GIT_SHA.fullmatch(verdict[name]):
            reasons.append(f"VERDICT_{name.upper()}_INVALID")
        elif verdict[name] != request[name] or verdict[name] != manifest[name]:
            reasons.append(f"VERDICT_{name.upper()}_MISMATCH")
    for name, request_name in (("candidate_commit", "commit"), ("candidate_tree", "tree")):
        if not isinstance(verdict[name], str) or not GIT_SHA.fullmatch(verdict[name]):
            reasons.append(f"VERDICT_{name.upper()}_INVALID")
        elif verdict[name] != request["candidate"][request_name] or verdict[name] != manifest[name]:
            reasons.append(f"VERDICT_{name.upper()}_MISMATCH")
    if not isinstance(verdict["candidate_object_delta_sha256"], str) or not SHA256.fullmatch(verdict["candidate_object_delta_sha256"]):
        reasons.append("VERDICT_CANDIDATE_OBJECT_DELTA_SHA256_INVALID")
    elif verdict["candidate_object_delta_sha256"] != request["candidate_object_delta_sha256"] or verdict["candidate_object_delta_sha256"] != manifest["candidate_object_delta_sha256"]:
        reasons.append("VERDICT_CANDIDATE_OBJECT_DELTA_SHA256_MISMATCH")
    if not isinstance(verdict["verdict"], str) or verdict["verdict"] not in {"ACCEPT", "CHANGES_REQUIRED", "BLOCKED"}:
        reasons.append("VERDICT_VALUE_INVALID")
    if verdict["human_disposition"] != "pending" or verdict["promotion_state"] != "not-promoted" or verdict["next_stage_authorized"] is not False:
        reasons.append("VERDICT_AUTHORITY_ESCALATION")
    limitations = verdict["limitations"]
    if (
        not isinstance(limitations, list)
        or not limitations
        or any(not isinstance(value, str) or not value for value in limitations)
        or len(limitations) != len(set(limitations))
    ):
        reasons.append("VERDICT_LIMITATIONS_INVALID")
    evidence_ids = {item["evidence_id"] for item in manifest["evidence"]}
    findings = verdict["findings"]
    if not isinstance(findings, list):
        reasons.append("VERDICT_FINDINGS_INVALID")
    else:
        for finding in findings:
            if not isinstance(finding, dict) or set(finding) != {"finding_id", "severity", "epistemic_status", "evidence_ids", "summary"}:
                reasons.append("VERDICT_FINDING_INVALID")
                continue
            if (
                not isinstance(finding["finding_id"], str)
                or not re.fullmatch(r"^FIND-[A-Z0-9-]+$", finding["finding_id"])
                or not isinstance(finding["severity"], str)
                or finding["severity"] not in {"P0", "P1", "P2", "P3"}
                or not isinstance(finding["epistemic_status"], str)
                or finding["epistemic_status"] not in {"FACT", "INFERENCE", "UNKNOWN"}
                or not isinstance(finding["summary"], str)
                or not finding["summary"]
            ):
                reasons.append("VERDICT_FINDING_INVALID")
                continue
            finding_evidence = finding["evidence_ids"]
            if (
                not isinstance(finding_evidence, list)
                or not finding_evidence
                or any(not isinstance(value, str) or not EVIDENCE_ID.fullmatch(value) for value in finding_evidence)
                or len(finding_evidence) != len(set(finding_evidence))
                or any(value not in evidence_ids for value in finding_evidence)
            ):
                reasons.append("FINDING_EVIDENCE_REFERENCE_INVALID")
    return sorted(set(reasons))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--verdict", type=Path)
    parser.add_argument("--kit-root", type=Path, default=ROOT)
    parser.add_argument("--review-contract", type=Path, required=True)
    parser.add_argument("--target-root", type=Path, required=True)
    parser.add_argument("--base-commit", required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    request = json.loads(args.request.read_text(encoding="utf-8"))
    runtime_identity = read_runtime_identity(args.kit_root, args.review_contract)
    contract_sha256 = None
    if args.review_contract.is_file():
        contract_sha256 = hashlib.sha256(args.review_contract.read_bytes()).hexdigest()
    target_identity, target_reasons = derive_target_identity(args.target_root, args.base_commit, args.kit_root)
    reasons = target_reasons or validate_runtime_binding(request, runtime_identity, contract_sha256, target_identity)
    if not reasons:
        reasons = validate(manifest, request, args.artifact_root)
    if not reasons and args.verdict:
        reasons = validate_verdict(json.loads(args.verdict.read_text(encoding="utf-8")), request, manifest, args.artifact_root)
    print(json.dumps({"status": "PASS" if not reasons else "FAIL", "reasons": reasons}, sort_keys=True))
    return 0 if not reasons else 1


if __name__ == "__main__":
    raise SystemExit(main())
