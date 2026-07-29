#!/usr/bin/env python3
"""Derive and verify commit-bound review identity without executing target code."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MODE = re.compile(r"^[0-7]{6}$")
REVIEW_ID = re.compile(r"^IRR-[A-Z0-9-]+$")
MAX_OUTPUT_BYTES = 4 * 1024 * 1024
GIT_TIMEOUT_SECONDS = 10
REQUEST_FIELDS = {
    "schema_version", "review_id", "repository_locator", "base", "candidate",
    "changed_paths", "changed_paths_sha256", "candidate_object_delta_sha256",
    "review_contract_bytes_sha256", "reviewer_kit_commit", "reviewer_kit_tree",
    "requested_checks",
}
ACTUAL_FIELDS = {
    "base_commit", "base_tree", "candidate_commit", "candidate_tree",
    "changed_paths", "changed_paths_sha256", "candidate_object_delta_sha256",
    "reviewer_kit_commit", "reviewer_kit_tree", "review_contract_bytes_sha256",
}
KIT_MODULES = (
    "scripts/verify_candidate_identity.py",
    "scripts/verify_evidence_manifest.py",
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def is_safe_repository_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or value.startswith("/"):
        return False
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        return False
    return all(segment not in {"", ".", ".."} for segment in value.split("/"))


def clean_git_env() -> dict[str, str]:
    """Return a minimal environment that ignores inherited Git configuration."""
    environment = {"PATH": os.environ.get("PATH", "")}
    if os.name == "nt":
        for name in ("SYSTEMROOT", "WINDIR"):
            if os.environ.get(name):
                environment[name] = os.environ[name]
    environment.update({
        "LC_ALL": "C",
        "LANG": "C",
        "PAGER": "cat",
        "GIT_PAGER": "cat",
        "GIT_EDITOR": "true",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
    })
    return environment


def run_git(root: Path, arguments: list[str], *, allowed_returncodes: set[int] = {0}) -> tuple[int, bytes]:
    command = [
        "git", "--no-optional-locks", "-C", str(root),
        "-c", "core.hooksPath=/dev/null",
        "-c", "core.fsmonitor=false",
        "-c", f"core.attributesFile={os.devnull}",
        "-c", "core.quotepath=true",
        "-c", "diff.external=",
        "-c", "diff.renames=false",
        "--no-pager",
        *arguments,
    ]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            env=clean_git_env(),
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError("GIT_COMMAND_UNAVAILABLE") from error
    output = result.stdout + result.stderr
    if len(output) > MAX_OUTPUT_BYTES:
        raise RuntimeError("GIT_OUTPUT_TOO_LARGE")
    if result.returncode not in allowed_returncodes:
        raise RuntimeError("GIT_COMMAND_FAILED")
    return result.returncode, result.stdout


def _text(root: Path, arguments: list[str]) -> str:
    return run_git(root, arguments)[1].decode("ascii", "strict").strip()


def _path_text(root: Path, arguments: list[str]) -> str:
    """Decode Git path output with the platform filesystem codec, not ASCII."""
    output = run_git(root, arguments)[1]
    if output.endswith(b"\n"):
        output = output[:-1]
    return os.fsdecode(output)


def repository_info(root: Path) -> dict[str, Path | str] | None:
    try:
        if _text(root, ["rev-parse", "--is-bare-repository"]) != "false":
            return None
        if _text(root, ["rev-parse", "--show-object-format"]) != "sha1":
            return None
        top_level = Path(_path_text(root, ["rev-parse", "--show-toplevel"])).resolve(strict=True)
        common_text = _path_text(root, ["rev-parse", "--git-common-dir"])
        common_dir = (Path(common_text) if Path(common_text).is_absolute() else root / common_text).resolve(strict=True)
    except (RuntimeError, OSError):
        return None
    return {"top_level": top_level, "common_dir": common_dir, "object_format": "sha1"}


def paths_overlap(first: Path, second: Path) -> bool:
    try:
        first.relative_to(second)
        return True
    except ValueError:
        pass
    try:
        second.relative_to(first)
        return True
    except ValueError:
        return False


def direct_commit(root: Path, object_id: str) -> str | None:
    if not isinstance(object_id, str) or not GIT_SHA.fullmatch(object_id):
        return None
    try:
        if _text(root, ["cat-file", "-t", object_id]) != "commit":
            return None
        resolved = _text(root, ["rev-parse", "--verify", object_id])
    except RuntimeError:
        return None
    return resolved if GIT_SHA.fullmatch(resolved) and resolved == object_id else None


def tree_for_commit(root: Path, commit: str) -> str | None:
    try:
        tree = _text(root, ["rev-parse", "--verify", f"{commit}^{{tree}}"])
    except RuntimeError:
        return None
    return tree if GIT_SHA.fullmatch(tree) else None


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def tracked_blob_matches(kit_root: Path, relative_path: str) -> bool:
    if not is_safe_repository_path(relative_path):
        return False
    path = (kit_root / relative_path).resolve()
    try:
        path.relative_to(kit_root.resolve(strict=True))
        data = path.read_bytes()
        listing = run_git(kit_root, ["ls-tree", "-r", "HEAD", "--", relative_path])[1].decode("utf-8", "strict").strip()
    except (RuntimeError, OSError, UnicodeDecodeError):
        return False
    if not listing or "\t" not in listing:
        return False
    header, listed_path = listing.split("\t", 1)
    fields = header.split()
    return len(fields) == 3 and fields[1] == "blob" and fields[2] == git_blob_sha1(data) and listed_path == relative_path


def read_runtime_identity(kit_root: Path, review_contract: Path | None = None) -> dict[str, str] | None:
    info = repository_info(kit_root)
    if info is None:
        return None
    root = info["top_level"]
    assert isinstance(root, Path)
    try:
        head = _text(root, ["rev-parse", "--verify", "HEAD"])
    except RuntimeError:
        return None
    commit = direct_commit(root, head)
    tree = tree_for_commit(root, commit) if commit else None
    if not commit or not tree or any(not tracked_blob_matches(root, path) for path in KIT_MODULES):
        return None
    if review_contract is not None:
        try:
            relative_contract = review_contract.resolve(strict=True).relative_to(root).as_posix()
        except (OSError, ValueError):
            return None
        if not tracked_blob_matches(root, relative_contract):
            return None
    return {"reviewer_kit_commit": commit, "reviewer_kit_tree": tree}


def parse_raw_delta(raw: bytes) -> list[dict[str, str]]:
    fields = raw.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()
    if len(fields) % 2:
        raise ValueError("TARGET_RAW_DELTA_INVALID")
    entries: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    for index in range(0, len(fields), 2):
        try:
            header = fields[index].decode("ascii", "strict")
            path = fields[index + 1].decode("utf-8", "strict")
        except UnicodeDecodeError as error:
            raise ValueError("TARGET_PATH_UNSUPPORTED") from error
        parts = header.split()
        if len(parts) != 5 or not parts[0].startswith(":"):
            raise ValueError("TARGET_RAW_DELTA_INVALID")
        old_mode, new_mode, old_oid, new_oid, status = parts[0][1:], parts[1], parts[2], parts[3], parts[4]
        if (
            not MODE.fullmatch(old_mode) or not MODE.fullmatch(new_mode)
            or not GIT_SHA.fullmatch(old_oid) or not GIT_SHA.fullmatch(new_oid)
            or status not in {"A", "D", "M", "T"} or not is_safe_repository_path(path) or path in seen_paths
        ):
            raise ValueError("TARGET_RAW_DELTA_INVALID")
        zero = "0" * 40
        if (status == "A" and (old_oid != zero or new_oid == zero)) or (status == "D" and (old_oid == zero or new_oid != zero)) or (status in {"M", "T"} and (old_oid == zero or new_oid == zero)):
            raise ValueError("TARGET_RAW_DELTA_INVALID")
        seen_paths.add(path)
        entries.append({"path": path, "status": status, "old_mode": old_mode, "new_mode": new_mode, "old_oid": old_oid, "new_oid": new_oid})
    return sorted(entries, key=lambda entry: entry["path"].encode("utf-8"))


def derive_target_identity(target_root: Path, base_commit: str, kit_root: Path) -> tuple[dict[str, Any] | None, list[str]]:
    target_info = repository_info(target_root)
    kit_info = repository_info(kit_root)
    if target_info is None:
        return None, ["TARGET_REPOSITORY_INVALID_OR_UNSUPPORTED"]
    if kit_info is None:
        return None, ["REVIEWER_KIT_RUNTIME_IDENTITY_UNAVAILABLE"]
    target_top = target_info["top_level"]
    target_common = target_info["common_dir"]
    kit_top = kit_info["top_level"]
    kit_common = kit_info["common_dir"]
    assert isinstance(target_top, Path) and isinstance(target_common, Path) and isinstance(kit_top, Path) and isinstance(kit_common, Path)
    if target_common.samefile(kit_common) or paths_overlap(target_top, kit_top):
        return None, ["TARGET_REPOSITORY_NOT_INDEPENDENT"]
    base = direct_commit(target_top, base_commit)
    try:
        head_raw = _text(target_top, ["rev-parse", "--verify", "HEAD"])
    except RuntimeError:
        return None, ["TARGET_HEAD_UNAVAILABLE"]
    candidate = direct_commit(target_top, head_raw)
    if not base:
        return None, ["BASE_COMMIT_INVALID"]
    if not candidate:
        return None, ["TARGET_HEAD_NOT_DIRECT_COMMIT"]
    returncode, _ = run_git(target_top, ["merge-base", "--is-ancestor", base, candidate], allowed_returncodes={0, 1})
    if returncode != 0:
        return None, ["BASE_NOT_ANCESTOR"]
    base_tree = tree_for_commit(target_top, base)
    candidate_tree = tree_for_commit(target_top, candidate)
    if not base_tree or not candidate_tree:
        return None, ["TARGET_TREE_UNAVAILABLE"]
    try:
        raw = run_git(target_top, ["diff-tree", "-r", "-z", "--no-commit-id", "--raw", "--no-abbrev", "--no-renames", "--no-ext-diff", "--no-textconv", "--ignore-submodules=none", base, candidate])[1]
        entries = parse_raw_delta(raw)
    except (RuntimeError, ValueError):
        return None, ["TARGET_OBJECT_DELTA_INVALID"]
    if not entries:
        return None, ["TARGET_OBJECT_DELTA_EMPTY"]
    paths = [entry["path"] for entry in entries]
    delta = {"format": "target-object-delta-v1", "entries": entries}
    return {
        "base_commit": base,
        "base_tree": base_tree,
        "candidate_commit": candidate,
        "candidate_tree": candidate_tree,
        "changed_paths": paths,
        "changed_paths_sha256": canonical_sha256(paths),
        "candidate_object_delta_sha256": hashlib.sha256(canonical_bytes(delta)).hexdigest(),
    }, []


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
    for name in ("review_contract_bytes_sha256", "changed_paths_sha256", "candidate_object_delta_sha256"):
        if not isinstance(request[name], str) or not SHA256.fullmatch(request[name]):
            reasons.append(f"{name.upper()}_INVALID")
    for name in ("reviewer_kit_commit", "reviewer_kit_tree"):
        if not isinstance(request[name], str) or not GIT_SHA.fullmatch(request[name]):
            reasons.append(f"{name.upper()}_INVALID")
    requested_checks = request["requested_checks"]
    if not isinstance(requested_checks, list) or not requested_checks or any(not isinstance(value, str) or not value for value in requested_checks) or len(requested_checks) != len(set(requested_checks)):
        reasons.append("REQUESTED_CHECKS_INVALID")
    base, candidate, changed_paths = request["base"], request["candidate"], request["changed_paths"]
    if not isinstance(base, dict) or set(base) != {"commit", "tree"} or not isinstance(candidate, dict) or set(candidate) != {"commit", "tree"} or any(not isinstance(value, str) or not GIT_SHA.fullmatch(value) for identity in (base, candidate) for value in identity.values()):
        reasons.append("REQUEST_GIT_IDENTITY_INVALID")
    if not isinstance(changed_paths, list) or not changed_paths or any(not isinstance(path, str) for path in changed_paths):
        reasons.append("REQUEST_PATHS_INVALID")
    elif any(not is_safe_repository_path(path) for path in changed_paths):
        reasons.append("REQUEST_PATH_INVALID")
    elif len(changed_paths) != len(set(changed_paths)):
        reasons.append("REQUEST_PATHS_DUPLICATE")
    elif request["changed_paths_sha256"] != canonical_sha256(sorted(changed_paths, key=lambda value: value.encode("utf-8"))):
        reasons.append("REQUEST_PATH_MANIFEST_HASH_INVALID")
    return sorted(set(reasons))


def validate(request: Any, actual: Any) -> list[str]:
    reasons = validate_request_structure(request)
    if reasons:
        return reasons
    if not isinstance(actual, dict) or set(actual) != ACTUAL_FIELDS:
        return ["ACTUAL_IDENTITY_INVALID"]
    for name in ("base_commit", "base_tree", "candidate_commit", "candidate_tree", "reviewer_kit_commit", "reviewer_kit_tree"):
        if not isinstance(actual[name], str) or not GIT_SHA.fullmatch(actual[name]):
            return ["ACTUAL_IDENTITY_INVALID"]
    for name in ("changed_paths_sha256", "candidate_object_delta_sha256", "review_contract_bytes_sha256"):
        if not isinstance(actual[name], str) or not SHA256.fullmatch(actual[name]):
            return ["ACTUAL_IDENTITY_INVALID"]
    if not isinstance(actual["changed_paths"], list) or any(not is_safe_repository_path(path) for path in actual["changed_paths"]):
        return ["ACTUAL_PATH_INVALID"]
    comparisons = {
        "BASE_COMMIT_MISMATCH": (request["base"]["commit"], actual["base_commit"]),
        "BASE_TREE_MISMATCH": (request["base"]["tree"], actual["base_tree"]),
        "CANDIDATE_COMMIT_MISMATCH": (request["candidate"]["commit"], actual["candidate_commit"]),
        "CANDIDATE_TREE_MISMATCH": (request["candidate"]["tree"], actual["candidate_tree"]),
        "REVIEWER_KIT_COMMIT_MISMATCH": (request["reviewer_kit_commit"], actual["reviewer_kit_commit"]),
        "REVIEWER_KIT_TREE_MISMATCH": (request["reviewer_kit_tree"], actual["reviewer_kit_tree"]),
        "REVIEW_CONTRACT_HASH_MISMATCH": (request["review_contract_bytes_sha256"], actual["review_contract_bytes_sha256"]),
        "CHANGED_PATHS_HASH_MISMATCH": (request["changed_paths_sha256"], actual["changed_paths_sha256"]),
        "CANDIDATE_OBJECT_DELTA_HASH_MISMATCH": (request["candidate_object_delta_sha256"], actual["candidate_object_delta_sha256"]),
    }
    reasons = [reason for reason, (expected, observed) in comparisons.items() if expected != observed]
    actual_paths = actual["changed_paths"]
    if len(actual_paths) != len(set(actual_paths)):
        reasons.append("ACTUAL_PATHS_DUPLICATE")
    if request["changed_paths"] != actual_paths:
        reasons.append("CHANGED_PATHS_MISMATCH")
    return sorted(set(reasons))


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("review request must be a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--target-root", type=Path, required=True)
    parser.add_argument("--base-commit", required=True)
    parser.add_argument("--kit-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--review-contract", type=Path, required=True)
    args = parser.parse_args()
    request = load_json(args.request)
    runtime_identity = read_runtime_identity(args.kit_root, args.review_contract)
    target_identity, target_reasons = derive_target_identity(args.target_root, args.base_commit, args.kit_root)
    if runtime_identity is None:
        reasons = ["REVIEWER_KIT_RUNTIME_IDENTITY_UNAVAILABLE"]
    elif target_reasons:
        reasons = target_reasons
    else:
        assert target_identity is not None
        reasons = validate(request, {
            **target_identity,
            **runtime_identity,
            "review_contract_bytes_sha256": hashlib.sha256(args.review_contract.read_bytes()).hexdigest(),
        })
    print(json.dumps({"status": "PASS" if not reasons else "FAIL", "reasons": reasons}, sort_keys=True))
    return 0 if not reasons else 1


if __name__ == "__main__":
    raise SystemExit(main())
