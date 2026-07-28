#!/usr/bin/env python3
"""Verify a review request against supplied immutable candidate identity."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
REVIEW_ID = re.compile(r"^IRR-[A-Z0-9-]+$")
REQUEST_FIELDS = {
    "schema_version", "review_id", "repository_locator", "base", "candidate",
    "changed_paths", "changed_paths_sha256", "review_contract_bytes_sha256",
    "reviewer_kit_commit", "reviewer_kit_tree", "requested_checks",
}
ACTUAL_FIELDS = {
    "base_commit", "base_tree", "candidate_commit", "candidate_tree",
    "reviewer_kit_commit", "reviewer_kit_tree", "review_contract_bytes_sha256", "changed_paths",
}


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("review request must be a JSON object")
    return value


def is_safe_repository_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    if value.startswith("/") or any(ord(character) < 32 for character in value):
        return False
    return all(segment not in {"", ".", ".."} for segment in value.split("/"))


def validate_request_structure(request: Any) -> list[str]:
    if not isinstance(request, dict) or set(request) != REQUEST_FIELDS:
        return ["REQUEST_FIELD_SET_INVALID"]
    reasons: list[str] = []
    if request["schema_version"] != "1.0.0":
        reasons.append("SCHEMA_VERSION_INVALID")
    if not isinstance(request["review_id"], str) or not REVIEW_ID.fullmatch(request["review_id"]):
        reasons.append("REVIEW_ID_INVALID")
    if not isinstance(request["repository_locator"], str) or not request["repository_locator"]:
        reasons.append("REPOSITORY_LOCATOR_INVALID")
    if not isinstance(request["review_contract_bytes_sha256"], str) or not SHA256.fullmatch(request["review_contract_bytes_sha256"]):
        reasons.append("REVIEW_CONTRACT_HASH_INVALID")
    if not isinstance(request["reviewer_kit_commit"], str) or not GIT_SHA.fullmatch(request["reviewer_kit_commit"]):
        reasons.append("REVIEWER_KIT_COMMIT_INVALID")
    if not isinstance(request["reviewer_kit_tree"], str) or not GIT_SHA.fullmatch(request["reviewer_kit_tree"]):
        reasons.append("REVIEWER_KIT_TREE_INVALID")
    requested_checks = request["requested_checks"]
    if (
        not isinstance(requested_checks, list)
        or not requested_checks
        or any(not isinstance(value, str) or not value for value in requested_checks)
        or len(requested_checks) != len(set(requested_checks))
    ):
        reasons.append("REQUESTED_CHECKS_INVALID")
    base = request.get("base")
    candidate = request.get("candidate")
    changed_paths = request.get("changed_paths")
    if (
        not isinstance(base, dict) or set(base) != {"commit", "tree"}
        or not isinstance(candidate, dict) or set(candidate) != {"commit", "tree"}
        or any(not isinstance(value, str) or not GIT_SHA.fullmatch(value) for identity in (base, candidate) for value in identity.values())
    ):
        reasons.append("REQUEST_GIT_IDENTITY_INVALID")
    if (
        not isinstance(changed_paths, list)
        or not changed_paths
        or any(not isinstance(item, str) or not item for item in changed_paths)
    ):
        reasons.append("REQUEST_PATHS_INVALID")
    else:
        if len(changed_paths) != len(set(changed_paths)):
            reasons.append("REQUEST_PATHS_DUPLICATE")
        if any(not is_safe_repository_path(path) for path in changed_paths):
            reasons.append("REQUEST_PATH_INVALID")
        expected_hash = canonical_sha256(sorted(changed_paths))
        if request.get("changed_paths_sha256") != expected_hash:
            reasons.append("REQUEST_PATH_MANIFEST_HASH_INVALID")
    return sorted(set(reasons))


def validate(request: Any, actual: Any) -> list[str]:
    request_reasons = validate_request_structure(request)
    if request_reasons:
        return request_reasons
    if not isinstance(actual, dict) or set(actual) != ACTUAL_FIELDS:
        return ["ACTUAL_IDENTITY_INVALID"]
    if any(
        not isinstance(actual[name], str) or not GIT_SHA.fullmatch(actual[name])
        for name in ("base_commit", "base_tree", "candidate_commit", "candidate_tree", "reviewer_kit_commit", "reviewer_kit_tree")
    ) or not isinstance(actual["review_contract_bytes_sha256"], str) or not SHA256.fullmatch(actual["review_contract_bytes_sha256"]):
        return ["ACTUAL_IDENTITY_INVALID"]
    actual_paths = actual["changed_paths"]
    if not isinstance(actual_paths, list) or any(not is_safe_repository_path(path) for path in actual_paths):
        return ["ACTUAL_PATH_INVALID"]
    reasons: list[str] = []
    base = request["base"]
    candidate = request["candidate"]
    changed_paths = request["changed_paths"]
    if base["commit"] != actual["base_commit"]:
        reasons.append("BASE_COMMIT_MISMATCH")
    if base["tree"] != actual["base_tree"]:
        reasons.append("BASE_TREE_MISMATCH")
    if candidate["commit"] != actual["candidate_commit"]:
        reasons.append("CANDIDATE_COMMIT_MISMATCH")
    if candidate["tree"] != actual["candidate_tree"]:
        reasons.append("CANDIDATE_TREE_MISMATCH")
    if request["reviewer_kit_commit"] != actual["reviewer_kit_commit"]:
        reasons.append("REVIEWER_KIT_COMMIT_MISMATCH")
    if request["reviewer_kit_tree"] != actual["reviewer_kit_tree"]:
        reasons.append("REVIEWER_KIT_TREE_MISMATCH")
    if request["review_contract_bytes_sha256"] != actual["review_contract_bytes_sha256"]:
        reasons.append("REVIEW_CONTRACT_HASH_MISMATCH")
    if len(actual_paths) != len(set(actual_paths)):
        reasons.append("ACTUAL_PATHS_DUPLICATE")
    if sorted(changed_paths) != sorted(actual_paths):
        reasons.append("CHANGED_PATHS_MISMATCH")
    return sorted(set(reasons))


def read_runtime_identity(kit_root: Path) -> dict[str, str] | None:
    try:
        commit = subprocess.run(
            ["git", "-C", str(kit_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        tree = subprocess.run(
            ["git", "-C", str(kit_root), "rev-parse", "HEAD^{tree}"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    if not GIT_SHA.fullmatch(commit) or not GIT_SHA.fullmatch(tree):
        return None
    return {"reviewer_kit_commit": commit, "reviewer_kit_tree": tree}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--base-commit", required=True)
    parser.add_argument("--base-tree", required=True)
    parser.add_argument("--candidate-commit", required=True)
    parser.add_argument("--candidate-tree", required=True)
    parser.add_argument("--kit-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--review-contract", type=Path, required=True)
    parser.add_argument("--changed-paths", type=Path, required=True)
    args = parser.parse_args()
    request = load_json(args.request)
    runtime_identity = read_runtime_identity(args.kit_root)
    if runtime_identity is None:
        print(json.dumps({"status": "FAIL", "reasons": ["REVIEWER_KIT_RUNTIME_IDENTITY_UNAVAILABLE"]}, sort_keys=True))
        return 1
    paths = [line for line in args.changed_paths.read_text(encoding="utf-8").splitlines() if line]
    reasons = validate(request, {
        "base_commit": args.base_commit,
        "base_tree": args.base_tree,
        "candidate_commit": args.candidate_commit,
        "candidate_tree": args.candidate_tree,
        **runtime_identity,
        "review_contract_bytes_sha256": hashlib.sha256(args.review_contract.read_bytes()).hexdigest(),
        "changed_paths": paths,
    })
    print(json.dumps({"status": "PASS" if not reasons else "FAIL", "reasons": reasons}, sort_keys=True))
    return 0 if not reasons else 1


if __name__ == "__main__":
    raise SystemExit(main())
