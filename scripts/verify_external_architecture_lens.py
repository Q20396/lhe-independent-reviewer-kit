#!/usr/bin/env python3
"""Validate supplied external architecture artifacts without installing or running them."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


OID = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
ARTIFACT_ID = re.compile(r"^EXT-ART-[A-Z0-9-]+$")
EVIDENCE_ID = re.compile(r"^EXT-EV-[A-Z0-9-]+$")
FINDING_ID = re.compile(r"^LENS-[A-Z0-9-]+$")
ARTIFACT_FIELDS = {"schema_version", "artifact_id", "source_repository", "ref", "commit", "license", "retrieved_at", "acquisition_method", "evidence_state", "evidence_items", "known_limitations", "human_disposition", "next_stage_authorized"}
EVIDENCE_FIELDS = {"evidence_id", "path", "content_sha256", "provenance"}
REVIEW_FIELDS = {"schema_version", "artifact_ids", "status", "findings", "limitations", "next_safe_action", "external_installation_required", "external_execution_required", "network_behavior", "hook_behavior", "persistence_behavior", "human_disposition", "next_stage_authorized"}
FINDING_FIELDS = {"finding_id", "classification", "statement", "evidence_refs", "disposition", "recommended_target"}


def string_list(value: Any, *, nonempty: bool = False) -> bool:
    return isinstance(value, list) and (bool(value) if nonempty else True) and all(isinstance(item, str) and item for item in value) and len(value) == len(set(value))


def safe_path(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and not value.startswith("/") and "\\" not in value and "\x00" not in value and "\r" not in value and "\n" not in value and all(segment not in {"", ".", ".."} for segment in value.split("/"))


def validate_artifacts(artifacts: Any) -> list[str]:
    if not isinstance(artifacts, list) or not artifacts:
        return ["ARTIFACT_COLLECTION_INVALID"]
    reasons: list[str] = []
    artifact_ids: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict) or set(artifact) != ARTIFACT_FIELDS:
            reasons.append("ARTIFACT_FIELD_SET_INVALID")
            continue
        artifact_id = artifact.get("artifact_id")
        if not isinstance(artifact_id, str) or not ARTIFACT_ID.fullmatch(artifact_id):
            reasons.append("ARTIFACT_ID_INVALID")
        elif artifact_id in artifact_ids:
            reasons.append("ARTIFACT_ID_DUPLICATE")
        else:
            artifact_ids.add(artifact_id)
        if artifact.get("schema_version") != "1.0.0" or not isinstance(artifact.get("source_repository"), str) or not artifact["source_repository"] or not isinstance(artifact.get("ref"), str) or not artifact["ref"] or not isinstance(artifact.get("commit"), str) or not OID.fullmatch(artifact["commit"]):
            reasons.append("ARTIFACT_IDENTITY_INVALID")
        if not isinstance(artifact.get("license"), str) or not artifact["license"] or not isinstance(artifact.get("retrieved_at"), str) or not artifact["retrieved_at"] or artifact.get("acquisition_method") != "public_read_only" or artifact.get("evidence_state") != "declared_opaque" or not string_list(artifact.get("known_limitations"), nonempty=True):
            reasons.append("ARTIFACT_EVIDENCE_BOUNDARY_INVALID")
        items = artifact.get("evidence_items")
        if not isinstance(items, list) or not items:
            reasons.append("ARTIFACT_EVIDENCE_ITEMS_INVALID")
        else:
            evidence_ids: set[str] = set()
            for item in items:
                if not isinstance(item, dict) or set(item) != EVIDENCE_FIELDS:
                    reasons.append("ARTIFACT_EVIDENCE_ITEM_INVALID")
                    continue
                evidence_id = item.get("evidence_id")
                if not isinstance(evidence_id, str) or not EVIDENCE_ID.fullmatch(evidence_id) or evidence_id in evidence_ids:
                    reasons.append("ARTIFACT_EVIDENCE_ITEM_INVALID")
                else:
                    evidence_ids.add(evidence_id)
                if not safe_path(item.get("path")) or not isinstance(item.get("content_sha256"), str) or not SHA256.fullmatch(item["content_sha256"]) or not isinstance(item.get("provenance"), str) or item["provenance"] not in {"EXTRACTED", "INFERRED"}:
                    reasons.append("ARTIFACT_EVIDENCE_ITEM_INVALID")
        if artifact.get("human_disposition") != "pending" or artifact.get("next_stage_authorized") is not False:
            reasons.append("ARTIFACT_AUTHORITY_ESCALATION")
    return sorted(set(reasons))


def validate_review(review: Any, artifacts: Any) -> list[str]:
    if validate_artifacts(artifacts):
        return ["ARTIFACTS_INVALID"]
    if not isinstance(review, dict) or set(review) != REVIEW_FIELDS:
        return ["REVIEW_FIELD_SET_INVALID"]
    if review.get("schema_version") != "1.0.0" or not string_list(review.get("artifact_ids"), nonempty=True) or any(not ARTIFACT_ID.fullmatch(item) for item in review["artifact_ids"]) or not isinstance(review.get("status"), str) or review["status"] not in {"blocked", "unverified", "requires_human_decision"}:
        return ["REVIEW_IDENTITY_INVALID"]
    artifact_map = {artifact["artifact_id"]: {item["evidence_id"]: item for item in artifact["evidence_items"]} for artifact in artifacts}
    if set(review["artifact_ids"]) != set(artifact_map):
        return ["REVIEW_ARTIFACT_BINDING_INVALID"]
    if review.get("external_installation_required") is not False or review.get("external_execution_required") is not False or any(review.get(field) != "forbidden" for field in ("network_behavior", "hook_behavior", "persistence_behavior")):
        return ["REVIEW_EFFECT_ESCALATION"]
    if review.get("human_disposition") != "pending" or review.get("next_stage_authorized") is not False:
        return ["REVIEW_AUTHORITY_ESCALATION"]
    if not string_list(review.get("limitations"), nonempty=True) or not isinstance(review.get("next_safe_action"), str) or not review["next_safe_action"]:
        return ["REVIEW_EVIDENCE_BOUNDARY_INVALID"]
    findings = review.get("findings")
    if not isinstance(findings, list) or not findings:
        return ["REVIEW_FINDINGS_INVALID"]
    reasons: list[str] = []
    finding_ids: set[str] = set()
    for finding in findings:
        if not isinstance(finding, dict) or set(finding) != FINDING_FIELDS:
            reasons.append("REVIEW_FINDING_INVALID")
            continue
        finding_id = finding.get("finding_id")
        if not isinstance(finding_id, str) or not FINDING_ID.fullmatch(finding_id) or finding_id in finding_ids:
            reasons.append("REVIEW_FINDING_INVALID")
        else:
            finding_ids.add(finding_id)
        if not isinstance(finding.get("classification"), str) or finding["classification"] not in {"FACT", "INFERENCE", "UNKNOWN"} or not isinstance(finding.get("statement"), str) or not finding["statement"] or not isinstance(finding.get("disposition"), str) or finding["disposition"] not in {"adopt", "reject", "defer"} or not isinstance(finding.get("recommended_target"), str) or finding["recommended_target"] not in {"reviewer_kit", "lhe_proposal_only", "defer"}:
            reasons.append("REVIEW_FINDING_INVALID")
            continue
        refs = finding.get("evidence_refs")
        if not string_list(refs) or (finding["classification"] != "UNKNOWN" and not refs) or any(":" not in reference for reference in refs):
            reasons.append("REVIEW_FINDING_EVIDENCE_INVALID")
            continue
        for reference in refs:
            artifact_id, evidence_id = reference.split(":", 1)
            if artifact_id not in artifact_map or evidence_id not in artifact_map[artifact_id]:
                reasons.append("REVIEW_FINDING_EVIDENCE_INVALID")
            elif finding["classification"] == "FACT" and artifact_map[artifact_id][evidence_id]["provenance"] != "EXTRACTED":
                reasons.append("REVIEW_FACT_PROVENANCE_INVALID")
        if finding["classification"] == "FACT":
            reasons.append("REVIEW_FACT_UNVERIFIED")
        if finding["recommended_target"] == "lhe_proposal_only" and finding["disposition"] == "adopt":
            reasons.append("REVIEW_LHE_MUTATION_FORBIDDEN")
    return sorted(set(reasons))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    args = parser.parse_args()
    try:
        artifacts, review = load_json(args.artifacts), load_json(args.review)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        print(json.dumps({"status": "FAIL", "reasons": ["INPUT_DOCUMENT_INVALID"]}, sort_keys=True))
        return 1
    reasons = validate_artifacts(artifacts) or validate_review(review, artifacts)
    print(json.dumps({"status": "PASS" if not reasons else "FAIL", "reasons": reasons}, sort_keys=True))
    return 0 if not reasons else 1


if __name__ == "__main__":
    raise SystemExit(main())
